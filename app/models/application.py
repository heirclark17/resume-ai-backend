from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Application(Base):
    """
    Application tracking model
    Tracks job applications through the hiring pipeline
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)  # User who created the application

    # Job details
    job_title = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False, index=True)
    job_url = Column(String)
    location = Column(String)

    # Salary range
    salary_min = Column(Integer)
    salary_max = Column(Integer)

    # Application status pipeline
    # Statuses: 'saved', 'applied', 'screening', 'interviewing', 'offer', 'accepted', 'rejected', 'withdrawn', 'no_response'
    status = Column(String, nullable=False, default='saved', index=True)

    # Dates
    applied_date = Column(Date)
    next_follow_up = Column(Date, index=True)  # Index for reminder queries

    # Contact information
    contact_name = Column(String)
    contact_email = Column(String)

    # Notes
    notes = Column(Text)

    # Foreign keys
    tailored_resume_id = Column(Integer, ForeignKey('tailored_resumes.id'), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # tailored_resume = relationship("TailoredResume", back_populates="applications")
