from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class PracticeQuestionResponse(Base):
    """
    Stores user's practice question responses with recordings and AI-generated STAR stories
    """
    __tablename__ = "practice_question_responses"

    id = Column(Integer, primary_key=True, index=True)
    interview_prep_id = Column(Integer, ForeignKey("interview_preps.id", ondelete="CASCADE"), nullable=False, index=True)

    # Question details
    question_text = Column(Text, nullable=False)
    question_category = Column(String(100), nullable=True)  # behavioral, technical, situational, etc.

    # AI-generated STAR story for this question
    star_story = Column(JSON, nullable=True)  # {situation, task, action, result}

    # User's response recordings
    audio_recording_url = Column(Text, nullable=True)  # URL to stored audio file
    video_recording_url = Column(Text, nullable=True)  # URL to stored video file

    # User's written notes/answer
    written_answer = Column(Text, nullable=True)

    # Practice session metadata
    practice_duration_seconds = Column(Integer, nullable=True)
    times_practiced = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_practiced_at = Column(DateTime, nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    interview_prep = relationship("InterviewPrep", backref="practice_responses")
