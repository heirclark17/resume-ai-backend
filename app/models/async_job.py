"""
SQLAlchemy model for the async_jobs table — durable PostgreSQL-backed job queue.
Replaces the in-memory JobStore.
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.database import Base
import uuid


class AsyncJob(Base):
    __tablename__ = "async_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False, index=True)
    job_type = Column(String(100), nullable=False, index=True)

    # Status: pending → processing → completed | failed
    status = Column(String(20), nullable=False, default="pending", index=True)
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    message = Column(String(500), nullable=True, default="Queued")

    # Payload and result
    input_data = Column(JSON, nullable=True)
    result_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Retry tracking
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
