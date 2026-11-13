"""Ticket management endpoints."""
from datetime import datetime, timezone
import hashlib
import io
import os
from flask import request, g, current_app, send_file
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func
from app import db
from app.api.v1 import api_v1_bp
from app.models.ticket import Ticket, Comment, Activity, Attachment
from app.models.notification import Notification
from app.utils.auth import require_auth, require_workspace_member
from app.utils.errors import ValidationError, NotFoundError, AuthorizationError
from app.utils.validators import require_fields, paginate_params, success_response
import uuid
import structlog

logger = structlog.get_logger()


def _save_attachment(relative_path: str, filename: str, content: bytes, content_type: str) -> None:
    if current_app.config["USE_OBJECT_STORAGE"]:
        from app.utils.storage import get_s3_client
        key = f"{relative_path}/{filename}"
        get_s3_client().put_object(
            Bucket=current_app.config["AWS_BUCKET_NAME"],
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return

    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], *relative_path.split("/"))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, filename), "wb") as stream:
        stream.write(content)


def _read_attachment(relative_path: str, filename: str) -> bytes:
    if current_app.config["USE_OBJECT_STORAGE"]:
        from app.utils.storage import get_s3_client
        key = f"{relative_path}/{filename}"
        response = get_s3_client().get_object(
            Bucket=current_app.config["AWS_BUCKET_NAME"],
            Key=key,
        )
        return response["Body"].read()

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], *relative_path.split("/"), filename)
    with open(path, "rb") as stream:
        return stream.read()


def _next_ticket_number(workspace_id) -> int:
    max_num = (
        db.session.query(func.coalesce(func.max(Ticket.number), 0))
        .filter(Ticket.workspace_id == workspace_id)
        .scalar()
    )
    return max_num + 1


def _log_activity(ticket, action: str, details: dict = None, actor_id=None):
    act = Activity(
        workspace_id=ticket.workspace_id,
        ticket_id=ticket.id,
        actor_id=actor_id or g.current_user.id,
        action=action,
        details=details or {},
    )
    db.session.add(act)


def _notify(user_id, workspace_id, ticket_id, ntype: str, title: str, body: str = None, data: dict = None):
    if user_id == g.current_user.id:
        return  # don't notify self
    n = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        type=ntype,
        title=title,
        body=body,
        data=data or {},
    )
    db.session.add(n)


@api_v1_bp.route("/workspaces/<workspace_id>/tickets", methods=["GET"])
@require_workspace_member("viewer")
def list_tickets(workspace_id):
    page, per_page = paginate_params(request.args)
    q = Ticket.query.filter_by(workspace_id=g.workspace.id)

    # Filters
    status = request.args.get("status")
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip() in Ticket.STATUSES]
        if statuses:
            q = q.filter(Ticket.status.in_(statuses))

    priority = request.args.get("priority")
    if priority and priority in Ticket.PRIORITIES:
        q = q.filter(Ticket.priority == priority)

    assignee = request.args.get("assignee")
    if assignee == "me":
        q = q.filter(Ticket.assignee_id == g.current_user.id)
    elif assignee == "unassigned":
        q = q.filter(Ticket.assignee_id.is_(None))
    elif assignee:
        try:
            q = q.filter(Ticket.assignee_id == uuid.UUID(assignee))
        except ValueError:
            pass

    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            Ticket.title.ilike(like),
            Ticket.description.ilike(like),
            func.array_to_string(Ticket.tags, " ").ilike(like),
            Ticket.comments.any(Comment.body.ilike(like)),
        ))

    # Sorting
    sort = request.args.get("sort", "-created_at")
    desc = sort.startswith("-")
    field = sort.lstrip("-")
    sort_map = {
        "created_at": Ticket.created_at,
        "updated_at": Ticket.updated_at,
        "priority": Ticket.priority,
        "status": Ticket.status,
        "number": Ticket.number,
    }
    col = sort_map.get(field, Ticket.created_at)
    q = q.order_by(col.desc() if desc else col.asc())

    total = q.count()
    tickets = q.offset((page - 1) * per_page).limit(per_page).all()

    return success_response(
        [t.to_dict() for t in tickets],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@api_v1_bp.route("/workspaces/<workspace_id>/tickets", methods=["POST"])
@require_workspace_member("agent")
def create_ticket(workspace_id):
    data = request.get_json(silent=True) or {}
    require_fields(data, ["title"])

    title = data["title"].strip()
    if len(title) < 3 or len(title) > 300:
        raise ValidationError("Title must be 3-300 characters.")

    description = (data.get("description") or "").strip() or None
    priority = data.get("priority", "medium")
    if priority not in Ticket.PRIORITIES:
        raise ValidationError(f"Invalid priority. Allowed: {Ticket.PRIORITIES}")
    ttype = data.get("type", "question")
    if ttype not in Ticket.TYPES:
        raise ValidationError(f"Invalid type. Allowed: {Ticket.TYPES}")
    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip()[:50] for t in tags if str(t).strip()][:10]

    assignee_id = None
    if data.get("assignee_id"):
        try:
            assignee_id = uuid.UUID(data["assignee_id"])
            # verify membership
            from app.models.workspace import Membership
            if not Membership.query.filter_by(
                workspace_id=g.workspace.id, user_id=assignee_id, is_active=True
            ).first():
                raise ValidationError("Assignee is not a member of this workspace.")
        except ValueError:
            raise ValidationError("Invalid assignee_id.")

    client_id = data.get("client_id")  # for offline idempotency
    if client_id:
        existing = Ticket.query.filter_by(workspace_id=g.workspace.id, client_id=client_id).first()
        if existing:
            return success_response(existing.to_dict(), message="Ticket already exists (idempotent).")

    number = _next_ticket_number(g.workspace.id)
    ticket = Ticket(
        workspace_id=g.workspace.id,
        number=number,
        title=title,
        description=description,
        priority=priority,
        type=ttype,
        tags=tags,
        created_by_id=g.current_user.id,
        assignee_id=assignee_id,
        client_id=client_id,
        status="open",
    )
    db.session.add(ticket)
    db.session.flush()

    _log_activity(ticket, "created", {"title": title})
    if assignee_id:
        _log_activity(ticket, "assigned", {"assignee_id": str(assignee_id)})
        _notify(
            assignee_id, g.workspace.id, ticket.id, "assigned",
            f"Ticket #{number} assigned to you",
            title,
            {"ticket_number": number},
        )
        from app.tasks.notifications import send_ticket_assigned_notification
        send_ticket_assigned_notification.delay(str(ticket.id), str(assignee_id))

    db.session.commit()
    logger.info("ticket_created", ticket_id=str(ticket.id), number=number, workspace=str(g.workspace.id))
    return success_response(ticket.to_dict(), message="Ticket created.", status=201)


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>", methods=["GET"])
@require_workspace_member("viewer")
def get_ticket(workspace_id, ticket_id):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise NotFoundError("Ticket not found.")

    ticket = Ticket.query.filter_by(id=tid, workspace_id=g.workspace.id).first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    return success_response(ticket.to_dict(
        include_comments=True,
        include_activities=True,
        include_internal_notes=g.membership.has_permission("agent"),
    ))


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>", methods=["PATCH"])
@require_workspace_member("agent")
def update_ticket(workspace_id, ticket_id):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise NotFoundError("Ticket not found.")

    ticket = Ticket.query.filter_by(id=tid, workspace_id=g.workspace.id).first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    data = request.get_json(silent=True) or {}
    changed = {}

    if "title" in data:
        title = data["title"].strip()
        if len(title) < 3 or len(title) > 300:
            raise ValidationError("Title must be 3-300 characters.")
        if title != ticket.title:
            changed["title"] = {"from": ticket.title, "to": title}
            ticket.title = title

    if "description" in data:
        desc = (data["description"] or "").strip() or None
        if desc != ticket.description:
            ticket.description = desc
            changed["description"] = True

    if "status" in data:
        status = data["status"]
        if status not in Ticket.STATUSES:
            raise ValidationError(f"Invalid status. Allowed: {Ticket.STATUSES}")
        if status != ticket.status:
            old = ticket.status
            ticket.status = status
            changed["status"] = {"from": old, "to": status}
            if status == "resolved" and not ticket.resolved_at:
                ticket.resolved_at = datetime.now(timezone.utc)
            if status == "closed" and not ticket.closed_at:
                ticket.closed_at = datetime.now(timezone.utc)
            _log_activity(ticket, "status_changed", {"from": old, "to": status})
            if ticket.assignee_id:
                _notify(
                    ticket.assignee_id, g.workspace.id, ticket.id, "status_change",
                    f"Ticket #{ticket.number} status changed to {status}",
                    data={"from": old, "to": status},
                )

    if "priority" in data:
        priority = data["priority"]
        if priority not in Ticket.PRIORITIES:
            raise ValidationError(f"Invalid priority.")
        if priority != ticket.priority:
            old = ticket.priority
            ticket.priority = priority
            changed["priority"] = {"from": old, "to": priority}
            _log_activity(ticket, "priority_changed", {"from": old, "to": priority})

    if "assignee_id" in data:
        new_assignee = data["assignee_id"]
        if new_assignee is None:
            if ticket.assignee_id:
                old = str(ticket.assignee_id)
                ticket.assignee_id = None
                changed["assignee_id"] = {"from": old, "to": None}
                _log_activity(ticket, "unassigned", {"previous": old})
        else:
            try:
                aid = uuid.UUID(new_assignee)
            except ValueError:
                raise ValidationError("Invalid assignee_id.")
            from app.models.workspace import Membership
            if not Membership.query.filter_by(workspace_id=g.workspace.id, user_id=aid, is_active=True).first():
                raise ValidationError("Assignee is not a member of this workspace.")
            if ticket.assignee_id != aid:
                old = str(ticket.assignee_id) if ticket.assignee_id else None
                ticket.assignee_id = aid
                changed["assignee_id"] = {"from": old, "to": str(aid)}
                _log_activity(ticket, "assigned", {"assignee_id": str(aid)})
                _notify(
                    aid, g.workspace.id, ticket.id, "assigned",
                    f"Ticket #{ticket.number} assigned to you",
                    ticket.title,
                    {"ticket_number": ticket.number},
                )
                from app.tasks.notifications import send_ticket_assigned_notification
                send_ticket_assigned_notification.delay(str(ticket.id), str(aid))

    if "tags" in data and isinstance(data["tags"], list):
        tags = [str(t).strip()[:50] for t in data["tags"] if str(t).strip()][:10]
        ticket.tags = tags
        changed["tags"] = tags

    if "due_at" in data:
        ticket.due_at = data["due_at"]  # assume ISO or null; production would parse carefully

    if not changed:
        return success_response(ticket.to_dict(), message="No changes.")

    ticket.version += 1
    db.session.commit()
    return success_response(ticket.to_dict(), message="Ticket updated.")


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>/comments", methods=["POST"])
@require_workspace_member("agent")
def add_comment(workspace_id, ticket_id):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise NotFoundError("Ticket not found.")

    ticket = Ticket.query.filter_by(id=tid, workspace_id=g.workspace.id).first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    data = request.get_json(silent=True) or {}
    require_fields(data, ["body"])
    body = data["body"].strip()
    if not body or len(body) > 10000:
        raise ValidationError("Comment body must be 1-10000 characters.")

    is_internal = bool(data.get("is_internal", False))
    if is_internal and not g.membership.has_permission("agent"):
        raise AuthorizationError("Only agents can add internal notes.")

    client_id = data.get("client_id")
    if client_id:
        existing = Comment.query.filter_by(ticket_id=ticket.id, client_id=client_id).first()
        if existing:
            return success_response(existing.to_dict(), message="Comment already exists (idempotent).")

    comment = Comment(
        ticket_id=ticket.id,
        author_id=g.current_user.id,
        body=body,
        is_internal=is_internal,
        client_id=client_id,
    )
    db.session.add(comment)
    db.session.flush()

    action = "internal_note" if is_internal else "commented"
    _log_activity(ticket, action, {"comment_id": str(comment.id)})

    if not ticket.first_response_at and not is_internal and ticket.created_by_id != g.current_user.id:
        ticket.first_response_at = datetime.now(timezone.utc)

    # Notify
    notify_ids = set()
    if ticket.assignee_id:
        notify_ids.add(ticket.assignee_id)
    if ticket.created_by_id:
        notify_ids.add(ticket.created_by_id)
    for uid in notify_ids:
        if uid != g.current_user.id:
            _notify(
                uid, g.workspace.id, ticket.id, "reply",
                f"New {'note' if is_internal else 'reply'} on #{ticket.number}",
                body[:200],
                {"comment_id": str(comment.id), "is_internal": is_internal},
            )

    ticket.version += 1
    ticket.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    from app.tasks.notifications import send_ticket_reply_notification
    send_ticket_reply_notification.delay(str(ticket.id), str(comment.id))

    return success_response(comment.to_dict(), message="Comment added.", status=201)


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>/comments", methods=["GET"])
@require_workspace_member("viewer")
def list_comments(workspace_id, ticket_id):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise NotFoundError("Ticket not found.")

    ticket = Ticket.query.filter_by(id=tid, workspace_id=g.workspace.id).first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    include_internal = g.membership.has_permission("agent")
    q = Comment.query.filter_by(ticket_id=ticket.id)
    if not include_internal:
        q = q.filter_by(is_internal=False)
    comments = q.order_by(Comment.created_at.asc()).all()
    return success_response([c.to_dict() for c in comments])


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>/attachments", methods=["POST"])
@require_workspace_member("agent")
def upload_attachment(workspace_id, ticket_id):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise NotFoundError("Ticket not found.")
    ticket = Ticket.query.filter_by(id=tid, workspace_id=g.workspace.id).first()
    if not ticket:
        raise NotFoundError("Ticket not found.")
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        raise ValidationError("A file is required.")
    original = secure_filename(uploaded.filename)
    if not original:
        raise ValidationError("Invalid filename.")
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in current_app.config["ALLOWED_EXTENSIONS"]:
        raise ValidationError("File type is not allowed.")

    content = uploaded.read()
    if not content:
        raise ValidationError("The uploaded file is empty.")
    file_id = uuid.uuid4()
    stored_name = f"{file_id}.{extension}"
    relative_path = f"{ticket.workspace_id}/{ticket.id}"
    _save_attachment(relative_path, stored_name, content, uploaded.content_type or "application/octet-stream")
    attachment = Attachment(
        id=file_id,
        ticket_id=ticket.id,
        uploaded_by_id=g.current_user.id,
        filename=stored_name,
        original_filename=original,
        content_type=uploaded.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=relative_path,
        checksum=hashlib.sha256(content).hexdigest(),
        is_processed=True,
    )
    db.session.add(attachment)
    db.session.commit()
    return success_response(attachment.to_dict(), message="Attachment uploaded.", status=201)


@api_v1_bp.route("/workspaces/<workspace_id>/tickets/<ticket_id>/attachments/<attachment_id>", methods=["GET"])
@require_workspace_member("viewer")
def download_attachment(workspace_id, ticket_id, attachment_id):
    try:
        tid = uuid.UUID(ticket_id)
        aid = uuid.UUID(attachment_id)
    except ValueError:
        raise NotFoundError("Attachment not found.")
    attachment = (
        Attachment.query.join(Ticket)
        .filter(Attachment.id == aid, Attachment.ticket_id == tid, Ticket.workspace_id == g.workspace.id)
        .first()
    )
    if not attachment:
        raise NotFoundError("Attachment not found.")
    return send_file(
        io.BytesIO(_read_attachment(attachment.storage_path, attachment.filename)),
        as_attachment=True,
        download_name=attachment.original_filename,
        mimetype=attachment.content_type,
    )


@api_v1_bp.route("/workspaces/<workspace_id>/stats", methods=["GET"])
@require_workspace_member("viewer")
def workspace_stats(workspace_id):
    ws_id = g.workspace.id
    base = Ticket.query.filter_by(workspace_id=ws_id)

    total = base.count()
    by_status = dict(
        db.session.query(Ticket.status, func.count(Ticket.id))
        .filter(Ticket.workspace_id == ws_id)
        .group_by(Ticket.status)
        .all()
    )
    by_priority = dict(
        db.session.query(Ticket.priority, func.count(Ticket.id))
        .filter(Ticket.workspace_id == ws_id)
        .group_by(Ticket.priority)
        .all()
    )
    open_count = by_status.get("open", 0) + by_status.get("in_progress", 0) + by_status.get("pending", 0)
    my_open = base.filter(
        Ticket.assignee_id == g.current_user.id,
        Ticket.status.in_(["open", "in_progress", "pending"]),
    ).count()
    unassigned = base.filter(
        Ticket.assignee_id.is_(None),
        Ticket.status.in_(["open", "in_progress", "pending"]),
    ).count()

    return success_response({
        "total": total,
        "open": open_count,
        "my_open": my_open,
        "unassigned": unassigned,
        "by_status": by_status,
        "by_priority": by_priority,
    })
