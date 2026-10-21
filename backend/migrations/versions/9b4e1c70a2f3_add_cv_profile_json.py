"""add cached cv profile json

Revision ID: 9b4e1c70a2f3
Revises: 7c9e4a12b8d0
Create Date: 2026-10-14 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b4e1c70a2f3"
down_revision: Union[str, Sequence[str], None] = "7c9e4a12b8d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_cvs", sa.Column("profile_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_cvs", "profile_json")
