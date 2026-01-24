"""
Analysis Cache Model - Stores AI analysis results for fast retrieval

Caches resume analysis, keyword analysis, and match score results
with 30-day TTL to avoid expensive repeated AI calls.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.database import Base


class AnalysisCache(Base):
    """
    Cache for AI-generated analysis results.
    Each tailored resume can have cached results for:
    - changes: Resume change analysis
    - keywords: Keyword extraction analysis
    - match_score: Job match score calculation
    """
    __tablename__ = "analysis_cache"

    id = Column(Integer, primary_key=True, index=True)
    tailored_resume_id = Column(Integer, ForeignKey("tailored_resumes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Type of analysis cached
    analysis_type = Column(String(50), nullable=False, index=True)  # "changes", "keywords", "match_score", "all"

    # Cached result data
    result_data = Column(JSON, nullable=False)

    # Cache metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Version tracking for cache invalidation
    version = Column(Integer, default=1)

    # Relationships
    tailored_resume = relationship("TailoredResume", backref="analysis_caches")

    @classmethod
    def create_with_ttl(cls, tailored_resume_id: int, analysis_type: str, result_data: dict, ttl_days: int = 30):
        """Create a cache entry with TTL"""
        return cls(
            tailored_resume_id=tailored_resume_id,
            analysis_type=analysis_type,
            result_data=result_data,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days)
        )

    def is_valid(self) -> bool:
        """Check if cache entry is still valid"""
        return datetime.utcnow() < self.expires_at
