"""project soft delete and unique live names

Revision ID: b4d8f2a6c901
Revises: a7c3e1f9b240
Create Date: 2026-10-18 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4d8f2a6c901'
down_revision: Union[str, Sequence[str], None] = 'a7c3e1f9b240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects',
                  sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    # Fails if two live projects already share a name (ignoring case).
    op.create_index(
        'uq_projects_active_name', 'projects', [sa.text('lower(name)')],
        unique=True, postgresql_where=sa.text('deleted_at IS NULL'))


def downgrade() -> None:
    op.drop_index('uq_projects_active_name', table_name='projects')
    op.drop_column('projects', 'deleted_at')