# MeetLens Database Documentation

## Overview

MeetLens uses PostgreSQL with SQLAlchemy 2.0 (async) for database operations. The database schema follows an account-centric architecture with soft delete support throughout.

## Design Principles

1. **Account-centric architecture** - Everything belongs to an Account
2. **Schema supports future expansion, UI does not** - Built for scale from day one
3. **Soft delete everywhere, no cascades** - Data is never truly deleted
4. **Global uniqueness for email** - Case-insensitive email uniqueness
5. **PostgreSQL-native features preferred** - UUID, CITEXT, TIMESTAMPTZ

## Database Schema

### Core Tables

#### users
Stores identity and authentication metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | User identifier (auto-generated) |
| email | CITEXT | UNIQUE, NOT NULL | Case-insensitive email |
| password_hash | TEXT | NULLABLE | Nullable for magic-link-only users |
| email_verified_at | TIMESTAMPTZ | NULLABLE | Email verification timestamp |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Auto-updated timestamp |
| deleted_at | TIMESTAMPTZ | NULLABLE | Soft delete timestamp |

#### accounts
Logical owner of all product resources.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Account identifier |
| account_type | TEXT | NOT NULL | MVP: 'personal' only |
| parent_account_id | UUID | FK, NULLABLE | Reserved for future features |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Auto-updated timestamp |
| deleted_at | TIMESTAMPTZ | NULLABLE | Soft delete timestamp |

#### account_memberships
Joins Users to Accounts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Membership identifier |
| user_id | UUID | FK(users.id) | User reference |
| account_id | UUID | FK(accounts.id) | Account reference |
| role | TEXT | NOT NULL | MVP default: 'owner' |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| deleted_at | TIMESTAMPTZ | NULLABLE | Soft delete timestamp |

**Unique Constraint**: `(user_id, account_id)` for active (non-deleted) memberships

### Authentication Tables

#### auth_sessions
Active login sessions / refresh tokens.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Session identifier |
| user_id | UUID | FK(users.id) | User reference |
| token_hash | TEXT | UNIQUE, NOT NULL | Hashed session token |
| expires_at | TIMESTAMPTZ | NOT NULL | Expiration timestamp |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| revoked_at | TIMESTAMPTZ | NULLABLE | Revocation timestamp |

#### magic_link_tokens
One-time login tokens for passwordless authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Token identifier |
| user_id | UUID | FK(users.id) | User reference |
| token_hash | TEXT | UNIQUE, NOT NULL | Hashed token |
| expires_at | TIMESTAMPTZ | NOT NULL | Expiration timestamp |
| used_at | TIMESTAMPTZ | NULLABLE | Usage timestamp |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |

#### password_reset_tokens
Password reset flow tokens.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Token identifier |
| user_id | UUID | FK(users.id) | User reference |
| token_hash | TEXT | UNIQUE, NOT NULL | Hashed token |
| expires_at | TIMESTAMPTZ | NOT NULL | Expiration timestamp |
| used_at | TIMESTAMPTZ | NULLABLE | Usage timestamp |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |

## Setup & Troubleshooting

For installation, environment configuration, migration management, and troubleshooting, see the [Database Setup & Quick Start](SETUP.md) guide.

## Using the Database

### Getting a Database Session

```python
from database.config import get_db
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    # Use db session here
    pass
```

### Using Repositories

```python
from database.repositories import UserRepository, AccountRepository

async def create_user_with_account(db: AsyncSession, email: str):
    user_repo = UserRepository(db)
    account_repo = AccountRepository(db)
    membership_repo = AccountMembershipRepository(db)

    # Create user
    user = await user_repo.create_user(email=email)

    # Create personal account
    account = await account_repo.create_account(account_type="personal")

    # Create membership
    membership = await membership_repo.create_membership(
        user_id=user.id,
        account_id=account.id,
        role="owner"
    )

    await db.commit()
    return user, account, membership
```

### Soft Delete Pattern

All queries automatically exclude soft-deleted records:

```python
# Get active user only
user = await user_repo.get_by_id(user_id)

# Include soft-deleted users
user = await user_repo.get_by_id(user_id, include_deleted=True)

# Soft delete a user
await user_repo.soft_delete(user)
await db.commit()
```

### Query Patterns

```python
# Get user by email (case-insensitive)
user = await user_repo.get_by_email("TEST@EXAMPLE.COM")

# Get user's memberships
memberships = await membership_repo.get_user_memberships(user.id)

# Get account's members
members = await membership_repo.get_account_memberships(account.id)

# Create and verify magic link
token = await magic_link_repo.create_token(user.id, token_hash)
retrieved = await magic_link_repo.get_by_token_hash(token_hash)
await magic_link_repo.mark_as_used(retrieved)
```

## Testing

See [Database Setup & Quick Start](SETUP.md#6-run-tests) for instructions on running database tests.

## Security Considerations

1. **Never store plain text passwords** - Always hash with passlib/bcrypt
2. **Always hash tokens** - Use SHA-256 or stronger before storing
3. **Use prepared statements** - SQLAlchemy handles this automatically
4. **Validate input** - Use Pydantic models for validation
5. **Limit query results** - Always use pagination for list endpoints
6. **Use connection pooling** - Configured in database.config

## Performance Tips

1. **Use indexes wisely** - Already configured for common queries
2. **Partial indexes** - Used for soft delete queries
3. **Connection pooling** - Default pool_size=10, max_overflow=20
4. **Async all the way** - Use async/await throughout
5. **Lazy loading** - Use selectin for relationships
6. **Query optimization** - Use `select()` for complex queries

## Troubleshooting

See [Database Setup & Quick Start](SETUP.md#troubleshooting).

## Future Extensions

The schema is designed to support (without migrations):

- **Workspaces** - Use parent_account_id hierarchy
- **Team accounts** - Add new account_type values
- **Billing** - Attach billing tables to accounts
- **Resellers** - Use parent_account_id for hierarchy
- **Advanced roles** - Add new role values to memberships

## References

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
