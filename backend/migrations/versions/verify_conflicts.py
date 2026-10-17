"""phase7 verify and conflicts

Revision ID: a7c3e1f9b240
Revises: 
Create Date: 2026-10-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7c3e1f9b240"
down_revision = "43209db3f185" 
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("updated_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tasks_updated_by_users", "tasks", "users",
                          ["updated_by"], ["id"], ondelete="RESTRICT")
    op.add_column("decisions", sa.Column("superseded_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_decisions_superseded_by", "decisions", "decisions",
                          ["superseded_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_decisions_superseded_by", "decisions", type_="foreignkey")
    op.drop_column("decisions", "superseded_by")
    op.drop_constraint("fk_tasks_updated_by_users", "tasks", type_="foreignkey")
    op.drop_column("tasks", "updated_by")