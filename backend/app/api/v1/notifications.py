"""Notification endpoints."""
from datetime import datetime, timezone
from flask import request, g
from app import db
from app.api.v1 import api_v1_bp
from app.models.notification import Notification
from app.utils.auth import require_auth
from app.utils.errors import NotFoundError
from app.utils.validators import paginate_params, success_response
import uuid


@api_v1_bp.route("/notifications", methods=["GET"])
@require_auth
def list_notifications():
    page, per_page = paginate_params(request.args)
    unread_only = request.args.get("unread") == "true"

    q = Notification.query.filter_by(user_id=g.current_user.id)
    if unread_only:
        q = q.filter_by(is_read=False)

    total = q.count()
    notifications = (
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    unread_count = Notification.query.filter_by(user_id=g.current_user.id, is_read=False).count()

    return success_response(
        [n.to_dict() for n in notifications],
        meta={"page": page, "per_page": per_page, "total": total, "unread_count": unread_count},
    )


@api_v1_bp.route("/notifications/<notification_id>/read", methods=["POST"])
@require_auth
def mark_read(notification_id):
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise NotFoundError("Notification not found.")

    n = Notification.query.filter_by(id=nid, user_id=g.current_user.id).first()
    if not n:
        raise NotFoundError("Notification not found.")

    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.session.commit()

    return success_response(n.to_dict(), message="Marked as read.")


@api_v1_bp.route("/notifications/read-all", methods=["POST"])
@require_auth
def mark_all_read():
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update(
        {"is_read": True, "read_at": datetime.now(timezone.utc)}
    )
    db.session.commit()
    return success_response(message="All notifications marked as read.")
