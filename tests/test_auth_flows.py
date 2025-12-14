"""
Integration tests for authentication flows.

Tests cover:
- Signup with email + password
- Magic link login
- Password reset
- Query behavior with soft deletes
"""
import pytest
import hashlib
from datetime import datetime, timedelta, timezone
from database.repositories import (
    UserRepository,
    AccountRepository,
    AccountMembershipRepository,
    AuthSessionRepository,
    MagicLinkTokenRepository,
    PasswordResetTokenRepository,
)


def hash_token(token: str) -> str:
    """Helper to hash tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.asyncio
class TestSignupFlow:
    """Test user signup and account creation flow."""

    async def test_signup_creates_user_account_and_membership(self, db_session):
        """Signup creates user, account, and membership with role='owner'."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        # Simulate signup
        email = "newuser@example.com"
        password_hash = hash_token("secure_password")

        # Create user
        user = await user_repo.create_user(email=email, password_hash=password_hash)

        # Create personal account
        account = await account_repo.create_account(account_type="personal")

        # Create membership with owner role
        membership = await membership_repo.create_membership(
            user_id=user.id, account_id=account.id, role="owner"
        )

        await db_session.commit()

        # Verify user
        assert user.email == email
        assert user.password_hash == password_hash
        assert user.deleted_at is None

        # Verify account
        assert account.account_type == "personal"
        assert account.deleted_at is None

        # Verify membership
        assert membership.user_id == user.id
        assert membership.account_id == account.id
        assert membership.role == "owner"
        assert membership.deleted_at is None

    async def test_signup_duplicate_email_fails(self, db_session):
        """Re-running signup with same email fails due to unique email constraint."""
        user_repo = UserRepository(db_session)

        email = "duplicate@example.com"
        await user_repo.create_user(email=email, password_hash="hash1")
        await db_session.commit()

        # Try to create another user with same email
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await user_repo.create_user(email=email, password_hash="hash2")
            await db_session.commit()
        await db_session.rollback()


@pytest.mark.asyncio
class TestMagicLinkFlow:
    """Test magic link authentication flow."""

    async def test_create_magic_link_token(self, db_session):
        """Creating a magic_link_tokens row for an existing user succeeds."""
        user_repo = UserRepository(db_session)
        token_repo = MagicLinkTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        raw_token = "secure_random_token_123"
        token_hash_value = hash_token(raw_token)

        magic_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value, expires_in_minutes=15
        )
        await db_session.commit()

        assert magic_token.user_id == user.id
        assert magic_token.token_hash == token_hash_value
        assert magic_token.used_at is None
        assert magic_token.expires_at > datetime.now(timezone.utc)

    async def test_consume_magic_link_creates_session(self, db_session):
        """Consuming a token marks used_at and creates an auth_sessions row."""
        user_repo = UserRepository(db_session)
        token_repo = MagicLinkTokenRepository(db_session)
        session_repo = AuthSessionRepository(db_session)

        # Create user and magic link token
        user = await user_repo.create_user(email="test@example.com")
        raw_token = "magic_token_456"
        token_hash_value = hash_token(raw_token)
        magic_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value
        )
        await db_session.commit()

        # Consume the token
        retrieved_token = await token_repo.get_by_token_hash(token_hash_value)
        assert retrieved_token is not None
        assert retrieved_token.used_at is None

        # Mark as used
        await token_repo.mark_as_used(retrieved_token)

        # Create session
        session_token = "session_token_789"
        session_hash = hash_token(session_token)
        auth_session = await session_repo.create_session(
            user_id=user.id, token_hash=session_hash, expires_in_hours=24
        )
        await db_session.commit()

        # Verify token is marked as used
        assert retrieved_token.used_at is not None

        # Verify session is created
        assert auth_session.user_id == user.id
        assert auth_session.token_hash == session_hash
        assert auth_session.revoked_at is None
        assert auth_session.expires_at > datetime.now(timezone.utc)

    async def test_reuse_consumed_token_fails(self, db_session):
        """Re-using a consumed token is rejected."""
        user_repo = UserRepository(db_session)
        token_repo = MagicLinkTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        raw_token = "used_token_999"
        token_hash_value = hash_token(raw_token)
        magic_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value
        )
        await db_session.commit()

        # Mark token as used
        await token_repo.mark_as_used(magic_token)
        await db_session.commit()

        # Try to retrieve the used token
        retrieved_token = await token_repo.get_by_token_hash(token_hash_value)
        assert retrieved_token is None  # Should not be returned

    async def test_expired_token_fails(self, db_session):
        """Using an expired token is rejected."""
        user_repo = UserRepository(db_session)
        token_repo = MagicLinkTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        raw_token = "expired_token"
        token_hash_value = hash_token(raw_token)

        # Create token that expires immediately (negative minutes to simulate past)
        magic_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value, expires_in_minutes=-1
        )
        await db_session.commit()

        # Try to retrieve expired token
        retrieved_token = await token_repo.get_by_token_hash(token_hash_value)
        assert retrieved_token is None


@pytest.mark.asyncio
class TestPasswordResetFlow:
    """Test password reset flow."""

    async def test_create_password_reset_token(self, db_session):
        """Creating password_reset_tokens for a user succeeds."""
        user_repo = UserRepository(db_session)
        token_repo = PasswordResetTokenRepository(db_session)

        user = await user_repo.create_user(
            email="test@example.com", password_hash="old_hash"
        )
        raw_token = "reset_token_123"
        token_hash_value = hash_token(raw_token)

        reset_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value, expires_in_minutes=30
        )
        await db_session.commit()

        assert reset_token.user_id == user.id
        assert reset_token.token_hash == token_hash_value
        assert reset_token.used_at is None

    async def test_use_valid_token_updates_password(self, db_session):
        """Using a valid token updates password and sets used_at."""
        user_repo = UserRepository(db_session)
        token_repo = PasswordResetTokenRepository(db_session)

        user = await user_repo.create_user(
            email="test@example.com", password_hash="old_hash"
        )
        raw_token = "reset_token_456"
        token_hash_value = hash_token(raw_token)
        reset_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value
        )
        await db_session.commit()

        # Use token to reset password
        retrieved_token = await token_repo.get_by_token_hash(token_hash_value)
        assert retrieved_token is not None

        # Update password
        new_password_hash = hash_token("new_secure_password")
        await user_repo.update_password(user, new_password_hash)

        # Mark token as used
        await token_repo.mark_as_used(retrieved_token)
        await db_session.commit()

        # Verify password updated
        updated_user = await user_repo.get_by_id(user.id)
        assert updated_user.password_hash == new_password_hash

        # Verify token marked as used
        assert retrieved_token.used_at is not None

    async def test_reuse_password_reset_token_fails(self, db_session):
        """Re-using a used token is rejected."""
        user_repo = UserRepository(db_session)
        token_repo = PasswordResetTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        raw_token = "used_reset_token"
        token_hash_value = hash_token(raw_token)
        reset_token = await token_repo.create_token(
            user_id=user.id, token_hash=token_hash_value
        )
        await db_session.commit()

        # Mark as used
        await token_repo.mark_as_used(reset_token)
        await db_session.commit()

        # Try to retrieve used token
        retrieved_token = await token_repo.get_by_token_hash(token_hash_value)
        assert retrieved_token is None


@pytest.mark.asyncio
class TestQueryBehavior:
    """Test query behavior with soft deletes and indexes."""

    async def test_default_queries_exclude_soft_deleted(self, db_session):
        """Default repository queries exclude soft-deleted records."""
        user_repo = UserRepository(db_session)

        # Create two users
        user1 = await user_repo.create_user(email="active@example.com")
        user2 = await user_repo.create_user(email="deleted@example.com")
        await db_session.commit()

        # Soft delete user2
        await user_repo.soft_delete(user2)
        await db_session.commit()

        # List all users (should only return active)
        active_users = await user_repo.list_all(include_deleted=False)
        assert len(active_users) == 1
        assert active_users[0].email == "active@example.com"

    async def test_email_lookup_excludes_soft_deleted(self, db_session):
        """Lookups by email only return non-deleted users."""
        user_repo = UserRepository(db_session)

        email = "test@example.com"
        user = await user_repo.create_user(email=email)
        await db_session.commit()

        # Soft delete user
        await user_repo.soft_delete(user)
        await db_session.commit()

        # Try to find by email
        found_user = await user_repo.get_by_email(email, include_deleted=False)
        assert found_user is None

        # Should find when including deleted
        found_user_with_deleted = await user_repo.get_by_email(
            email, include_deleted=True
        )
        assert found_user_with_deleted is not None

    async def test_membership_queries_work_correctly(self, db_session):
        """Lookups by user_id/account_id work correctly when not deleted."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        account1 = await account_repo.create_account(account_type="personal")
        account2 = await account_repo.create_account(account_type="personal")

        membership1 = await membership_repo.create_membership(
            user_id=user.id, account_id=account1.id, role="owner"
        )
        membership2 = await membership_repo.create_membership(
            user_id=user.id, account_id=account2.id, role="member"
        )
        await db_session.commit()

        # Get all user memberships
        memberships = await membership_repo.get_user_memberships(user.id)
        assert len(memberships) == 2

        # Soft delete one membership
        await membership_repo.soft_delete(membership1)
        await db_session.commit()

        # Should only return active membership
        active_memberships = await membership_repo.get_user_memberships(
            user.id, include_deleted=False
        )
        assert len(active_memberships) == 1
        assert active_memberships[0].account_id == account2.id
