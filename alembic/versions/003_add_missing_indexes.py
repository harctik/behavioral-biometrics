"""add missing indexes

Revision ID: 003
Revises: 002
Create Date: 2026-04-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('idx_behavioral_data_user_ts', 'behavioral_data', ['user_id', sa.text('timestamp DESC')])
    op.create_index('idx_sessions_user_id', 'sessions', ['user_id'], if_not_exists=True)
    op.create_index('idx_audit_evidence_user_action', 'audit_evidence', ['user_id', 'action'])

def downgrade():
    op.drop_index('idx_behavioral_data_user_ts', table_name='behavioral_data')
    op.drop_index('idx_sessions_user_id', table_name='sessions', if_exists=True)
    op.drop_index('idx_audit_evidence_user_action', table_name='audit_evidence')
