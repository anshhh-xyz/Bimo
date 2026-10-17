"""project summary

Revision ID: 43209db3f185
Revises: a1f3c9d2b7e4
Create Date: 2026-10-17 20:04:14.974350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43209db3f185'
down_revision: Union[str, Sequence[str], None] = 'a1f3c9d2b7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
       op.add_column("projects", sa.Column("summary", sa.Text(), nullable=True))
       op.add_column("projects", sa.Column("summary_version", sa.Integer(),
                                           server_default="1", nullable=False))
       op.create_check_constraint("ck_projects_summary_len", "projects",
                                  "summary IS NULL OR char_length(summary) <= 4000")


def downgrade() -> None:
       op.drop_constraint("ck_projects_summary_len", "projects", type_="check")
       op.drop_column("projects", "summary_version")
       op.drop_column("projects", "summary")