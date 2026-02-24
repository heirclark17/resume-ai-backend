"""
SalaryCache Model - Cross-job persistent salary data cache

Caches Perplexity salary research by (company, job_title, location) rather
than by job URL. This means a "Software Engineer" at "Google" in "Remote"
only ever triggers one Perplexity API call regardless of how many different
job URLs are used. Cache expires after 30 days and is then re-fetched.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint, Index
from datetime import datetime, timedelta
from app.database import Base


SALARY_CACHE_TTL_DAYS = 30


class SalaryCache(Base):
    """
    Persistent salary data cache keyed on (company, job_title, location).

    Unique constraint on (company, job_title, location) ensures only one row
    per logical salary lookup. The updated_at column tracks when Perplexity
    was last queried so callers can display "Last updated X days ago".
    """

    __tablename__ = "salary_cache"

    id = Column(Integer, primary_key=True, index=True)

    # Cache key fields (normalized to lowercase on insert)
    company = Column(String(255), nullable=False, index=True)
    job_title = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True, index=True)

    # Salary data from Perplexity
    median_salary = Column(String(100), nullable=True)
    salary_range = Column(String(200), nullable=True)
    market_insights = Column(Text, nullable=True)
    sources = Column(Text, nullable=True)  # JSON-serialized list of citation URLs

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Composite unique constraint - one row per (company, title, location) triple
    __table_args__ = (
        UniqueConstraint("company", "job_title", "location", name="uq_salary_cache_key"),
        Index("ix_salary_cache_lookup", "company", "job_title", "location"),
    )

    # ------------------------------------------------------------------
    # Class helpers
    # ------------------------------------------------------------------

    @classmethod
    def make_key(cls, company: str, job_title: str, location: str = None) -> tuple:
        """
        Normalize and return the lookup key tuple.
        Lowercasing prevents 'Google' vs 'google' duplicates.
        """
        return (
            (company or "").strip().lower(),
            (job_title or "").strip().lower(),
            (location or "").strip().lower() if location else None,
        )

    def is_expired(self) -> bool:
        """Return True if the cached data is older than SALARY_CACHE_TTL_DAYS."""
        cutoff = datetime.utcnow() - timedelta(days=SALARY_CACHE_TTL_DAYS)
        return self.updated_at < cutoff

    def days_old(self) -> int:
        """Return the integer number of days since last update."""
        delta = datetime.utcnow() - self.updated_at
        return delta.days

    def to_salary_dict(self) -> dict:
        """
        Return salary data in the same shape that Perplexity returns,
        plus cache-metadata fields the frontend uses.
        """
        import json

        try:
            sources = json.loads(self.sources) if self.sources else []
        except (TypeError, ValueError):
            sources = []

        return {
            "salary_range": self.salary_range or "Data not available",
            "median_salary": self.median_salary or "Data not available",
            "market_insights": self.market_insights or "",
            "sources": sources,
            "last_updated": self.updated_at.isoformat(),
            "cache_updated_at": self.updated_at.isoformat(),
            "days_old": self.days_old(),
            "from_cache": True,
        }
