"""create auth tables

Revision ID: 004
Revises: 003
Create Date: 2025-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create auth_sessions table
    op.create_table(
        'auth_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create foreign key to users
    op.create_foreign_key(
        'fk_auth_sessions_user_id',
        'auth_sessions',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'  # Sessions should be deleted if user is deleted
    )

    # Create indexes for auth_sessions
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_token_hash', 'auth_sessions', ['token_hash'], unique=True)
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])

    # Create magic_link_tokens table
    op.create_table(
        'magic_link_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Create foreign key to users
    op.create_foreign_key(
        'fk_magic_link_tokens_user_id',
        'magic_link_tokens',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create indexes for magic_link_tokens
    op.create_index('ix_magic_link_tokens_user_id', 'magic_link_tokens', ['user_id'])
    op.create_index('ix_magic_link_tokens_token_hash', 'magic_link_tokens', ['token_hash'], unique=True)
    op.create_index('ix_magic_link_tokens_expires_at', 'magic_link_tokens', ['expires_at'])

    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Create foreign key to users
    op.create_foreign_key(
        'fk_password_reset_tokens_user_id',
        'password_reset_tokens',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create indexes for password_reset_tokens
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_expires_at', 'password_reset_tokens', ['expires_at'])


def downgrade() -> None:
    # Drop password_reset_tokens
    op.drop_index('ix_password_reset_tokens_expires_at', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_token_hash', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_user_id', table_name='password_reset_tokens')
    op.drop_constraint('fk_password_reset_tokens_user_id', 'password_reset_tokens', type_='foreignkey')
    op.drop_table('password_reset_tokens')

    # Drop magic_link_tokens
    op.drop_index('ix_magic_link_tokens_expires_at', table_name='magic_link_tokens')
    op.drop_index('ix_magic_link_tokens_token_hash', table_name='magic_link_tokens')
    op.drop_index('ix_magic_link_tokens_user_id', table_name='magic_link_tokens')
    op.drop_constraint('fk_magic_link_tokens_user_id', 'magic_link_tokens', type_='foreignkey')
    op.drop_table('magic_link_tokens')

    # Drop auth_sessions
    op.drop_index('ix_auth_sessions_expires_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_token_hash', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_user_id', table_name='auth_sessions')
    op.drop_constraint('fk_auth_sessions_user_id', 'auth_sessions', type_='foreignkey')
    op.drop_table('auth_sessions')
