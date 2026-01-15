from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class SavedComparison(Base):
    """
    Stores bookmarked resume comparisons for later viewing.
    Allows users to save and return to specific comparison sessions.
    """
    __tablename__ = "saved_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    session_user_id = Column(String, nullable=False, index=True)  # Session-based user identification

    # User-defined metadata
    title = Column(String, nullable=True)  # Optional custom title (e.g., "Google SWE Application")
    notes = Column(Text, nullable=True)  # User notes about this comparison
    tags = Column(Text, nullable=True)  # JSON array of tags (e.g., ["FAANG", "Senior", "Applied"])

    # AI Analysis Data (persisted from analysis endpoints)
    analysis_data = Column(Text, nullable=True)  # JSON: AI change analysis with section explanations
    keywords_data = Column(Text, nullable=True)  # JSON: Keyword extraction and matching results
    match_score_data = Column(Text, nullable=True)  # JSON: Overall match score and detailed breakdown

    # Status tracking
    is_pinned = Column(Boolean, default=False, index=True)  # Pin to top of list

    # Metadata
    saved_at = Column(DateTime, default=datetime.utcnow, index=True)  # When was it saved
    last_viewed_at = Column(DateTime, nullable=True)  # Last time user viewed this comparison

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    tailored_resume = relationship("TailoredResume", backref="saved_comparisons")


class TailoredResumeEdit(Base):
    """
    Stores user edits to tailored resume sections.
    Preserves AI-generated original while tracking user modifications.
    """
    __tablename__ = "tailored_resume_edits"

    id = Column(Integer, primary_key=True, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    session_user_id = Column(String, nullable=False, index=True)

    # What was edited
    section_name = Column(String, nullable=False)  # "summary", "skills", "experience", "alignment_statement"
    section_index = Column(Integer, nullable=True)  # For array sections like skills[0] or experience[1]

    # Edit details
    original_content = Column(Text, nullable=True)  # Content before edit (for undo)
    edited_content = Column(Text, nullable=False)  # New content after edit

    # Metadata
    edited_at = Column(DateTime, default=datetime.utcnow, index=True)
    edit_type = Column(String, nullable=True)  # "modify", "add", "delete"

    # Soft delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    tailored_resume = relationship("TailoredResume", backref="edits")
