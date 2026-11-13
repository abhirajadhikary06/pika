"""Notification model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app import db


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        db.Index("ix_notifications_user_unread", "user_id", "is_read"),
        db.Index("ix_notifications_created", "created_at"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    ticket_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True)
    type = db.Column(db.String(50), nullable=False)  # assigned, reply, status_change, mention, invitation
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    data = db.Column(db.JSON, default=dict, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "workspace_id": str(self.workspace_id) if self.workspace_id else None,
            "ticket_id": str(self.ticket_id) if self.ticket_id else None,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "data": self.data or {},
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Notification {self.type} for {self.user_id}>"
