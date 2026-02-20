from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)  # Index for searching by title
    location = Column(String)
    posted_date = Column(String)
    salary = Column(String)  # Basic salary range from job posting
    is_active = Column(Boolean, default=True, index=True)  # Index for filtering active jobs
    requires_clearance = Column(Boolean, default=False)
    verified_at = Column(DateTime, default=datetime.utcnow)

    # User ownership - ties saved jobs to a specific user session
    session_user_id = Column(String, nullable=True, index=True)

    # Description from job posting
    description = Column(Text)
    requirements = Column(Text)

    # Perplexity salary research data
    median_salary = Column(String, nullable=True)  # Median salary from Perplexity
    salary_insights = Column(Text, nullable=True)  # Market insights and trends
    salary_sources = Column(Text, nullable=True)  # JSON array of citation URLs
    salary_last_updated = Column(DateTime, nullable=True)  # When salary data was researched

    # Relationships
    tailored_resumes = relationship("TailoredResume", back_populates="job", cascade="all, delete-orphan")
    company_research = relationship("CompanyResearch", back_populates="job", uselist=False, cascade="all, delete-orphan")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
