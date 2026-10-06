"""add contact outreach details

Revision ID: d9c27a4b31f0
Revises: 12682ead8e87
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9c27a4b31f0"
down_revision: Union[str, Sequence[str], None] = "12682ead8e87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("name_contact", sa.String(length=150), nullable=True))
    op.add_column("contacts", sa.Column("role_contact", sa.String(length=150), nullable=True))
    op.add_column("contacts", sa.Column("contact_type", sa.String(length=50), nullable=True))
    op.add_column("contacts", sa.Column("source_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "source_url")
    op.drop_column("contacts", "contact_type")
    op.drop_column("contacts", "role_contact")
    op.drop_column("contacts", "name_contact")