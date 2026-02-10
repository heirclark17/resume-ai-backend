from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime
from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    session_user_id = Column(String(255), nullable=False, index=True)
    job_title = Column(String(500), nullable=False)
    company_name = Column(String(500), nullable=False)
    job_url = Column(Text, nullable=True)
    status = Column(String(50), default="saved", index=True)
    applied_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    tailored_resume_id = Column(Integer, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    location = Column(String(500), nullable=True)
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    next_follow_up = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "jobTitle": self.job_title,
            "companyName": self.company_name,
            "jobUrl": self.job_url,
            "status": self.status,
            "appliedDate": self.applied_date.isoformat() if self.applied_date else None,
            "notes": self.notes,
            "tailoredResumeId": self.tailored_resume_id,
            "salaryMin": self.salary_min,
            "salaryMax": self.salary_max,
            "location": self.location,
            "contactName": self.contact_name,
            "contactEmail": self.contact_email,
            "nextFollowUp": self.next_follow_up.isoformat() if self.next_follow_up else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
