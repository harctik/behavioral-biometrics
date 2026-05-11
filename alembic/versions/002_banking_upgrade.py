"""Banking upgrade schema

Revision ID: 002
Revises: 001
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(), server_default="user"))

    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("device_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("assurance_level", sa.String(), server_default="pwd"))

    op.create_table(
        "audit_evidence",
        sa.Column("evidence_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("metadata", sa.String(), nullable=True),
        sa.Column("retention_tag", sa.String(), server_default="standard", nullable=False),
        sa.Column("prev_hash", sa.String(), nullable=True),
        sa.Column("entry_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("idx_audit_evidence_user_id", "audit_evidence", ["user_id"])
    op.create_index("idx_audit_evidence_created_at", "audit_evidence", ["created_at"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("token_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_index("idx_password_reset_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "idx_password_reset_token_hash", "password_reset_tokens", ["token_hash"]
    )


def downgrade() -> None:
    op.drop_index("idx_password_reset_token_hash", table_name="password_reset_tokens")
    op.drop_index("idx_password_reset_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_index("idx_audit_evidence_created_at", table_name="audit_evidence")
    op.drop_index("idx_audit_evidence_user_id", table_name="audit_evidence")
    op.drop_table("audit_evidence")

    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("assurance_level")
        batch.drop_column("device_id")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("role")

