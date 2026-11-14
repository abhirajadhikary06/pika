"""Versioned, idempotent API used by offline clients."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from flask import g, request

from app import db
from app.api.v1 import api_v1_bp
from app.models.ticket import Activity, Comment, SyncChange, SyncOperation, Ticket
from app.models.workspace import Workspace
from app.utils.auth import require_workspace_member
from app.utils.errors import ValidationError, NotFoundError
from app.utils.validators import success_response


def _change(workspace_id, entity_type, entity_id, version, payload=None, operation="upsert"):
    # Serialize writes per workspace so allocated cursors follow commit order.
    Workspace.query.filter_by(id=workspace_id).with_for_update().first()
    db.session.add(SyncChange(
        workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id,
        operation=operation, version=version, payload=payload,
    ))


@api_v1_bp.route("/workspaces/<workspace_id>/sync/push", methods=["POST"])
@require_workspace_member("agent")
def push_sync_operations(workspace_id):
    body = request.get_json(silent=True) or {}
    operations = body.get("operations")
    if not isinstance(operations, list) or len(operations) > 100:
        raise ValidationError("operations must be a list of at most 100 items.")

    results = []
    for item in operations:
        try:
            op_id = uuid.UUID(item["op_id"])
            payload = item.get("payload") or {}
            digest = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            Workspace.query.filter_by(id=g.workspace.id).with_for_update().first()
            prior = SyncOperation.query.filter_by(user_id=g.current_user.id, op_id=op_id).first()
            if prior:
                if prior.workspace_id != g.workspace.id or prior.payload_hash != digest:
                    results.append({"op_id": str(op_id), "status": "failed", "error": "Operation ID was reused with different data."})
                else:
                    results.append({"op_id": str(op_id), "status": "synced", "result": prior.result})
                continue

            kind = item.get("record_type")
            action = item.get("operation")
            if kind == "ticket" and action == "create":
                client_record_id = uuid.UUID(str(payload.get("id")))
                existing = Ticket.query.filter_by(workspace_id=g.workspace.id, client_id=str(op_id)).first()
                ticket = existing
                if ticket is None:
                    title = (payload.get("title") or "").strip()
                    if not 3 <= len(title) <= 300:
                        raise ValidationError("Title must be 3-300 characters.")
                    priority = payload.get("priority", "medium")
                    ticket_type = payload.get("type", "question")
                    if priority not in Ticket.PRIORITIES or ticket_type not in Ticket.TYPES:
                        raise ValidationError("Invalid ticket priority or type.")
                    tags = payload.get("tags") or []
                    if not isinstance(tags, list):
                        raise ValidationError("Ticket tags must be a list.")
                    Workspace.query.filter_by(id=g.workspace.id).with_for_update().first()
                    number = db.session.query(db.func.coalesce(db.func.max(Ticket.number), 0)).filter(Ticket.workspace_id == g.workspace.id).scalar() + 1
                    ticket = Ticket(
                        id=client_record_id, workspace_id=g.workspace.id, number=number,
                        title=title, description=payload.get("description") or None,
                        priority=priority, type=ticket_type,
                        tags=[str(tag).strip()[:50] for tag in tags if str(tag).strip()][:10],
                        status="open", created_by_id=g.current_user.id,
                        client_id=str(op_id), version=1,
                    )
                    db.session.add(ticket)
                    db.session.flush()
                    db.session.add(Activity(workspace_id=g.workspace.id, ticket_id=ticket.id,
                                            actor_id=g.current_user.id, action="created",
                                            details={"title": title}))
                    _change(g.workspace.id, "ticket", ticket.id, ticket.version, ticket.to_dict())
                result = ticket.to_dict()
            elif kind == "comment" and action == "create":
                ticket_id = uuid.UUID(str(payload.get("ticket_id")))
                ticket = Ticket.query.filter_by(id=ticket_id, workspace_id=g.workspace.id).with_for_update().first()
                if not ticket:
                    raise NotFoundError("Ticket not found.")
                text = (payload.get("body") or "").strip()
                if not text or len(text) > 10000:
                    raise ValidationError("Comment body must be 1-10000 characters.")
                internal = bool(payload.get("is_internal", False))
                if internal and not g.membership.has_permission("agent"):
                    raise ValidationError("Only agents can add internal notes.")
                comment_id = uuid.UUID(str(payload.get("id")))
                comment = Comment(
                    id=comment_id, ticket_id=ticket.id, author_id=g.current_user.id,
                    body=text, is_internal=internal, client_id=str(op_id), version=1,
                )
                db.session.add(comment)
                db.session.flush()
                ticket.version += 1
                ticket.updated_at = datetime.now(timezone.utc)
                if not ticket.first_response_at and not internal and ticket.created_by_id != g.current_user.id:
                    ticket.first_response_at = datetime.now(timezone.utc)
                db.session.add(Activity(workspace_id=g.workspace.id, ticket_id=ticket.id,
                                        actor_id=g.current_user.id,
                                        action="internal_note" if internal else "commented",
                                        details={"comment_id": str(comment.id)}))
                _change(g.workspace.id, "comment", comment.id, comment.version,
                        {**comment.to_dict(), "is_internal": internal})
                _change(g.workspace.id, "ticket", ticket.id, ticket.version, ticket.to_dict())
                result = comment.to_dict()
            elif kind == "ticket" and action == "update":
                ticket_id = uuid.UUID(str(payload.get("id")))
                ticket = Ticket.query.filter_by(id=ticket_id, workspace_id=g.workspace.id).with_for_update().first()
                if not ticket:
                    raise NotFoundError("Ticket not found.")
                base_version = int(item.get("base_version", 0))
                if ticket.version != base_version:
                    results.append({"op_id": str(op_id), "status": "conflict", "base_version": base_version,
                                    "server": ticket.to_dict(), "local": payload.get("changes", {})})
                    continue
                changes = payload.get("changes") or {}
                previous_values = {}
                for field, value in changes.items():
                    if field not in {"title", "description", "status", "priority", "type", "tags", "due_at"}:
                        raise ValidationError(f"Field cannot be updated: {field}")
                    if field == "status" and value not in Ticket.STATUSES:
                        raise ValidationError("Invalid ticket status.")
                    if field == "priority" and value not in Ticket.PRIORITIES:
                        raise ValidationError("Invalid ticket priority.")
                    if field == "type" and value not in Ticket.TYPES:
                        raise ValidationError("Invalid ticket type.")
                    previous_values[field] = getattr(ticket, field)
                    setattr(ticket, field, value)
                ticket.version += 1
                ticket.updated_at = datetime.now(timezone.utc)
                db.session.add(Activity(workspace_id=g.workspace.id, ticket_id=ticket.id,
                                        actor_id=g.current_user.id, action="updated",
                                        details={"changes": {field: {"from": old, "to": changes[field]}
                                                              for field, old in previous_values.items()}}))
                result = ticket.to_dict()
                _change(g.workspace.id, "ticket", ticket.id, ticket.version, result)
            elif kind == "ticket" and action == "delete":
                ticket_id = uuid.UUID(str(payload.get("id")))
                ticket = Ticket.query.filter_by(id=ticket_id, workspace_id=g.workspace.id).with_for_update().first()
                if not ticket:
                    result = {"id": str(ticket_id), "deleted": True}
                else:
                    base_version = int(item.get("base_version", 0))
                    if ticket.version != base_version:
                        results.append({"op_id": str(op_id), "status": "conflict", "base_version": base_version,
                                        "server": ticket.to_dict(), "local": {"deleted": True}})
                        continue
                    _change(g.workspace.id, "ticket", ticket.id, ticket.version + 1, operation="delete")
                    result = {"id": str(ticket.id), "deleted": True}
                    db.session.delete(ticket)
            else:
                raise ValidationError("Unsupported sync operation.")

            db.session.add(SyncOperation(
                user_id=g.current_user.id, workspace_id=g.workspace.id, op_id=op_id,
                payload_hash=digest, result=result,
            ))
            results.append({"op_id": str(op_id), "status": "synced", "result": result})
        except (KeyError, TypeError, ValueError) as error:
            results.append({"op_id": item.get("op_id"), "status": "failed", "error": str(error)})

    db.session.commit()
    return success_response({"results": results})


@api_v1_bp.route("/workspaces/<workspace_id>/sync/pull", methods=["GET"])
@require_workspace_member("viewer")
def pull_sync_changes(workspace_id):
    try:
        cursor = max(0, int(request.args.get("cursor", "0")))
        limit = min(500, max(1, int(request.args.get("limit", "100"))))
    except ValueError:
        raise ValidationError("cursor and limit must be integers.")
    rows = SyncChange.query.filter(
        SyncChange.workspace_id == g.workspace.id,
        SyncChange.cursor > cursor,
    ).order_by(SyncChange.cursor.asc()).limit(limit).all()
    can_see_internal = g.membership.has_permission("agent")
    changes = []
    for row in rows:
        if row.entity_type == "comment" and row.payload and row.payload.get("is_internal") and not can_see_internal:
            continue
        changes.append({"cursor": row.cursor, "entity_type": row.entity_type,
                        "entity_id": str(row.entity_id), "operation": row.operation,
                        "version": row.version, "payload": row.payload})
    next_cursor = rows[-1].cursor if rows else cursor
    return success_response({"changes": changes, "cursor": next_cursor, "has_more": len(rows) == limit})
