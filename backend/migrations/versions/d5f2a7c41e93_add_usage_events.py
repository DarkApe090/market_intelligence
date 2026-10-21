"""add usage events for per-user quotas

Revision ID: d5f2a7c41e93
Revises: c3d8e1a90b2f
Create Date: 2026-10-15 12:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5f2a7c41e93"
down_revision: Union[str, Sequence[str], None] = "c3d8e1a90b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id_usage", sa.Integer(), primary_key=True),
        sa.Column("id_user", sa.Integer(), sa.ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_events_id_user", "usage_events", ["id_user"])
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_id_user", table_name="usage_events")
    op.drop_table("usage_events")
