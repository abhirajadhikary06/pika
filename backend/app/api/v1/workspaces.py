"""Workspace and membership endpoints."""
import secrets
from datetime import datetime, timezone, timedelta
from flask import request, g
from app import db
from app.api.v1 import api_v1_bp
from app.models.workspace import Workspace, Membership, Invitation
from app.models.user import User
from app.models.notification import Notification
from app.utils.auth import require_auth, require_workspace_member
from app.utils.errors import ValidationError, NotFoundError, ConflictError, AuthorizationError
from app.utils.validators import require_fields, validate_slug, validate_email, paginate_params, success_response
import uuid
import structlog

logger = structlog.get_logger()


def _generate_slug(name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    base = "-".join(filter(None, base.split("-")))[:80]
    if not base:
        base = "workspace"
    candidate = base
    i = 1
    while Workspace.query.filter_by(slug=candidate).first():
        candidate = f"{base}-{i}"
        i += 1
    return candidate


@api_v1_bp.route("/workspaces", methods=["GET"])
@require_auth
def list_workspaces():
    memberships = (
        Membership.query
        .filter_by(user_id=g.current_user.id, is_active=True)
        .join(Workspace)
        .filter(Workspace.is_active == True)
        .all()
    )
    data = []
    for m in memberships:
        ws = m.workspace.to_dict()
        ws["role"] = m.role
        data.append(ws)
    return success_response(data)


@api_v1_bp.route("/workspaces", methods=["POST"])
@require_auth
def create_workspace():
    data = request.get_json(silent=True) or {}
    require_fields(data, ["name"])
    name = data["name"].strip()
    if len(name) < 2 or len(name) > 150:
        raise ValidationError("Name must be 2-150 characters.")

    slug = data.get("slug")
    if slug:
        slug = validate_slug(slug)
        if Workspace.query.filter_by(slug=slug).first():
            raise ConflictError("Slug already taken.")
    else:
        slug = _generate_slug(name)

    description = (data.get("description") or "").strip() or None

    workspace = Workspace(
        name=name,
        slug=slug,
        description=description,
        owner_id=g.current_user.id,
    )
    db.session.add(workspace)
    db.session.flush()

    membership = Membership(
        workspace_id=workspace.id,
        user_id=g.current_user.id,
        role="owner",
    )
    db.session.add(membership)
    db.session.commit()

    logger.info("workspace_created", workspace_id=str(workspace.id), owner=str(g.current_user.id))
    result = workspace.to_dict()
    result["role"] = "owner"
    return success_response(result, message="Workspace created.", status=201)


@api_v1_bp.route("/workspaces/<workspace_id>", methods=["GET"])
@require_workspace_member("viewer")
def get_workspace(workspace_id):
    ws = g.workspace.to_dict(include_owner=True)
    ws["role"] = g.membership.role
    return success_response(ws)


@api_v1_bp.route("/workspaces/<workspace_id>", methods=["PATCH"])
@require_workspace_member("admin")
def update_workspace(workspace_id):
    data = request.get_json(silent=True) or {}
    ws = g.workspace

    if "name" in data:
        name = data["name"].strip()
        if len(name) < 2 or len(name) > 150:
            raise ValidationError("Name must be 2-150 characters.")
        ws.name = name
        ws.version += 1

    if "description" in data:
        ws.description = (data["description"] or "").strip() or None
        ws.version += 1

    if "settings" in data and isinstance(data["settings"], dict):
        current = ws.settings or {}
        current.update(data["settings"])
        ws.settings = current
        ws.version += 1

    db.session.commit()
    return success_response(ws.to_dict(), message="Workspace updated.")


@api_v1_bp.route("/workspaces/<workspace_id>/members", methods=["GET"])
@require_workspace_member("viewer")
def list_members(workspace_id):
    page, per_page = paginate_params(request.args)
    q = Membership.query.filter_by(workspace_id=g.workspace.id, is_active=True)
    total = q.count()
    members = q.order_by(Membership.joined_at).offset((page - 1) * per_page).limit(per_page).all()
    return success_response(
        [m.to_dict(include_user=True) for m in members],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@api_v1_bp.route("/workspaces/<workspace_id>/members/<user_id>", methods=["PATCH"])
@require_workspace_member("admin")
def update_member(workspace_id, user_id):
    data = request.get_json(silent=True) or {}
    if "role" not in data:
        raise ValidationError("Role is required.")
    role = data["role"]
    if role not in Membership.ROLES or role == "owner":
        raise ValidationError("Invalid role.")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("Member not found.")

    membership = Membership.query.filter_by(workspace_id=g.workspace.id, user_id=uid, is_active=True).first()
    if not membership:
        raise NotFoundError("Member not found.")
    if membership.role == "owner":
        raise AuthorizationError("Cannot change the owner's role.")

    # Only owner can promote to admin
    if role == "admin" and g.membership.role != "owner":
        raise AuthorizationError("Only the owner can assign admin role.")

    membership.role = role
    membership.version += 1
    db.session.commit()
    return success_response(membership.to_dict(include_user=True), message="Member updated.")


@api_v1_bp.route("/workspaces/<workspace_id>/members/<user_id>", methods=["DELETE"])
@require_workspace_member("admin")
def remove_member(workspace_id, user_id):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("Member not found.")

    membership = Membership.query.filter_by(workspace_id=g.workspace.id, user_id=uid, is_active=True).first()
    if not membership:
        raise NotFoundError("Member not found.")
    if membership.role == "owner":
        raise AuthorizationError("Cannot remove the owner.")
    if membership.user_id == g.current_user.id:
        raise AuthorizationError("Use leave endpoint to leave the workspace.")

    membership.is_active = False
    membership.version += 1
    db.session.commit()
    return success_response(message="Member removed.")


@api_v1_bp.route("/workspaces/<workspace_id>/invitations", methods=["POST"])
@require_workspace_member("admin")
def create_invitation(workspace_id):
    data = request.get_json(silent=True) or {}
    require_fields(data, ["email"])
    email = validate_email(data["email"])
    role = data.get("role", "agent")
    if role not in ("admin", "agent", "viewer"):
        raise ValidationError("Invalid role for invitation.")

    # Check existing membership
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        existing_mem = Membership.query.filter_by(
            workspace_id=g.workspace.id, user_id=existing_user.id, is_active=True
        ).first()
        if existing_mem:
            raise ConflictError("User is already a member.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    inv = Invitation.query.filter_by(workspace_id=g.workspace.id, email=email).first()
    if inv:
        # The schema permits one invitation record per workspace/email. Reuse it
        # so resending an invite refreshes the token instead of violating the constraint.
        inv.role = role
        inv.token = token
        inv.invited_by_id = g.current_user.id
        inv.status = "pending"
        inv.expires_at = expires_at
        inv.accepted_at = None
    else:
        inv = Invitation(
            workspace_id=g.workspace.id,
            email=email,
            role=role,
            token=token,
            invited_by_id=g.current_user.id,
            expires_at=expires_at,
        )
        db.session.add(inv)
    if existing_user:
        db.session.add(Notification(
            user_id=existing_user.id,
            workspace_id=g.workspace.id,
            type="invitation",
            title=f"Invitation to join {g.workspace.name}",
            body=f"{g.current_user.full_name} invited you to join this workspace.",
            data={"invitation_token": token, "role": role},
        ))
    db.session.commit()

    # In production: enqueue email task
    from app.tasks.notifications import send_invitation_email
    send_invitation_email.delay(str(inv.id))

    logger.info("invitation_created", workspace_id=str(g.workspace.id), email=email)
    return success_response(inv.to_dict(), message="Invitation sent.", status=201)


@api_v1_bp.route("/workspaces/<workspace_id>/invitations", methods=["GET"])
@require_workspace_member("admin")
def list_invitations(workspace_id):
    invs = (
        Invitation.query
        .filter_by(workspace_id=g.workspace.id)
        .filter(Invitation.status.in_(["pending", "accepted"]))
        .order_by(Invitation.created_at.desc())
        .limit(50)
        .all()
    )
    return success_response([i.to_dict() for i in invs])


@api_v1_bp.route("/invitations/<token>/accept", methods=["POST"])
@require_auth
def accept_invitation(token):
    inv = Invitation.query.filter_by(token=token, status="pending").first()
    if not inv:
        raise NotFoundError("Invitation not found or already used.")
    if inv.expires_at < datetime.now(timezone.utc):
        inv.status = "expired"
        db.session.commit()
        raise ValidationError("Invitation has expired.")

    if inv.email != g.current_user.email:
        raise AuthorizationError("This invitation is for a different email address.")

    existing = Membership.query.filter_by(
        workspace_id=inv.workspace_id, user_id=g.current_user.id
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.role = inv.role
            existing.version += 1
        else:
            raise ConflictError("You are already a member.")
    else:
        membership = Membership(
            workspace_id=inv.workspace_id,
            user_id=g.current_user.id,
            role=inv.role,
        )
        db.session.add(membership)

    inv.status = "accepted"
    inv.accepted_at = datetime.now(timezone.utc)
    db.session.commit()

    return success_response(
        {"workspace_id": str(inv.workspace_id), "role": inv.role},
        message="Invitation accepted.",
    )
