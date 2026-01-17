"""
SQLAlchemy model for Career Plans
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class CareerPlan(Base):
    __tablename__ = "career_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # For future auth integration
    session_user_id = Column(String(255), nullable=False, index=True)  # Session-based user ID

    # Intake data (user input)
    intake_json = Column(JSON, nullable=False)

    # Research data (Perplexity web-grounded facts)
    research_json = Column(JSON, nullable=True)

    # Complete plan (OpenAI synthesized output)
    plan_json = Column(JSON, nullable=False)

    # Metadata
    version = Column(String(10), default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<CareerPlan(id={self.id}, session_user={self.session_user_id}, version={self.version})>"
