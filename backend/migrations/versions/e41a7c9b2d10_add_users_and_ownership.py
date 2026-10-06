"""add users, sessions, google accounts, cvs and row ownership

Revision ID: e41a7c9b2d10
Revises: d30561622c5e
Create Date: 2026-10-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e41a7c9b2d10'
down_revision: Union[str, Sequence[str], None] = 'd30561622c5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id_user', sa.Integer(), primary_key=True),
        sa.Column('google_sub', sa.String(length=64), nullable=False, unique=True),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('picture_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'auth_sessions',
        sa.Column('token_hash', sa.String(length=64), primary_key=True),
        sa.Column('id_user', sa.Integer(), sa.ForeignKey('users.id_user', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_auth_sessions_id_user', 'auth_sessions', ['id_user'])
    op.create_table(
        'google_accounts',
        sa.Column('id_user', sa.Integer(), sa.ForeignKey('users.id_user', ondelete='CASCADE'), primary_key=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=False),
    )
    op.create_table(
        'user_cvs',
        sa.Column('id_user', sa.Integer(), sa.ForeignKey('users.id_user', ondelete='CASCADE'), primary_key=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('candidate_name', sa.String(length=200), nullable=True),
        sa.Column('skills_json', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
    )
    for table in ('companies', 'contacts'):
        op.add_column(table, sa.Column('id_user', sa.Integer(), nullable=True))
        op.create_foreign_key(f'fk_{table}_id_user', table, 'users', ['id_user'], ['id_user'], ondelete='CASCADE')
        op.create_index(f'ix_{table}_id_user', table, ['id_user'])


def downgrade() -> None:
    for table in ('contacts', 'companies'):
        op.drop_index(f'ix_{table}_id_user', table_name=table)
        op.drop_constraint(f'fk_{table}_id_user', table, type_='foreignkey')
        op.drop_column(table, 'id_user')
    op.drop_table('user_cvs')
    op.drop_table('google_accounts')
    op.drop_index('ix_auth_sessions_id_user', table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_table('users')
