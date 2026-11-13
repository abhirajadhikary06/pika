"""Refresh token model for revocation support."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app import db


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        db.Index("ix_refresh_tokens_jti", "jti"),
        db.Index("ix_refresh_tokens_user", "user_id"),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti = db.Column(db.String(64), unique=True, nullable=False)  # JWT ID
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="refresh_tokens")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def revoke(self) -> None:
        self.revoked_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "jti": self.jti,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<RefreshToken {self.jti[:8]}...>"
