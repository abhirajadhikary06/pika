"""Ticket, Comment, Attachment, Activity models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app import db


class Ticket(db.Model):
    __tablename__ = "tickets"
    __table_args__ = (
        db.Index("ix_tickets_workspace_status", "workspace_id", "status"),
        db.Index("ix_tickets_workspace_priority", "workspace_id", "priority"),
        db.Index("ix_tickets_assignee", "assignee_id"),
        db.Index("ix_tickets_created_at", "created_at"),
        db.Index("ix_tickets_number", "workspace_id", "number", unique=True),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # sequential per workspace
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="open")  # open, in_progress, pending, resolved, closed
    priority = db.Column(db.String(20), nullable=False, default="medium")  # low, medium, high, urgent
    type = db.Column(db.String(30), nullable=False, default="question")  # question, incident, problem, task
    tags = db.Column(ARRAY(db.String(50)), default=list, nullable=False)
    created_by_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignee_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    first_response_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Offline / sync support
    client_id = db.Column(db.String(64), nullable=True, index=True)  # client-generated idempotency
    version = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    workspace = db.relationship("Workspace", back_populates="tickets")
    created_by = db.relationship("User", foreign_keys=[created_by_id], back_populates="created_tickets")
    assignee = db.relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tickets")
    comments = db.relationship("Comment", back_populates="ticket", cascade="all, delete-orphan", lazy="dynamic", order_by="Comment.created_at")
    attachments = db.relationship("Attachment", back_populates="ticket", cascade="all, delete-orphan", lazy="dynamic")
    activities = db.relationship("Activity", back_populates="ticket", cascade="all, delete-orphan", lazy="dynamic", order_by="Activity.created_at.desc()")

    STATUSES = ("open", "in_progress", "pending", "resolved", "closed")
    PRIORITIES = ("low", "medium", "high", "urgent")
    TYPES = ("question", "incident", "problem", "task")

    def to_dict(
        self,
        include_comments: bool = False,
        include_activities: bool = False,
        include_internal_notes: bool = False,
    ) -> dict:
        data = {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "number": self.number,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "type": self.type,
            "tags": self.tags or [],
            "created_by_id": str(self.created_by_id) if self.created_by_id else None,
            "assignee_id": str(self.assignee_id) if self.assignee_id else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "first_response_at": self.first_response_at.isoformat() if self.first_response_at else None,
            "client_id": self.client_id,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by.to_dict(include_email=False) if self.created_by else None,
            "assignee": self.assignee.to_dict(include_email=False) if self.assignee else None,
        }
        if include_comments:
            data["comments"] = [c.to_dict() for c in self.comments.filter_by(is_internal=False).all()]
            if include_internal_notes:
                data["internal_notes"] = [c.to_dict() for c in self.comments.filter_by(is_internal=True).all()]
        data["attachments"] = [a.to_dict() for a in self.attachments.all()]
        if include_activities:
            data["activities"] = [a.to_dict() for a in self.activities.limit(50).all()]
        return data

    def __repr__(self) -> str:
        return f"<Ticket #{self.number} {self.title[:30]}>"


class Comment(db.Model):
    __tablename__ = "comments"
    __table_args__ = (
        db.Index("ix_comments_ticket_created", "ticket_id", "created_at"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    author_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)  # internal note vs public reply
    client_id = db.Column(db.String(64), nullable=True, index=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ticket = db.relationship("Ticket", back_populates="comments")
    author = db.relationship("User", back_populates="comments")
    attachments = db.relationship("Attachment", back_populates="comment", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id),
            "author_id": str(self.author_id) if self.author_id else None,
            "body": self.body,
            "is_internal": self.is_internal,
            "client_id": self.client_id,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "author": self.author.to_dict(include_email=False) if self.author else None,
            "attachments": [a.to_dict() for a in self.attachments.all()],
        }

    def __repr__(self) -> str:
        return f"<Comment {self.id} on {self.ticket_id}>"


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    comment_id = db.Column(UUID(as_uuid=True), db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    uploaded_by_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    checksum = db.Column(db.String(64), nullable=True)
    is_processed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    ticket = db.relationship("Ticket", back_populates="attachments")
    comment = db.relationship("Comment", back_populates="attachments")
    uploaded_by = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "ticket_id": str(self.ticket_id),
            "comment_id": str(self.comment_id) if self.comment_id else None,
            "uploaded_by_id": str(self.uploaded_by_id) if self.uploaded_by_id else None,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "is_processed": self.is_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Attachment {self.original_filename}>"


class Activity(db.Model):
    __tablename__ = "activities"
    __table_args__ = (
        db.Index("ix_activities_ticket_created", "ticket_id", "created_at"),
        db.Index("ix_activities_workspace", "workspace_id"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    ticket_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    actor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # created, status_changed, assigned, commented, etc.
    details = db.Column(db.JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    ticket = db.relationship("Ticket", back_populates="activities")
    actor = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "ticket_id": str(self.ticket_id),
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "action": self.action,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "actor": self.actor.to_dict(include_email=False) if self.actor else None,
        }

    def __repr__(self) -> str:
        return f"<Activity {self.action} on {self.ticket_id}>"


class SyncOperation(db.Model):
    __tablename__ = "sync_operations"
    __table_args__ = (db.UniqueConstraint("user_id", "op_id", name="uq_sync_operations_user_op"),)

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    op_id = db.Column(UUID(as_uuid=True), nullable=False)
    payload_hash = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class SyncChange(db.Model):
    """Ordered workspace change feed; deletion rows are retained as tombstones.

    Do not purge these rows until expired cursors trigger a full client resync.
    Keeping tombstones indefinitely is the safe cleanup policy for this release.
    """
    __tablename__ = "sync_changes"

    cursor = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(UUID(as_uuid=True), nullable=False)
    operation = db.Column(db.String(20), nullable=False, default="upsert")
    version = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
