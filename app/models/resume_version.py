from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from datetime import datetime
from app.database import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id"), index=True)
    session_user_id = Column(String(255), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "tailoredResumeId": self.tailored_resume_id,
            "versionNumber": self.version_number,
            "changeSummary": self.change_summary,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
