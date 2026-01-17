"""
Pydantic schemas for Career Path Designer
Defines the comprehensive CareerPlan structure with strict validation
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


# ========== Intake Schemas ==========
class IntakeRequest(BaseModel):
    """User input for career path planning"""
    current_role_title: str = Field(..., min_length=2, max_length=200)
    current_industry: str = Field(..., min_length=2, max_length=200)
    years_experience: float = Field(..., ge=0, le=50)
    top_tasks: List[str] = Field(..., min_items=3, max_items=10)
    tools: List[str] = Field(default_factory=list, max_items=20)
    strengths: List[str] = Field(..., min_items=2, max_items=10)
    likes: List[str] = Field(default_factory=list, max_items=10)
    dislikes: List[str] = Field(default_factory=list, max_items=10)
    target_role_interest: Optional[str] = Field(None, max_length=200)
    time_per_week: int = Field(..., ge=1, le=168, description="Hours per week available")
    budget: str = Field(..., description="Budget range: low/medium/high or specific amount")
    timeline: str = Field(..., description="Timeline: 3months/6months/12months")
    education_level: str = Field(..., description="Current education: high school/associates/bachelors/masters/phd")
    location: str = Field(..., description="City, State or Country")
    in_person_vs_remote: str = Field(..., description="Preference: in-person/remote/hybrid")


# ========== Target Role Schemas ==========
class BridgeRole(BaseModel):
    """Intermediate stepping stone role"""
    title: str
    why_good_fit: str
    time_to_qualify: str
    key_gaps_to_close: List[str]


class TargetRole(BaseModel):
    """A career target with supporting data"""
    title: str
    why_aligned: str = Field(..., description="Why this matches user background")
    growth_outlook: str = Field(..., description="Job market outlook data")
    salary_range: str
    typical_requirements: List[str]
    bridge_roles: List[BridgeRole] = Field(default_factory=list, max_items=2)
    source_citations: List[str] = Field(default_factory=list, description="Web-grounded sources")


# ========== Skills Mapping Schemas ==========
class TransferableSkill(BaseModel):
    """Skills the user already has"""
    skill_name: str
    evidence_from_input: str = Field(..., description="What in intake shows this")
    target_role_mapping: str = Field(..., description="How this applies to target role")
    resume_bullets: List[str] = Field(..., min_items=1, max_items=3)


class ReframableSkill(BaseModel):
    """Skills user has but needs to reposition"""
    skill_name: str
    current_context: str
    target_context: str
    how_to_reframe: str
    resume_bullets: List[str] = Field(..., min_items=1, max_items=2)


class GapSkill(BaseModel):
    """Skills user needs to build"""
    skill_name: str
    why_needed: str
    priority: str = Field(..., description="critical/high/medium")
    how_to_build: str
    estimated_time: str


class SkillsAnalysis(BaseModel):
    """Complete skills breakdown"""
    already_have: List[TransferableSkill] = Field(..., min_items=3)
    can_reframe: List[ReframableSkill] = Field(default_factory=list)
    need_to_build: List[GapSkill] = Field(..., min_items=1)


# ========== Certification Schemas ==========
class Certification(BaseModel):
    """A specific certification with real data"""
    name: str
    level: str = Field(..., description="foundation/intermediate/advanced")
    prerequisites: List[str] = Field(default_factory=list)
    est_study_weeks: int = Field(..., ge=1, le=104)
    est_cost_range: str
    official_links: List[str] = Field(..., min_items=1, description="ONLY web-grounded URLs")
    what_it_unlocks: str
    alternatives: List[str] = Field(default_factory=list)
    source_citations: List[str] = Field(..., min_items=1)


# ========== Education Schemas ==========
class EducationOption(BaseModel):
    """Degree, bootcamp, or self-study path"""
    type: str = Field(..., description="degree/bootcamp/self-study/online-course")
    name: str
    duration: str
    cost_range: str
    format: str = Field(..., description="online/in-person/hybrid")
    official_link: Optional[str] = None
    pros: List[str] = Field(..., min_items=1, max_items=5)
    cons: List[str] = Field(..., min_items=1, max_items=5)
    source_citations: List[str] = Field(default_factory=list)


# ========== Experience Builder Schemas ==========
class ExperienceProject(BaseModel):
    """Portfolio project, volunteer work, or lab"""
    type: str = Field(..., description="portfolio/volunteer/lab/side-project/freelance")
    title: str
    description: str
    skills_demonstrated: List[str] = Field(..., min_items=1)
    time_commitment: str
    how_to_showcase: str = Field(..., description="How to present on resume/LinkedIn")
    example_resources: List[str] = Field(default_factory=list)


# ========== Events Schemas ==========
class Event(BaseModel):
    """Real networking/learning event with verified data"""
    name: str
    type: str = Field(..., description="conference/meetup/virtual/career-fair/workshop")
    date_or_season: str
    location: str
    price_range: str
    beginner_friendly: bool
    why_attend: str
    registration_link: str = Field(..., description="MUST be web-grounded, not hallucinated")
    source_citations: List[str] = Field(..., min_items=1, description="Where this data came from")


# ========== Timeline Schemas ==========
class WeeklyTask(BaseModel):
    """Tasks for a specific week"""
    week_number: int = Field(..., ge=1, le=52)
    tasks: List[str] = Field(..., min_items=1, max_items=5)
    milestone: Optional[str] = None
    checkpoint: Optional[str] = Field(None, description="Apply-ready milestone")


class MonthlyPhase(BaseModel):
    """Tasks for a specific month"""
    month_number: int = Field(..., ge=1, le=12)
    phase_name: str
    goals: List[str] = Field(..., min_items=1, max_items=4)
    deliverables: List[str] = Field(..., min_items=1)
    checkpoint: Optional[str] = None


class Timeline(BaseModel):
    """12-week and 6-month plans"""
    twelve_week_plan: List[WeeklyTask] = Field(..., min_items=12, max_items=12)
    six_month_plan: List[MonthlyPhase] = Field(..., min_items=6, max_items=6)
    apply_ready_checkpoint: str = Field(..., description="When user can start applying")


# ========== Resume Assets Schemas ==========
class ResumeAssets(BaseModel):
    """AI-generated resume content aligned to the plan"""
    headline: str = Field(..., max_length=200)
    summary: str = Field(..., min_length=100, max_length=1000)
    skills_section: List[str] = Field(..., min_items=8, max_items=20)
    target_role_bullets: List[str] = Field(..., min_items=6, max_items=10, description="Achievement bullets")
    keywords_for_ats: List[str] = Field(..., min_items=10)


# ========== Complete Career Plan Schema ==========
class CareerPlan(BaseModel):
    """The master schema for the entire career plan"""
    # Metadata
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = Field(default="1.0")

    # Core sections
    profile_summary: str = Field(..., min_length=100, max_length=500)
    target_roles: List[TargetRole] = Field(..., min_items=1, max_items=6)
    skills_analysis: SkillsAnalysis
    certification_path: List[Certification] = Field(..., min_items=1, max_items=8)
    education_options: List[EducationOption] = Field(..., min_items=1, max_items=5)
    experience_plan: List[ExperienceProject] = Field(..., min_items=2, max_items=10)
    events: List[Event] = Field(..., min_items=3, max_items=15)
    timeline: Timeline
    resume_assets: ResumeAssets

    # Source tracking
    research_sources: List[str] = Field(..., min_items=3, description="All web-grounded sources")


# ========== API Request/Response Schemas ==========
class ResearchRequest(BaseModel):
    """Request for Perplexity research phase"""
    target_roles: List[str] = Field(..., min_items=1, max_items=6)
    location: str
    education_level: str
    budget: str


class ResearchResponse(BaseModel):
    """Web-grounded facts from Perplexity"""
    certifications: List[Certification]
    education_options: List[EducationOption]
    events: List[Event]
    research_sources: List[str]


class GenerateRequest(BaseModel):
    """Request to generate full career plan"""
    intake: IntakeRequest
    research_data: Optional[ResearchResponse] = None


class GenerateResponse(BaseModel):
    """Response with complete career plan"""
    success: bool
    plan: Optional[CareerPlan] = None
    plan_id: Optional[int] = None
    error: Optional[str] = None


class RefreshEventsRequest(BaseModel):
    """Request to refresh events without regenerating plan"""
    plan_id: int
    location: str


class CareerPlanListItem(BaseModel):
    """Summary for listing career plans"""
    id: int
    target_roles: List[str]
    created_at: str
    updated_at: str
    version: str


# ========== Validation Schemas ==========
class ValidationError(BaseModel):
    """Schema validation error details"""
    field: str
    error: str
    expected: str
    received: Any


class ValidationResult(BaseModel):
    """Result of schema validation"""
    valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    repaired: bool = False
    repaired_json: Optional[Dict[str, Any]] = None
