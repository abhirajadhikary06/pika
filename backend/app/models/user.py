"""User model."""
import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID
from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    avatar_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # For offline sync / conflict detection
    version = db.Column(db.Integer, default=1, nullable=False)

    # Relationships
    memberships = db.relationship("Membership", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    owned_workspaces = db.relationship("Workspace", back_populates="owner", lazy="dynamic")
    assigned_tickets = db.relationship(
        "Ticket",
        foreign_keys="Ticket.assignee_id",
        back_populates="assignee",
        lazy="dynamic",
    )
    created_tickets = db.relationship(
        "Ticket",
        foreign_keys="Ticket.created_by_id",
        back_populates="created_by",
        lazy="dynamic",
    )
    comments = db.relationship("Comment", back_populates="author", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    refresh_tokens = db.relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_email: bool = True) -> dict:
        data = {
            "id": str(self.id),
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }
        if include_email:
            data["email"] = self.email
            data["is_verified"] = self.is_verified
            data["last_login_at"] = self.last_login_at.isoformat() if self.last_login_at else None
        return data

    def __repr__(self) -> str:
        return f"<User {self.email}>"
