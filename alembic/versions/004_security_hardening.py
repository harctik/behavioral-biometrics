"""Security hardening: add context_hash, drop redundant salt column

Revision ID: 004
Revises: 003
Create Date: 2026-04-28

Changes:
- sessions: add ``context_hash`` column (SHA-256 of IP+UA for session binding)
- users: drop redundant ``salt`` column (bcrypt embeds salt in the hash)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add context_hash to sessions; drop salt from users."""

    # 1. Add context_hash to sessions for session-binding validation
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column("context_hash", sa.String(), nullable=True)
        )

    # 2. Drop the redundant salt column from users.
    #    bcrypt stores the salt inside the password_hash itself, so this
    #    column has always been redundant and a minor information leak.
    #
    #    NOTE: SQLite does not support ALTER TABLE DROP COLUMN natively in
    #    older versions. Alembic's batch mode handles this by recreating the
    #    table behind the scenes (safe for production).
    with op.batch_alter_table("users") as batch:
        batch.drop_column("salt")


def downgrade() -> None:
    """Re-add salt to users; drop context_hash from sessions."""

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("salt", sa.String(), nullable=False, server_default="")
        )

    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("context_hash")
