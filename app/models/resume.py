from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.database import Base

class BaseResume(Base):
    __tablename__ = "base_resumes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    # Parsed sections
    summary = Column(Text)
    skills = Column(Text)  # JSON string
    experience = Column(Text)  # JSON string of job entries
    education = Column(Text)
    certifications = Column(Text)

    # Metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tailored_resumes = relationship("TailoredResume", back_populates="base_resume")

class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id = Column(Integer, primary_key=True, index=True)
    base_resume_id = Column(Integer, ForeignKey("base_resumes.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    # Tailored sections
    tailored_summary = Column(Text)
    tailored_skills = Column(Text)  # JSON string
    tailored_experience = Column(Text)  # JSON string
    alignment_statement = Column(Text)  # Company values alignment

    # Quality metrics
    quality_score = Column(Float)  # 0-100
    changes_count = Column(Integer)  # Number of changes made

    # Export paths
    docx_path = Column(String)
    pdf_path = Column(String)

    # Relationships
    base_resume = relationship("BaseResume", back_populates="tailored_resumes")
    job = relationship("Job", back_populates="tailored_resumes")

    created_at = Column(DateTime, default=datetime.utcnow)
