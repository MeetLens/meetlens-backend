"""
Repository layer for database operations.

Provides data access layer with automatic soft delete filtering
and common CRUD operations for all entities.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, TypeVar, Generic, Type
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User,
    Account,
    AccountMembership,
    AuthSession,
    MagicLinkToken,
    PasswordResetToken,
)

T = TypeVar("T")

def utcnow() -> datetime:
    """Timezone-aware UTC 'now' for TIMESTAMPTZ columns."""
    return datetime.now(timezone.utc)


class BaseRepository(Generic[T]):
    """
    Base repository with soft delete support.

    All queries automatically filter out soft-deleted records unless
    explicitly requested via include_deleted=True.
    """

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_by_id(
        self, id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[T]:
        """Get entity by ID, excluding soft-deleted by default."""
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, limit: int = 100, offset: int = 0, include_deleted: bool = False
    ) -> List[T]:
        """List all entities, excluding soft-deleted by default."""
        stmt = select(self.model)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entity: T) -> T:
        """Soft delete an entity by setting deleted_at."""
        if hasattr(entity, "deleted_at"):
            entity.deleted_at = utcnow()
            await self.session.flush()
            await self.session.refresh(entity)
        return entity

    async def hard_delete(self, entity: T) -> None:
        """Permanently delete an entity (use with caution)."""
        await self.session.delete(entity)
        await self.session.flush()


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(
        self, email: str, include_deleted: bool = False
    ) -> Optional[User]:
        """Get user by email (case-insensitive)."""
        stmt = select(User).where(User.email == email.lower())
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self, email: str, password_hash: Optional[str] = None
    ) -> User:
        """Create a new user."""
        user = User(email=email.lower(), password_hash=password_hash)
        return await self.create(user)

    async def verify_email(self, user: User) -> User:
        """Mark user's email as verified."""
        user.email_verified_at = utcnow()
        return await self.update(user)

    async def update_password(self, user: User, password_hash: str) -> User:
        """Update user's password hash."""
        user.password_hash = password_hash
        return await self.update(user)


class AccountRepository(BaseRepository[Account]):
    """Repository for Account operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Account)

    async def create_account(
        self,
        account_type: str = "personal",
        parent_account_id: Optional[uuid.UUID] = None,
    ) -> Account:
        """Create a new account."""
        account = Account(
            account_type=account_type, parent_account_id=parent_account_id
        )
        return await self.create(account)

    async def get_by_type(
        self, account_type: str, include_deleted: bool = False
    ) -> List[Account]:
        """Get all accounts of a specific type."""
        stmt = select(Account).where(Account.account_type == account_type)
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AccountMembershipRepository(BaseRepository[AccountMembership]):
    """Repository for AccountMembership operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AccountMembership)

    async def create_membership(
        self, user_id: uuid.UUID, account_id: uuid.UUID, role: str = "owner"
    ) -> AccountMembership:
        """Create a new account membership."""
        membership = AccountMembership(
            user_id=user_id, account_id=account_id, role=role
        )
        return await self.create(membership)

    async def get_by_user_and_account(
        self, user_id: uuid.UUID, account_id: uuid.UUID, include_deleted: bool = False
    ) -> Optional[AccountMembership]:
        """Get membership for specific user and account."""
        stmt = select(AccountMembership).where(
            and_(
                AccountMembership.user_id == user_id,
                AccountMembership.account_id == account_id,
            )
        )
        if not include_deleted:
            stmt = stmt.where(AccountMembership.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_memberships(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> List[AccountMembership]:
        """Get all memberships for a user."""
        stmt = select(AccountMembership).where(AccountMembership.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(AccountMembership.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_account_memberships(
        self, account_id: uuid.UUID, include_deleted: bool = False
    ) -> List[AccountMembership]:
        """Get all memberships for an account."""
        stmt = select(AccountMembership).where(
            AccountMembership.account_id == account_id
        )
        if not include_deleted:
            stmt = stmt.where(AccountMembership.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AuthSessionRepository(BaseRepository[AuthSession]):
    """Repository for AuthSession operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AuthSession)

    async def create_session(
        self, user_id: uuid.UUID, token_hash: str, expires_in_hours: int = 24
    ) -> AuthSession:
        """Create a new auth session."""
        session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(hours=expires_in_hours),
        )
        return await self.create(session)

    async def get_by_token_hash(self, token_hash: str) -> Optional[AuthSession]:
        """Get session by token hash."""
        stmt = select(AuthSession).where(
            and_(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > utcnow(),
                AuthSession.revoked_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_session(self, session: AuthSession) -> AuthSession:
        """Revoke an auth session."""
        session.revoked_at = utcnow()
        return await self.update(session)

    async def get_user_sessions(
        self, user_id: uuid.UUID, active_only: bool = True
    ) -> List[AuthSession]:
        """Get all sessions for a user."""
        stmt = select(AuthSession).where(AuthSession.user_id == user_id)
        if active_only:
            stmt = stmt.where(
                and_(
                    AuthSession.expires_at > utcnow(),
                    AuthSession.revoked_at.is_(None),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class MagicLinkTokenRepository(BaseRepository[MagicLinkToken]):
    """Repository for MagicLinkToken operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, MagicLinkToken)

    async def create_token(
        self, user_id: uuid.UUID, token_hash: str, expires_in_minutes: int = 15
    ) -> MagicLinkToken:
        """Create a new magic link token."""
        token = MagicLinkToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=expires_in_minutes),
        )
        return await self.create(token)

    async def get_by_token_hash(self, token_hash: str) -> Optional[MagicLinkToken]:
        """Get valid (unused, non-expired) magic link token."""
        stmt = select(MagicLinkToken).where(
            and_(
                MagicLinkToken.token_hash == token_hash,
                MagicLinkToken.expires_at > utcnow(),
                MagicLinkToken.used_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_as_used(self, token: MagicLinkToken) -> MagicLinkToken:
        """Mark token as used."""
        token.used_at = utcnow()
        return await self.update(token)


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    """Repository for PasswordResetToken operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PasswordResetToken)

    async def create_token(
        self, user_id: uuid.UUID, token_hash: str, expires_in_minutes: int = 30
    ) -> PasswordResetToken:
        """Create a new password reset token."""
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=expires_in_minutes),
        )
        return await self.create(token)

    async def get_by_token_hash(
        self, token_hash: str
    ) -> Optional[PasswordResetToken]:
        """Get valid (unused, non-expired) password reset token."""
        stmt = select(PasswordResetToken).where(
            and_(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.expires_at > utcnow(),
                PasswordResetToken.used_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_as_used(self, token: PasswordResetToken) -> PasswordResetToken:
        """Mark token as used."""
        token.used_at = utcnow()
        return await self.update(token)
