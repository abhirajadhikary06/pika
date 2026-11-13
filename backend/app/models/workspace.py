"""Workspace, Membership, and Invitation models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app import db


class Workspace(db.Model):
    __tablename__ = "workspaces"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    settings = db.Column(db.JSON, default=dict, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    version = db.Column(db.Integer, default=1, nullable=False)

    owner = db.relationship("User", back_populates="owned_workspaces")
    memberships = db.relationship("Membership", back_populates="workspace", cascade="all, delete-orphan", lazy="dynamic")
    invitations = db.relationship("Invitation", back_populates="workspace", cascade="all, delete-orphan", lazy="dynamic")
    tickets = db.relationship("Ticket", back_populates="workspace", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self, include_owner: bool = False) -> dict:
        data = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "is_active": self.is_active,
            "settings": self.settings or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }
        if include_owner and self.owner:
            data["owner"] = self.owner.to_dict(include_email=False)
        return data

    def __repr__(self) -> str:
        return f"<Workspace {self.slug}>"


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),
        db.Index("ix_memberships_user_workspace", "user_id", "workspace_id"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="agent")  # owner, admin, agent, viewer
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    joined_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    version = db.Column(db.Integer, default=1, nullable=False)

    workspace = db.relationship("Workspace", back_populates="memberships")
    user = db.relationship("User", back_populates="memberships")

    ROLES = ("owner", "admin", "agent", "viewer")
    ROLE_HIERARCHY = {"owner": 4, "admin": 3, "agent": 2, "viewer": 1}

    def has_permission(self, min_role: str) -> bool:
        return self.ROLE_HIERARCHY.get(self.role, 0) >= self.ROLE_HIERARCHY.get(min_role, 0)

    def to_dict(self, include_user: bool = True, include_workspace: bool = False) -> dict:
        data = {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "user_id": str(self.user_id),
            "role": self.role,
            "is_active": self.is_active,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
        }
        if include_user and self.user:
            data["user"] = self.user.to_dict(include_email=True)
        if include_workspace and self.workspace:
            data["workspace"] = self.workspace.to_dict()
        return data

    def __repr__(self) -> str:
        return f"<Membership {self.user_id}@{self.workspace_id} ({self.role})>"


class Invitation(db.Model):
    __tablename__ = "invitations"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "email", name="uq_invitation_workspace_email"),
        db.Index("ix_invitations_token", "token"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = db.Column(UUID(as_uuid=True), db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="agent")
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    invited_by_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, accepted, expired, revoked
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    workspace = db.relationship("Workspace", back_populates="invitations")
    invited_by = db.relationship("User", foreign_keys=[invited_by_id])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "invited_by_id": str(self.invited_by_id) if self.invited_by_id else None,
        }

    def __repr__(self) -> str:
        return f"<Invitation {self.email} -> {self.workspace_id}>"
