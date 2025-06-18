"""add agent_state to flow

Revision ID: 634f33015b24
Revises: 
Create Date: 2025-01-21 14:18:55.531872

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '634f33015b24'
down_revision = 'd116ead34789'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add agent_state column to flows table
    op.add_column('flows', sa.Column('agent_state', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove agent_state column from flows table
    op.drop_column('flows', 'agent_state')
