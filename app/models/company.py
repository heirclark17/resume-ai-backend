from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class CompanyResearch(Base):
    __tablename__ = "company_research"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    # 5-step research results
    mission_values = Column(Text)  # Step 1
    initiatives = Column(Text)     # Step 2
    team_culture = Column(Text)    # Step 3
    compliance = Column(Text)      # Step 4
    tech_stack = Column(Text)      # Step 5

    # Sources/citations from Perplexity
    sources = Column(JSON)  # List of URLs

    # Industry detection
    industry = Column(String)  # financial, healthcare, federal, tech, consulting

    # Cache metadata
    researched_at = Column(DateTime, default=datetime.utcnow)
    cache_expires_at = Column(DateTime)  # 30 days from research

    # Relationships
    job = relationship("Job", back_populates="company_research")

    created_at = Column(DateTime, default=datetime.utcnow)
