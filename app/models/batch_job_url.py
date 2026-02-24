from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class BatchJobUrl(Base):
    __tablename__ = "batch_job_urls"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    session_user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
