"""make source location optional

Revision ID: b3e91c5d7a28
Revises: f1a237c80d64
Create Date: 2026-10-06 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3e91c5d7a28'
down_revision: Union[str, Sequence[str], None] = 'f1a237c80d64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('sources', 'id_location', nullable=True)


def downgrade() -> None:
    op.alter_column('sources', 'id_location', nullable=False)
