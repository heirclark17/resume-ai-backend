from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import secrets
import bcrypt

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=True, index=True)  # Make nullable for Supabase users

    # Supabase authentication
    supabase_id = Column(String, unique=True, nullable=True, index=True)  # Supabase user ID

    # Simple API key authentication (legacy, optional for Supabase users)
    api_key = Column(String, unique=True, nullable=True, index=True)
    api_key_prefix = Column(String(8), nullable=True, index=True)  # First 8 chars for O(1) lookup

    # User metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Two-Factor Authentication (2FA)
    totp_secret = Column(String, nullable=True)  # TOTP secret key (encrypted)
    twofa_enabled = Column(Boolean, default=False)  # Is 2FA enabled
    twofa_backup_codes = Column(String, nullable=True)  # Encrypted backup codes (JSON)

    # Relationships
    resumes = relationship("BaseResume", back_populates="user", foreign_keys="[BaseResume.user_id]", cascade="all, delete-orphan")

    def generate_api_key(self) -> str:
        """Generate a secure random API key"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(api_key.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """Return first 8 chars of plaintext key for O(1) lookup"""
        return api_key[:8]

    @staticmethod
    def verify_api_key(api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash"""
        try:
            return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))
        except Exception:
            return False

    @classmethod
    def create_user(cls, email: str, username: str):
        """Factory method to create user with hashed API key"""
        # Generate plaintext key (to return to user)
        plaintext_key = secrets.token_urlsafe(32)

        # Store hashed version in database with prefix for O(1) lookup
        user = cls(
            email=email,
            username=username,
            api_key=cls.hash_api_key(plaintext_key),
            api_key_prefix=cls.get_key_prefix(plaintext_key)
        )

        # Attach plaintext key for one-time return (not stored)
        user._plaintext_api_key = plaintext_key
        return user
