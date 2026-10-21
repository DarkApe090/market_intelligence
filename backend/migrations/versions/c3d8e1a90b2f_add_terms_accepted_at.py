"""add terms accepted timestamp

Revision ID: c3d8e1a90b2f
Revises: 9b4e1c70a2f3
Create Date: 2026-10-15 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d8e1a90b2f"
down_revision: Union[str, Sequence[str], None] = "9b4e1c70a2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "terms_accepted_at")
