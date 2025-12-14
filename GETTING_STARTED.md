# Getting Started with MeetLens Database

## Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] PostgreSQL 15+ installed
- [ ] pip or virtualenv available

## Step-by-Step Setup

### 1. Install PostgreSQL

Choose your platform:

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
Download from https://www.postgresql.org/download/windows/

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

```bash
# Copy example env file
cp .env.example .env

# Edit .env and update these variables:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens
# TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meetlens_test
```

### 5. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migration status
alembic current

# You should see: "004 (head)"
```

### 6. Run Tests

```bash
# Run all database tests
pytest tests/test_database_schema.py tests/test_auth_flows.py -v

# Expected: All tests pass ✅
```

## Verification Checklist

After setup, verify everything works:

- [ ] PostgreSQL is running: `pg_isready`
- [ ] Databases exist: `psql -l | grep meetlens`
- [ ] Tables created: `psql meetlens -c "\dt"`
- [ ] Migrations applied: `alembic current` shows "004"
- [ ] Tests pass: `pytest tests/test_database_schema.py -v`

## Next Steps

### For MVP Development:

1. **Implement Auth Endpoints**
   - [ ] POST /auth/signup - User registration
   - [ ] POST /auth/login - Email + password login
   - [ ] POST /auth/magic-link/request - Request magic link
   - [ ] POST /auth/magic-link/verify - Verify magic link token
   - [ ] POST /auth/password-reset/request - Request password reset
   - [ ] POST /auth/password-reset/verify - Reset password with token
   - [ ] GET /auth/me - Get current user
   - [ ] POST /auth/logout - Logout (revoke session)

2. **Add Session Middleware**
   - [ ] Extract token from Authorization header
   - [ ] Verify session token with AuthSessionRepository
   - [ ] Inject current user into request context
   - [ ] Handle expired/revoked sessions

3. **Implement Email Sending**
   - [ ] Configure email provider (SendGrid, AWS SES, etc.)
   - [ ] Create email templates for magic links
   - [ ] Create email templates for password reset
   - [ ] Send verification emails (optional for MVP)

4. **Add Account Context**
   - [ ] Add account_id to JWT/session payload
   - [ ] Implement account switching for multi-account users
   - [ ] Enforce account-level permissions

### For Phase 2:

- [ ] Enable email verification enforcement
- [ ] Add team account creation
- [ ] Add invitation system
- [ ] Add billing integration
- [ ] Add workspace hierarchy

## Common Tasks

### Create a new migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add new column"

# Create empty migration
alembic revision -m "custom migration"
```

### Rollback a migration

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

### Reset test database

```bash
# Drop and recreate
dropdb meetlens_test
createdb meetlens_test
alembic upgrade head
```

### View database schema

```bash
# Connect to database
psql meetlens

# List tables
\dt

# Describe table
\d users

# View indexes
\di

# Exit
\q
```

## Example Code: User Signup

Here's a complete example of implementing user signup:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from database.config import get_db
from database.repositories import (
    UserRepository,
    AccountRepository,
    AccountMembershipRepository,
    AuthSessionRepository,
)
from database.utils import hash_password, generate_and_hash_token

router = APIRouter(prefix="/auth", tags=["auth"])

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class SignupResponse(BaseModel):
    user_id: str
    account_id: str
    session_token: str

@router.post("/signup", response_model=SignupResponse)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository(db)
    account_repo = AccountRepository(db)
    membership_repo = AccountMembershipRepository(db)
    session_repo = AuthSessionRepository(db)

    # Check if user exists
    existing_user = await user_repo.get_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    password_hash = hash_password(request.password)

    # Create user
    user = await user_repo.create_user(
        email=request.email,
        password_hash=password_hash
    )

    # Create personal account
    account = await account_repo.create_account(account_type="personal")

    # Create membership
    await membership_repo.create_membership(
        user_id=user.id,
        account_id=account.id,
        role="owner"
    )

    # Create session
    session_token, token_hash = generate_and_hash_token()
    await session_repo.create_session(
        user_id=user.id,
        token_hash=token_hash,
        expires_in_hours=24
    )

    # Commit transaction
    await db.commit()

    return SignupResponse(
        user_id=str(user.id),
        account_id=str(account.id),
        session_token=session_token
    )
```

## Example Code: Magic Link Login

```python
from datetime import datetime
from database.repositories import MagicLinkTokenRepository
from database.utils import generate_and_hash_token

class MagicLinkRequest(BaseModel):
    email: EmailStr

@router.post("/magic-link/request")
async def request_magic_link(
    request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository(db)
    token_repo = MagicLinkTokenRepository(db)

    # Find user
    user = await user_repo.get_by_email(request.email)
    if not user:
        # Don't reveal if user exists
        return {"message": "If the email exists, a magic link has been sent"}

    # Generate token
    raw_token, token_hash = generate_and_hash_token()

    # Create magic link token
    await token_repo.create_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_in_minutes=15
    )

    await db.commit()

    # TODO: Send email with magic link
    # magic_link = f"https://app.meetlens.com/auth/magic-link?token={raw_token}"
    # send_email(user.email, magic_link)

    return {"message": "If the email exists, a magic link has been sent"}

class MagicLinkVerifyRequest(BaseModel):
    token: str

class MagicLinkVerifyResponse(BaseModel):
    session_token: str

@router.post("/magic-link/verify", response_model=MagicLinkVerifyResponse)
async def verify_magic_link(
    request: MagicLinkVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    from database.utils import hash_token

    token_repo = MagicLinkTokenRepository(db)
    session_repo = AuthSessionRepository(db)

    # Hash token
    token_hash = hash_token(request.token)

    # Verify token (checks expiry and used_at)
    magic_token = await token_repo.get_by_token_hash(token_hash)
    if not magic_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )

    # Mark token as used
    await token_repo.mark_as_used(magic_token)

    # Create session
    session_token, session_hash = generate_and_hash_token()
    await session_repo.create_session(
        user_id=magic_token.user_id,
        token_hash=session_hash,
        expires_in_hours=24
    )

    await db.commit()

    return MagicLinkVerifyResponse(session_token=session_token)
```

## Troubleshooting

### "relation does not exist" error

```bash
# Run migrations
alembic upgrade head
```

### "password authentication failed"

Update DATABASE_URL in .env with correct credentials:
```
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/meetlens
```

### Tests fail with connection error

Make sure test database exists:
```bash
createdb meetlens_test
```

### Migration conflicts

```bash
# View current version
alembic current

# View all migrations
alembic history

# Reset to specific version
alembic downgrade <revision_id>
alembic upgrade head
```

## Resources

- **Database Documentation**: `docs/database.md`
- **Quick Reference**: `database/README.md`
- **Schema Diagram**: `docs/SCHEMA_DIAGRAM.md`
- **Implementation Summary**: `DATABASE_IMPLEMENTATION_SUMMARY.md`

## Support

For issues or questions:
1. Check documentation in `docs/database.md`
2. Review test examples in `tests/test_auth_flows.py`
3. Consult SQLAlchemy docs: https://docs.sqlalchemy.org/
4. Check Alembic docs: https://alembic.sqlalchemy.org/

---

**Status**: ✅ Ready for MVP Development

The database layer is fully implemented and tested. You can now build authentication endpoints and integrate with your FastAPI application.
