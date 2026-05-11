"""Initial database schema for behavior-based authentication system

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Users table
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("salt", sa.String(), nullable=False),
        sa.Column("mfa_secret", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")
        ),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column(
            "calibration_complete", sa.Boolean(), server_default="0", nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # Sessions table
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")
        ),
        sa.Column(
            "last_activity",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
    )

    # Behavioral data table
    op.create_table(
        "behavioral_data",
        sa.Column("data_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")
        ),
        sa.Column("data_type", sa.String(), nullable=False),
        sa.Column("features", sa.String(), nullable=False),
        sa.Column("raw_data", sa.String(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("data_id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.session_id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
    )

    # Authentication events table
    op.create_table(
        "auth_events",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_data", sa.String(), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")
        ),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.session_id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
    )

    # Model metadata table
    op.create_table(
        "model_metadata",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_trained", sa.DateTime(), nullable=True),
        sa.Column("training_samples", sa.Integer(), server_default="0", nullable=False),
        sa.Column("model_accuracy", sa.Float(), nullable=True),
        sa.Column("drift_detected", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("drift_timestamp", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
    )

    # Create indexes for better query performance
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index(
        "idx_sessions_last_activity", "sessions", ["last_activity"], unique=False
    )
    op.create_index(
        "idx_behavioral_data_user_id", "behavioral_data", ["user_id"], unique=False
    )
    op.create_index(
        "idx_behavioral_data_timestamp", "behavioral_data", ["timestamp"], unique=False
    )
    op.create_index(
        "idx_behavioral_data_type", "behavioral_data", ["data_type"], unique=False
    )
    op.create_index("idx_auth_events_user_id", "auth_events", ["user_id"], unique=False)
    op.create_index(
        "idx_auth_events_timestamp", "auth_events", ["timestamp"], unique=False
    )
    op.create_index("idx_auth_events_type", "auth_events", ["event_type"], unique=False)


def downgrade() -> None:
    """Drop all tables (reverse of upgrade)."""
    # Drop indexes
    op.drop_index("idx_auth_events_type", table_name="auth_events")
    op.drop_index("idx_auth_events_timestamp", table_name="auth_events")
    op.drop_index("idx_auth_events_user_id", table_name="auth_events")
    op.drop_index("idx_behavioral_data_type", table_name="behavioral_data")
    op.drop_index("idx_behavioral_data_timestamp", table_name="behavioral_data")
    op.drop_index("idx_behavioral_data_user_id", table_name="behavioral_data")
    op.drop_index("idx_sessions_last_activity", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("model_metadata")
    op.drop_table("auth_events")
    op.drop_table("behavioral_data")
    op.drop_table("sessions")
    op.drop_table("users")
