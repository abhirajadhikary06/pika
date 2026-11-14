"""Add idempotent sync operation ledger and workspace change cursor."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261114_sync"
down_revision = "1bbe939deb99"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sync_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("op_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "op_id", name="uq_sync_operations_user_op"),
    )
    op.create_index("ix_sync_operations_user_id", "sync_operations", ["user_id"])
    op.create_index("ix_sync_operations_workspace_id", "sync_operations", ["workspace_id"])
    op.create_table(
        "sync_changes",
        sa.Column("cursor", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("cursor"),
    )
    op.create_index("ix_sync_changes_workspace_id", "sync_changes", ["workspace_id"])


def downgrade():
    op.drop_table("sync_changes")
    op.drop_table("sync_operations")
