"""role cleanup: member -> editor, constrain roles

Revision ID: a1f3c9d2b7e4
Revises: de08efde38ed
Create Date: 2026-10-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1f3c9d2b7e4'
down_revision: Union[str, Sequence[str], None] = 'de08efde38ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert before adding the constraint, or existing 'member' rows would violate it.
    op.execute("UPDATE project_members SET role = 'editor' WHERE role = 'member'")
    op.alter_column('project_members', 'role', server_default='editor')
    op.create_check_constraint(
        'ck_project_members_role', 'project_members',
        "role IN ('viewer', 'editor', 'owner')")


def downgrade() -> None:
    # Cannot tell which editors used to be 'member'; they stay 'editor'.
    op.drop_constraint('ck_project_members_role', 'project_members', type_='check')
    op.alter_column('project_members', 'role', server_default='member')
