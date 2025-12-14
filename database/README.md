# MeetLens Database Schema

## Quick Start

```bash
# 1. Install PostgreSQL
brew install postgresql@15  # macOS
brew services start postgresql@15

# 2. Create databases
createdb meetlens
createdb meetlens_test

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set DATABASE_URL

# 5. Run migrations
alembic upgrade head
```

## Schema Overview

The database implements an **account-centric architecture** with **soft deletes** throughout.

### Core Entities

- **users** - Identity and authentication (email, password)
- **accounts** - Resource ownership (personal, team, etc.)
- **account_memberships** - User ↔ Account relationships with roles
- **auth_sessions** - Active login sessions
- **magic_link_tokens** - Passwordless login tokens
- **password_reset_tokens** - Password reset flow

### Key Features

1. **Soft Delete Everywhere** - `deleted_at` column, no cascade deletes
2. **Global Email Uniqueness** - Case-insensitive via CITEXT
3. **Account-Centric** - All resources belong to accounts, not users
4. **Future-Proof** - Schema supports workspaces, teams, billing without migrations
5. **PostgreSQL Native** - UUID, CITEXT, TIMESTAMPTZ, triggers

## Design Principles

From the PRD:

1. **Account-centric architecture** - Everything belongs to an Account
2. **Schema supports future expansion, UI does not** - Built for scale
3. **Soft delete everywhere, no cascades** - Data is never truly deleted
4. **Global uniqueness for email** - One email = one user
5. **PostgreSQL-native features preferred** - Use the database's strengths

## Table Relationships

```
users (1) ----< (N) account_memberships (N) >---- (1) accounts
                           |
                           └─ role: 'owner', 'member', etc.

users (1) ----< (N) auth_sessions
users (1) ----< (N) magic_link_tokens
users (1) ----< (N) password_reset_tokens

accounts (1) ----< (N) accounts (parent_account_id, self-referential)
```

## Migration Files

Located in `alembic/versions/`:

- `001_create_users_table.py` - Users table with CITEXT extension
- `002_create_accounts_table.py` - Accounts table with hierarchy support
- `003_create_account_memberships_table.py` - User-Account join table
- `004_create_auth_tables.py` - Authentication support tables

## Repository Pattern

All database access goes through repositories in `database/repositories.py`:

```python
from database.repositories import UserRepository, AccountRepository

async def example(db: AsyncSession):
    user_repo = UserRepository(db)

    # Create user
    user = await user_repo.create_user(email="test@example.com")

    # Get by email (case-insensitive)
    user = await user_repo.get_by_email("TEST@EXAMPLE.COM")

    # Soft delete
    await user_repo.soft_delete(user)
    await db.commit()
```

### Soft Delete Behavior

By default, all queries exclude soft-deleted records:

```python
# Excludes deleted users (default)
user = await user_repo.get_by_id(user_id)

# Includes deleted users
user = await user_repo.get_by_id(user_id, include_deleted=True)
```

## ORM Models

SQLAlchemy models in `database/models.py`:

- `User` - User model with email, password_hash
- `Account` - Account model with type, parent hierarchy
- `AccountMembership` - Join model with role
- `AuthSession` - Session model with token_hash, expires_at
- `MagicLinkToken` - Magic link model with token_hash, used_at
- `PasswordResetToken` - Password reset model

## Authentication Flow Examples

### Signup (Email + Password)

```python
from database.repositories import (
    UserRepository,
    AccountRepository,
    AccountMembershipRepository
)

async def signup(db: AsyncSession, email: str, password: str):
    user_repo = UserRepository(db)
    account_repo = AccountRepository(db)
    membership_repo = AccountMembershipRepository(db)

    # Hash password
    password_hash = hash_password(password)

    # Create user
    user = await user_repo.create_user(email=email, password_hash=password_hash)

    # Create personal account
    account = await account_repo.create_account(account_type="personal")

    # Create membership (owner role)
    membership = await membership_repo.create_membership(
        user_id=user.id,
        account_id=account.id,
        role="owner"
    )

    await db.commit()
    return user, account
```

### Magic Link Login

```python
from database.repositories import MagicLinkTokenRepository, AuthSessionRepository

async def create_magic_link(db: AsyncSession, user_id: UUID):
    token_repo = MagicLinkTokenRepository(db)

    # Generate random token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create token (expires in 15 minutes)
    token = await token_repo.create_token(
        user_id=user_id,
        token_hash=token_hash,
        expires_in_minutes=15
    )

    await db.commit()
    return raw_token  # Send this in email

async def consume_magic_link(db: AsyncSession, raw_token: str):
    token_repo = MagicLinkTokenRepository(db)
    session_repo = AuthSessionRepository(db)

    # Hash token
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Verify token (checks expiry and used_at)
    magic_token = await token_repo.get_by_token_hash(token_hash)
    if not magic_token:
        raise ValueError("Invalid or expired token")

    # Mark as used
    await token_repo.mark_as_used(magic_token)

    # Create session
    session_token = secrets.token_urlsafe(32)
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()

    session = await session_repo.create_session(
        user_id=magic_token.user_id,
        token_hash=session_hash,
        expires_in_hours=24
    )

    await db.commit()
    return session_token  # Return to client
```

### Password Reset

```python
from database.repositories import PasswordResetTokenRepository, UserRepository

async def request_password_reset(db: AsyncSession, email: str):
    user_repo = UserRepository(db)
    token_repo = PasswordResetTokenRepository(db)

    user = await user_repo.get_by_email(email)
    if not user:
        return  # Don't reveal if user exists

    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Create token (expires in 30 minutes)
    token = await token_repo.create_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_in_minutes=30
    )

    await db.commit()
    return raw_token  # Send in email

async def reset_password(db: AsyncSession, raw_token: str, new_password: str):
    token_repo = PasswordResetTokenRepository(db)
    user_repo = UserRepository(db)

    # Hash token
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Verify token
    reset_token = await token_repo.get_by_token_hash(token_hash)
    if not reset_token:
        raise ValueError("Invalid or expired token")

    # Update password
    new_hash = hash_password(new_password)
    user = await user_repo.get_by_id(reset_token.user_id)
    await user_repo.update_password(user, new_hash)

    # Mark token as used
    await token_repo.mark_as_used(reset_token)

    await db.commit()
```

## Testing

Run database tests:

```bash
# All database tests
pytest tests/test_database_schema.py tests/test_auth_flows.py -v

# Schema tests only
pytest tests/test_database_schema.py -v

# Auth flow tests only
pytest tests/test_auth_flows.py -v
```

Tests automatically:
- Create fresh test database
- Run migrations
- Use transactions (rolled back after each test)
- Clean up after completion

## Common Operations

### Create User with Account

```python
async def create_user_with_account(db: AsyncSession, email: str):
    user = await UserRepository(db).create_user(email=email)
    account = await AccountRepository(db).create_account(account_type="personal")
    membership = await AccountMembershipRepository(db).create_membership(
        user_id=user.id,
        account_id=account.id,
        role="owner"
    )
    await db.commit()
    return user, account
```

### List User's Accounts

```python
async def get_user_accounts(db: AsyncSession, user_id: UUID):
    memberships = await AccountMembershipRepository(db).get_user_memberships(user_id)
    return [m.account for m in memberships]
```

### Verify Email

```python
async def verify_user_email(db: AsyncSession, user_id: UUID):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    await user_repo.verify_email(user)
    await db.commit()
```

## Security Best Practices

1. **Never store plain text passwords** - Use passlib with bcrypt
2. **Always hash tokens** - Use SHA-256 minimum before storage
3. **Validate expiration** - Check `expires_at` before accepting tokens
4. **Check `used_at`** - Ensure tokens are single-use
5. **Revoke sessions** - Set `revoked_at` instead of deleting
6. **Rate limit** - Implement at application layer

## Troubleshooting

### Migrations fail

```bash
# Check current version
alembic current

# View migration history
alembic history

# Downgrade to previous version
alembic downgrade -1
```

### Tests fail

```bash
# Ensure test database exists
createdb meetlens_test

# Run migrations on test database
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens_test alembic upgrade head
```

### Connection errors

```bash
# Test connection
psql postgresql://postgres:postgres@localhost:5432/meetlens

# Check PostgreSQL is running
brew services list  # macOS
sudo systemctl status postgresql  # Linux
```

## Future Roadmap

The schema is designed to support (without schema changes):

- **Team Accounts** - Just add `account_type = 'team'`
- **Workspaces** - Use `parent_account_id` hierarchy
- **Billing** - Attach billing tables to `accounts.id`
- **Advanced Roles** - Add more `role` values to memberships
- **Reseller Hierarchy** - Use `parent_account_id` chains

## Additional Resources

- Full documentation: `docs/database.md`
- Alembic migrations: `alembic/versions/`
- ORM models: `database/models.py`
- Repositories: `database/repositories.py`
- Schema tests: `tests/test_database_schema.py`
- Auth flow tests: `tests/test_auth_flows.py`
