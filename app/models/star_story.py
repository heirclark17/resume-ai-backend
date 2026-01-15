from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class StarStory(Base):
    """
    STAR Story model for storing detailed interview stories

    STAR = Situation, Task, Action, Result
    Used for behavioral interview preparation
    """
    __tablename__ = "star_stories"

    id = Column(Integer, primary_key=True, index=True)
    session_user_id = Column(String(255), nullable=False, index=True)  # User who created this story

    # Optional: Link to tailored resume if created from interview prep
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id"), nullable=True, index=True)

    # Story metadata
    title = Column(String(500), nullable=False)  # Brief story title
    story_theme = Column(String(500), nullable=True)  # Theme/category (e.g., "Leadership", "Problem Solving")
    company_context = Column(String(500), nullable=True)  # Company/role context if applicable

    # STAR components (TEXT allows for very long, detailed content)
    situation = Column(Text, nullable=False)  # Detailed context and background
    task = Column(Text, nullable=False)  # What needed to be accomplished
    action = Column(Text, nullable=False)  # Specific actions taken (most detailed)
    result = Column(Text, nullable=False)  # Quantifiable outcomes and impact

    # Supporting information
    key_themes = Column(JSON, default=list)  # ["Leadership", "Problem Solving", etc.]
    talking_points = Column(JSON, default=list)  # Key points to remember when telling story
    experience_indices = Column(JSON, default=list)  # Which resume experiences were used

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationship to tailored resume (optional)
    tailored_resume = relationship("TailoredResume", backref="star_stories", foreign_keys=[tailored_resume_id])

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "session_user_id": self.session_user_id,
            "tailored_resume_id": self.tailored_resume_id,
            "title": self.title,
            "story_theme": self.story_theme,
            "company_context": self.company_context,
            "situation": self.situation,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "key_themes": self.key_themes or [],
            "talking_points": self.talking_points or [],
            "experience_indices": self.experience_indices or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
