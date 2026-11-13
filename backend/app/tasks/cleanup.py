"""Periodic cleanup tasks."""
from datetime import datetime, timezone, timedelta
from app import celery, db
from app.models.token import RefreshToken
from app.models.workspace import Invitation
import structlog

logger = structlog.get_logger()


@celery.task(name="tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Remove expired or long-revoked refresh tokens."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    deleted = (
        RefreshToken.query
        .filter(
            (RefreshToken.expires_at < datetime.now(timezone.utc)) |
            ((RefreshToken.revoked_at.isnot(None)) & (RefreshToken.revoked_at < cutoff))
        )
        .delete(synchronize_session=False)
    )
    db.session.commit()
    logger.info("cleanup_expired_tokens", deleted=deleted)
    return {"deleted": deleted}


@celery.task(name="tasks.expire_old_invitations")
def expire_old_invitations():
    """Mark past-due pending invitations as expired."""
    now = datetime.now(timezone.utc)
    updated = (
        Invitation.query
        .filter(Invitation.status == "pending", Invitation.expires_at < now)
        .update({"status": "expired"}, synchronize_session=False)
    )
    db.session.commit()
    logger.info("expire_old_invitations", updated=updated)
    return {"updated": updated}
