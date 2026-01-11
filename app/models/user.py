from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import secrets

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)

    # Simple API key authentication (no passwords for now)
    api_key = Column(String, unique=True, nullable=False, index=True)

    # User metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    resumes = relationship("BaseResume", back_populates="user", cascade="all, delete-orphan")

    def generate_api_key(self) -> str:
        """Generate a secure random API key"""
        return secrets.token_urlsafe(32)

    @classmethod
    def create_user(cls, email: str, username: str):
        """Factory method to create user with API key"""
        user = cls(
            email=email,
            username=username,
            api_key=secrets.token_urlsafe(32)
        )
        return user
