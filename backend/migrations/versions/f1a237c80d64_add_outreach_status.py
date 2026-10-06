"""add outreach status to company contacts

Revision ID: f1a237c80d64
Revises: d9c27a4b31f0
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a237c80d64"
down_revision: Union[str, Sequence[str], None] = "d9c27a4b31f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_contacts",
        sa.Column(
            "outreach_status",
            sa.String(length=30),
            nullable=False,
            server_default="to_contact",
        ),
    )
    op.alter_column(
        "company_contacts",
        "outreach_status",
        existing_type=sa.String(length=30),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("company_contacts", "outreach_status")