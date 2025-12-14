"""create account_memberships table

Revision ID: 003
Revises: 002
Create Date: 2025-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create account_memberships table
    op.create_table(
        'account_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create foreign key to users (no cascade delete)
    op.create_foreign_key(
        'fk_account_memberships_user_id',
        'account_memberships',
        'users',
        ['user_id'],
        ['id'],
        ondelete='RESTRICT'  # Prevent deletion if memberships exist
    )

    # Create foreign key to accounts (no cascade delete)
    op.create_foreign_key(
        'fk_account_memberships_account_id',
        'account_memberships',
        'accounts',
        ['account_id'],
        ['id'],
        ondelete='RESTRICT'  # Prevent deletion if memberships exist
    )

    # Create unique constraint on (user_id, account_id) for active memberships
    op.create_index(
        'ix_account_memberships_user_account_active',
        'account_memberships',
        ['user_id', 'account_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # Create index on user_id for queries
    op.create_index(
        'ix_account_memberships_user_id',
        'account_memberships',
        ['user_id']
    )

    # Create index on account_id for queries
    op.create_index(
        'ix_account_memberships_account_id',
        'account_memberships',
        ['account_id']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_account_memberships_account_id', table_name='account_memberships')
    op.drop_index('ix_account_memberships_user_id', table_name='account_memberships')
    op.drop_index('ix_account_memberships_user_account_active', table_name='account_memberships')

    # Drop foreign keys
    op.drop_constraint('fk_account_memberships_account_id', 'account_memberships', type_='foreignkey')
    op.drop_constraint('fk_account_memberships_user_id', 'account_memberships', type_='foreignkey')

    # Drop table
    op.drop_table('account_memberships')
