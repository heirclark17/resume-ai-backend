from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime
from app.database import Base


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id = Column(Integer, primary_key=True, index=True)
    session_user_id = Column(String(255), nullable=False, index=True)
    tailored_resume_id = Column(Integer, nullable=True)
    job_title = Column(String(500))
    company_name = Column(String(500))
    job_description = Column(Text, nullable=True)
    tone = Column(String(50), default="professional")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tailoredResumeId": self.tailored_resume_id,
            "jobTitle": self.job_title,
            "companyName": self.company_name,
            "tone": self.tone,
            "content": self.content,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
