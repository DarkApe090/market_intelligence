"""add gmail thread id to company contacts

Revision ID: 7c9e4a12b8d0
Revises: 264c1f186031
Create Date: 2026-10-13 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c9e4a12b8d0"
down_revision: Union[str, Sequence[str], None] = "264c1f186031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_contacts",
        sa.Column("gmail_thread_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_contacts", "gmail_thread_id")
