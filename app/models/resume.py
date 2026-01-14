from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class BaseResume(Base):
    __tablename__ = "base_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # Nullable for migration
    session_user_id = Column(String, nullable=True, index=True)  # Session-based user identification (e.g., 'user_uuid')
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    # Candidate information (extracted from resume)
    candidate_name = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    candidate_phone = Column(String, nullable=True)
    candidate_location = Column(String, nullable=True)
    candidate_linkedin = Column(String, nullable=True)

    # Parsed sections
    summary = Column(Text)
    skills = Column(Text)  # JSON string
    experience = Column(Text)  # JSON string of job entries
    education = Column(Text)
    certifications = Column(Text)

    # Metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)  # Index for sorting by date
    file_signature = Column(String, nullable=True)  # HMAC-SHA256 signature for file integrity

    # Soft delete fields (audit trail)
    is_deleted = Column(Boolean, default=False, index=True)  # Index for filtering
    deleted_at = Column(DateTime, nullable=True)  # When was it deleted
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Who deleted it

    # Relationships
    user = relationship("User", back_populates="resumes", foreign_keys=[user_id])
    tailored_resumes = relationship("TailoredResume", back_populates="base_resume", cascade="all, delete-orphan")

class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id = Column(Integer, primary_key=True, index=True)
    base_resume_id = Column(Integer, ForeignKey("base_resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    session_user_id = Column(String, nullable=True, index=True)  # Session-based user identification

    # Tailored sections
    tailored_summary = Column(Text)
    tailored_skills = Column(Text)  # JSON string
    tailored_experience = Column(Text)  # JSON string
    alignment_statement = Column(Text)  # Company values alignment

    # Quality metrics
    quality_score = Column(Float, index=True)  # 0-100, indexed for filtering/sorting
    changes_count = Column(Integer)  # Number of changes made

    # Export paths
    docx_path = Column(String)
    pdf_path = Column(String)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # Index for sorting by date

    # Soft delete fields (audit trail)
    is_deleted = Column(Boolean, default=False, index=True)  # Index for filtering
    deleted_at = Column(DateTime, nullable=True)  # When was it deleted
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Who deleted it

    # Relationships
    base_resume = relationship("BaseResume", back_populates="tailored_resumes")
    job = relationship("Job", back_populates="tailored_resumes")
