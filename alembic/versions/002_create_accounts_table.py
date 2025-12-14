"""create accounts table

Revision ID: 002
Revises: 001
Create Date: 2025-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_type', sa.Text(), nullable=False),
        sa.Column('parent_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create foreign key for parent_account_id (self-referential)
    op.create_foreign_key(
        'fk_accounts_parent_account_id',
        'accounts',
        'accounts',
        ['parent_account_id'],
        ['id'],
        ondelete='SET NULL'  # No cascade - soft delete principle
    )

    # Create partial index for active accounts
    op.create_index(
        'ix_accounts_id_active',
        'accounts',
        ['id'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # Create index on account_type for queries
    op.create_index(
        'ix_accounts_account_type',
        'accounts',
        ['account_type']
    )

    # Create trigger to auto-update updated_at
    op.execute("""
        CREATE TRIGGER update_accounts_updated_at
        BEFORE UPDATE ON accounts
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts')

    # Drop indexes
    op.drop_index('ix_accounts_account_type', table_name='accounts')
    op.drop_index('ix_accounts_id_active', table_name='accounts')

    # Drop foreign key
    op.drop_constraint('fk_accounts_parent_account_id', 'accounts', type_='foreignkey')

    # Drop table
    op.drop_table('accounts')
