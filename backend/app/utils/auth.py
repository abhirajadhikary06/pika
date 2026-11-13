"""Authentication and authorization helpers."""
from functools import wraps
from flask import g, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app import db
from app.models.user import User
from app.models.workspace import Membership
from app.utils.errors import AuthenticationError, AuthorizationError, NotFoundError
import uuid


def get_current_user() -> User:
    """Load current user from JWT identity. Raises if not found/active."""
    user_id = get_jwt_identity()
    if not user_id:
        raise AuthenticationError("Invalid token identity.")
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid user identity.")
    user = User.query.get(uid)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


def require_auth(fn):
    """Decorator: require valid access token and load user into g.current_user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        g.current_user = get_current_user()
        return fn(*args, **kwargs)
    return wrapper


def require_workspace_member(min_role: str = "viewer"):
    """
    Decorator factory: require membership in the workspace identified by
    workspace_id (from path or query). Sets g.membership and g.workspace.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = get_current_user()
            g.current_user = user

            workspace_id = kwargs.get("workspace_id") or request.view_args.get("workspace_id")
            if not workspace_id:
                # try body/query
                data = request.get_json(silent=True) or {}
                workspace_id = data.get("workspace_id") or request.args.get("workspace_id")

            if not workspace_id:
                raise AuthorizationError("Workspace context is required.")

            try:
                wid = uuid.UUID(str(workspace_id))
            except (ValueError, TypeError):
                raise NotFoundError("Workspace not found.")

            membership = (
                Membership.query
                .filter_by(workspace_id=wid, user_id=user.id, is_active=True)
                .first()
            )
            if not membership:
                raise AuthorizationError("You are not a member of this workspace.")

            if not membership.has_permission(min_role):
                raise AuthorizationError(f"Requires at least '{min_role}' role.")

            g.membership = membership
            g.workspace = membership.workspace
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_membership_or_404(workspace_id, user_id) -> Membership:
    membership = (
        Membership.query
        .filter_by(workspace_id=workspace_id, user_id=user_id, is_active=True)
        .first()
    )
    if not membership:
        raise AuthorizationError("Not a member of this workspace.")
    return membership
