"""
Unit tests for database schema, constraints, and soft delete behavior.

Tests cover:
- Schema correctness and constraints
- Unique constraints (email, user+account membership)
- Soft delete behavior (no cascading)
- Foreign key relationships
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from database.models import User, Account, AccountMembership
from database.repositories import (
    UserRepository,
    AccountRepository,
    AccountMembershipRepository,
)


@pytest.mark.asyncio
class TestUserSchema:
    """Test User table schema and constraints."""

    async def test_create_user_with_email_and_password(self, db_session):
        """Creating a user with valid email and password hash succeeds."""
        repo = UserRepository(db_session)
        user = await repo.create_user(
            email="test@example.com", password_hash="hashed_password"
        )

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"
        assert user.deleted_at is None
        assert user.created_at is not None

    async def test_create_user_without_email_fails(self, db_session):
        """Creating a user without an email fails."""
        user = User(password_hash="hashed_password")
        db_session.add(user)

        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_duplicate_email_fails(self, db_session):
        """Creating two users with same email (case-insensitive) fails."""
        repo = UserRepository(db_session)
        await repo.create_user(email="test@example.com", password_hash="hash1")
        await db_session.commit()

        with pytest.raises(IntegrityError):
            await repo.create_user(email="TEST@EXAMPLE.COM", password_hash="hash2")
            await db_session.commit()
        await db_session.rollback()

    async def test_user_soft_delete_no_cascade(self, db_session):
        """Setting deleted_at on user does not cascade to other tables."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        # Create user, account, and membership
        user = await user_repo.create_user(email="test@example.com")
        account = await account_repo.create_account(account_type="personal")
        membership = await membership_repo.create_membership(
            user_id=user.id, account_id=account.id, role="owner"
        )
        await db_session.commit()

        # Soft delete user
        await user_repo.soft_delete(user)
        await db_session.commit()

        # Verify user is soft-deleted
        user_check = await user_repo.get_by_id(user.id, include_deleted=False)
        assert user_check is None

        # Verify account and membership are NOT deleted
        account_check = await account_repo.get_by_id(account.id)
        membership_check = await membership_repo.get_by_id(membership.id)
        assert account_check is not None
        assert membership_check is not None

    async def test_soft_deleted_users_remain_queryable(self, db_session):
        """Records with deleted_at remain physically present when explicitly queried."""
        repo = UserRepository(db_session)
        user = await repo.create_user(email="test@example.com")
        user_id = user.id
        await db_session.commit()

        # Soft delete
        await repo.soft_delete(user)
        await db_session.commit()

        # Should not be found in normal queries
        user_normal = await repo.get_by_id(user_id, include_deleted=False)
        assert user_normal is None

        # Should be found when including deleted
        user_deleted = await repo.get_by_id(user_id, include_deleted=True)
        assert user_deleted is not None
        assert user_deleted.deleted_at is not None


@pytest.mark.asyncio
class TestAccountSchema:
    """Test Account table schema and constraints."""

    async def test_create_account_with_type_succeeds(self, db_session):
        """Creating an account with account_type = 'personal' succeeds."""
        repo = AccountRepository(db_session)
        account = await repo.create_account(account_type="personal")

        assert account.id is not None
        assert account.account_type == "personal"
        assert account.parent_account_id is None
        assert account.deleted_at is None

    async def test_account_soft_delete_no_cascade(self, db_session):
        """Setting deleted_at on account does not cascade."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        # Create user, account, and membership
        user = await user_repo.create_user(email="test@example.com")
        account = await account_repo.create_account(account_type="personal")
        membership = await membership_repo.create_membership(
            user_id=user.id, account_id=account.id
        )
        await db_session.commit()

        # Soft delete account
        await account_repo.soft_delete(account)
        await db_session.commit()

        # Verify account is soft-deleted
        account_check = await account_repo.get_by_id(account.id, include_deleted=False)
        assert account_check is None

        # Verify user and membership are NOT deleted
        user_check = await user_repo.get_by_id(user.id)
        membership_check = await membership_repo.get_by_id(membership.id)
        assert user_check is not None
        assert membership_check is not None


@pytest.mark.asyncio
class TestAccountMembershipSchema:
    """Test AccountMembership table schema and constraints."""

    async def test_create_membership_succeeds(self, db_session):
        """Creating account_memberships with valid data succeeds."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        account = await account_repo.create_account(account_type="personal")
        membership = await membership_repo.create_membership(
            user_id=user.id, account_id=account.id, role="owner"
        )
        await db_session.commit()

        assert membership.id is not None
        assert membership.user_id == user.id
        assert membership.account_id == account.id
        assert membership.role == "owner"
        assert membership.deleted_at is None

    async def test_duplicate_membership_fails(self, db_session):
        """Creating memberships with same (user_id, account_id) twice fails."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        account = await account_repo.create_account(account_type="personal")
        await membership_repo.create_membership(
            user_id=user.id, account_id=account.id, role="owner"
        )
        await db_session.commit()

        # Try to create duplicate membership
        with pytest.raises(IntegrityError):
            await membership_repo.create_membership(
                user_id=user.id, account_id=account.id, role="member"
            )
            await db_session.commit()
        await db_session.rollback()

    async def test_membership_soft_delete_no_cascade(self, db_session):
        """Setting deleted_at on membership does not cascade."""
        user_repo = UserRepository(db_session)
        account_repo = AccountRepository(db_session)
        membership_repo = AccountMembershipRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        account = await account_repo.create_account(account_type="personal")
        membership = await membership_repo.create_membership(
            user_id=user.id, account_id=account.id
        )
        await db_session.commit()

        # Soft delete membership
        await membership_repo.soft_delete(membership)
        await db_session.commit()

        # Verify membership is soft-deleted
        membership_check = await membership_repo.get_by_id(
            membership.id, include_deleted=False
        )
        assert membership_check is None

        # Verify user and account are NOT deleted
        user_check = await user_repo.get_by_id(user.id)
        account_check = await account_repo.get_by_id(account.id)
        assert user_check is not None
        assert account_check is not None


@pytest.mark.asyncio
class TestAuthTablesSchema:
    """Test auth tables schema and constraints."""

    async def test_auth_session_token_hash_unique(self, db_session):
        """auth_sessions.token_hash is unique."""
        from database.repositories import AuthSessionRepository

        user_repo = UserRepository(db_session)
        session_repo = AuthSessionRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        await session_repo.create_session(
            user_id=user.id, token_hash="hash123", expires_in_hours=24
        )
        await db_session.commit()

        # Try to create another session with same token hash
        with pytest.raises(IntegrityError):
            await session_repo.create_session(
                user_id=user.id, token_hash="hash123", expires_in_hours=24
            )
            await db_session.commit()
        await db_session.rollback()

    async def test_magic_link_token_hash_unique(self, db_session):
        """magic_link_tokens.token_hash is unique."""
        from database.repositories import MagicLinkTokenRepository

        user_repo = UserRepository(db_session)
        token_repo = MagicLinkTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        await token_repo.create_token(
            user_id=user.id, token_hash="hash456", expires_in_minutes=15
        )
        await db_session.commit()

        # Try to create another token with same hash
        with pytest.raises(IntegrityError):
            await token_repo.create_token(
                user_id=user.id, token_hash="hash456", expires_in_minutes=15
            )
            await db_session.commit()
        await db_session.rollback()

    async def test_password_reset_token_hash_unique(self, db_session):
        """password_reset_tokens.token_hash is unique."""
        from database.repositories import PasswordResetTokenRepository

        user_repo = UserRepository(db_session)
        token_repo = PasswordResetTokenRepository(db_session)

        user = await user_repo.create_user(email="test@example.com")
        await token_repo.create_token(
            user_id=user.id, token_hash="hash789", expires_in_minutes=30
        )
        await db_session.commit()

        # Try to create another token with same hash
        with pytest.raises(IntegrityError):
            await token_repo.create_token(
                user_id=user.id, token_hash="hash789", expires_in_minutes=30
            )
            await db_session.commit()
        await db_session.rollback()
