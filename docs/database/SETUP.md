# Database Setup & Quick Start

This guide covers everything you need to get the MeetLens database up and running, from installation to common development tasks.

## Prerequisites

- Python 3.10+
- PostgreSQL 15+
- pip or virtualenv

## Step-by-Step Setup

### 1. Install PostgreSQL

**macOS (Homebrew)**:
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows**:
Download from [postgresql.org](https://www.postgresql.org/download/windows/)

### 2. Create Databases

**Quick method** (using provided script):
```bash
./scripts/setup_database.sh
```

**Manual method**:
```bash
# Connect to PostgreSQL
psql postgres

# In psql:
CREATE DATABASE meetlens;
CREATE DATABASE meetlens_test;

# Exit
\q
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and update the database URLs:

```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens_test
```

### 5. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migration status
alembic current
# Expected output: "004 (head)"
```

### 6. Run Tests

```bash
# Run all database tests
pytest tests/test_database_schema.py tests/test_auth_flows.py -v
```

---

## Verification Checklist

- [ ] PostgreSQL is running: `pg_isready`
- [ ] Databases exist: `psql -l | grep meetlens`
- [ ] Tables created: `psql meetlens -c "\dt"`
- [ ] Migrations applied: `alembic current` shows "004"
- [ ] Tests pass: `pytest tests/test_database_schema.py -v`

---

## Repository Pattern Examples

All database access should go through repositories in `database/repositories.py`.

### User Signup Example

```python
from database.repositories import UserRepository, AccountRepository, AccountMembershipRepository

async def signup(db: AsyncSession, email: str, password: str):
    user_repo = UserRepository(db)
    account_repo = AccountRepository(db)
    membership_repo = AccountMembershipRepository(db)

    # Hash password (see database.utils)
    password_hash = hash_password(password)

    # 1. Create user
    user = await user_repo.create_user(email=email, password_hash=password_hash)

    # 2. Create personal account
    account = await account_repo.create_account(account_type="personal")

    # 3. Create membership (owner role)
    membership = await membership_repo.create_membership(
        user_id=user.id,
        account_id=account.id,
        role="owner"
    )

    await db.commit()
    return user, account
```

### Soft Delete Behavior

By default, all queries exclude soft-deleted records:

```python
# Excludes deleted users (default)
user = await user_repo.get_by_id(user_id)

# Includes deleted users
user = await user_repo.get_by_id(user_id, include_deleted=True)
```

---

## Common Development Tasks

### Creating a New Migration

```bash
# Auto-generate from model changes (models.py)
alembic revision --autogenerate -m "description of changes"

# Create empty migration
alembic revision -m "custom migration"
```

### Rollback a Migration

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

### Viewing Database Schema

```bash
psql meetlens
# \dt      - List tables
# \d users - Describe users table
# \q       - Exit
```

---

## Troubleshooting

- **"relation does not exist"**: Run `alembic upgrade head`.
- **"password authentication failed"**: Check `DATABASE_URL` credentials in `.env`.
- **Tests fail with connection error**: Ensure `meetlens_test` database exists.

## Additional Resources

- [Database Overview](OVERVIEW.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Schema Diagram](../architecture/SCHEMA_DIAGRAM.md)
