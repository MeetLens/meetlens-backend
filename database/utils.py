"""
Database utility functions.

Provides common helper functions for password hashing, token generation,
and other database-related operations.
"""
import hashlib
import secrets
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Number of bytes for the token (default 32)

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256.

    Args:
        token: Plain text token to hash

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_and_hash_token(length: int = 32) -> tuple[str, str]:
    """
    Generate a token and return both the plain and hashed versions.

    Args:
        length: Number of bytes for the token

    Returns:
        Tuple of (plain_token, hashed_token)
    """
    plain_token = generate_token(length)
    hashed_token = hash_token(plain_token)
    return plain_token, hashed_token
