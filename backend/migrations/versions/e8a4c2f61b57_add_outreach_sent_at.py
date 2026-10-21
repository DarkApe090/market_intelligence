"""add sent timestamp to company contacts

Revision ID: e8a4c2f61b57
Revises: d5f2a7c41e93
Create Date: 2026-10-16 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a4c2f61b57"
down_revision: Union[str, Sequence[str], None] = "d5f2a7c41e93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company_contacts", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("company_contacts", "sent_at")
