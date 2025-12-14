"""
SQLAlchemy ORM models for MeetLens database.

All models follow the design principles from the PRD:
- Account-centric architecture
- Soft delete everywhere (deleted_at column)
- No cascading deletes
- PostgreSQL-native features (UUID, CITEXT, TIMESTAMPTZ)
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Text, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, CITEXT, TIMESTAMP
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database.config import Base


class User(Base):
    """
    User identity and authentication metadata.

    A User may belong to multiple Accounts via AccountMembership.
    In MVP, each user gets one personal account auto-created.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships (use lazy='selectin' for async compatibility)
    memberships: Mapped[List["AccountMembership"]] = relationship(
        "AccountMembership",
        back_populates="user",
        lazy="selectin"
    )
    auth_sessions: Mapped[List["AuthSession"]] = relationship(
        "AuthSession",
        back_populates="user",
        lazy="selectin"
    )
    magic_link_tokens: Mapped[List["MagicLinkToken"]] = relationship(
        "MagicLinkToken",
        back_populates="user",
        lazy="selectin"
    )
    password_reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        lazy="selectin"
    )

    __table_args__ = (
        Index(
            "ix_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        ),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Account(Base):
    """
    Logical owner of all product resources.

    In MVP, only 'personal' account_type is used.
    parent_account_id is reserved for future workspace/reseller features.
    """
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    parent_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[List["AccountMembership"]] = relationship(
        "AccountMembership",
        back_populates="account",
        lazy="selectin"
    )

    __table_args__ = (
        Index(
            "ix_accounts_id_active",
            "id",
            postgresql_where=text("deleted_at IS NULL")
        ),
        Index("ix_accounts_account_type", "account_type"),
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, type={self.account_type})>"


class AccountMembership(Base):
    """
    Join table linking Users to Accounts.

    Enforces unique (user_id, account_id) constraint for active memberships.
    No cascading deletes - orphaned records are allowed.
    """
    __tablename__ = "account_memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memberships", lazy="selectin")
    account: Mapped["Account"] = relationship("Account", back_populates="memberships", lazy="selectin")

    __table_args__ = (
        Index(
            "ix_account_memberships_user_account_active",
            "user_id",
            "account_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        ),
        Index("ix_account_memberships_user_id", "user_id"),
        Index("ix_account_memberships_account_id", "account_id"),
    )

    def __repr__(self) -> str:
        return f"<AccountMembership(user_id={self.user_id}, account_id={self.account_id}, role={self.role})>"


class AuthSession(Base):
    """
    Active login sessions / refresh tokens.

    Stores hashed tokens only. Can be revoked via revoked_at timestamp.
    """
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auth_sessions", lazy="selectin")

    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
        Index("ix_auth_sessions_token_hash", "token_hash", unique=True),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<AuthSession(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


class MagicLinkToken(Base):
    """
    One-time login tokens for passwordless authentication.

    Tokens are hashed and can only be used once (tracked via used_at).
    """
    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="magic_link_tokens", lazy="selectin")

    __table_args__ = (
        Index("ix_magic_link_tokens_user_id", "user_id"),
        Index("ix_magic_link_tokens_token_hash", "token_hash", unique=True),
        Index("ix_magic_link_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<MagicLinkToken(id={self.id}, user_id={self.user_id}, used_at={self.used_at})>"


class PasswordResetToken(Base):
    """
    Password reset flow tokens.

    One-time tokens for secure password reset operations.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()")
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens", lazy="selectin")

    __table_args__ = (
        Index("ix_password_reset_tokens_user_id", "user_id"),
        Index("ix_password_reset_tokens_token_hash", "token_hash", unique=True),
        Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, used_at={self.used_at})>"
