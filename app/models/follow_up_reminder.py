from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from datetime import datetime
from app.database import Base


class FollowUpReminder(Base):
    __tablename__ = "follow_up_reminders"

    id = Column(Integer, primary_key=True, index=True)
    session_user_id = Column(String(255), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    reminder_date = Column(DateTime, nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=True)
    message = Column(Text, nullable=True)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "applicationId": self.application_id,
            "reminderDate": self.reminder_date.isoformat() if self.reminder_date else None,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "isSent": self.is_sent,
            "sentAt": self.sent_at.isoformat() if self.sent_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
