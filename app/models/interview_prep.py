from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class InterviewPrep(Base):
    __tablename__ = "interview_preps"

    id = Column(Integer, primary_key=True, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Complete interview prep data (JSON structure matching the schema)
    prep_data = Column(JSON, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    tailored_resume = relationship("TailoredResume", backref="interview_prep")
