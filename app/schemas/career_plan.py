"""
Pydantic schemas for Career Path Designer
Defines the comprehensive CareerPlan structure with strict validation
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


# ========== Intake Schemas ==========
class IntakeRequest(BaseModel):
    """User input for career path planning - comprehensive intake questionnaire"""

    # Basic Profile
    current_role_title: str = Field(..., min_length=2, max_length=200)
    current_industry: str = Field(..., min_length=2, max_length=200)
    years_experience: float = Field(..., ge=0, le=50)
    education_level: str = Field(..., description="Current education: high school/associates/bachelors/masters/phd")

    # Current Skills & Experience
    top_tasks: List[str] = Field(..., min_items=3, max_items=10)
    tools: List[str] = Field(default_factory=list, max_items=20)
    strengths: List[str] = Field(..., min_items=2, max_items=10)
    likes: List[str] = Field(default_factory=list, max_items=10)
    dislikes: List[str] = Field(default_factory=list, max_items=10)

    # Target Role Details
    target_role_interest: Optional[str] = Field(None, max_length=200)
    target_role_level: str = Field(..., description="entry-level/mid-level/senior/lead/executive")
    target_industries: List[str] = Field(default_factory=list, max_items=5, description="Industries interested in")
    specific_companies: List[str] = Field(default_factory=list, max_items=10, description="Specific companies to target")

    # Timeline & Availability
    time_per_week: int = Field(..., ge=1, le=168, description="Hours per week available")
    timeline: str = Field(..., description="Timeline: 3months/6months/12months")
    current_employment_status: str = Field(..., description="employed-full-time/employed-part-time/unemployed/student/freelance")

    # Location & Work Preferences
    location: str = Field(..., description="City, State or Country")
    willing_to_relocate: bool = Field(default=False, description="Willing to relocate for opportunities")
    in_person_vs_remote: str = Field(..., description="Preference: in-person/remote/hybrid")

    # Learning Preferences
    learning_style: List[str] = Field(..., min_items=1, description="video-courses/reading-books/hands-on-projects/bootcamp/mentorship/self-paced")
    preferred_platforms: List[str] = Field(default_factory=list, max_items=10, description="Coursera, Udemy, Pluralsight, etc.")
    technical_background: str = Field(..., description="non-technical/some-technical/technical/highly-technical")

    # Motivation & Goals
    transition_motivation: List[str] = Field(..., min_items=1, max_items=6, description="Why transitioning: better-pay/work-life-balance/interesting-work/remote-work/career-growth/passion")
    specific_technologies_interest: List[str] = Field(default_factory=list, max_items=20, description="Specific tech/frameworks want to learn")
    certification_areas_interest: List[str] = Field(default_factory=list, max_items=10, description="Areas want to get certified in")


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
    already_have: List[TransferableSkill] = Field(..., min_items=1)  # Reduced from 3 to 1
    can_reframe: List[ReframableSkill] = Field(default_factory=list)
    need_to_build: List[GapSkill] = Field(..., min_items=1)


# ========== Skills Guidance Schemas ==========
class SkillGuidanceItem(BaseModel):
    """Individual skill with guidance on why and how to develop it"""
    skill_name: str
    why_needed: str = Field(..., min_length=100, description="Detailed explanation of why this skill is critical for the target role")
    how_to_improve: str = Field(..., min_length=150, description="Specific actionable steps to develop this skill")
    importance: str = Field(..., description="critical/high/medium - priority level")
    estimated_time: str = Field(..., description="Time to develop proficiency (e.g., '3-6 months', '1-2 years')")
    resources: List[str] = Field(default_factory=list, max_items=5, description="Specific learning resources (courses, books, platforms)")
    real_world_application: str = Field(..., min_length=100, description="How this skill is used in day-to-day work")


class SkillsGuidance(BaseModel):
    """Comprehensive guidance on soft and hard skills needed for target role"""
    soft_skills: List[SkillGuidanceItem] = Field(..., min_items=3, max_items=8, description="Essential soft skills for the target role")
    hard_skills: List[SkillGuidanceItem] = Field(..., min_items=3, max_items=10, description="Essential technical/hard skills for the target role")
    skill_development_strategy: str = Field(..., min_length=200, description="Overall strategy for building these skills in parallel")


# ========== Certification Schemas ==========
class StudyMaterial(BaseModel):
    """Study materials for certification prep"""
    type: str = Field(..., description="official-course/book/video-series/practice-exams/hands-on-labs")
    title: str
    provider: str  # e.g., "Official Certification Body", "Udemy", "Pluralsight", "O'Reilly"
    url: str = Field(..., description="Direct link to resource")
    cost: str  # e.g., "Free", "$49.99", "Included in subscription"
    duration: str  # e.g., "40 hours", "350 pages", "12 practice exams"
    description: str = Field(..., min_length=50, max_length=500)
    recommended_order: int = Field(..., ge=1, le=20, description="Order to study this material")

class Certification(BaseModel):
    """A specific certification with real data and detailed study path"""
    name: str
    certifying_body: str = Field(..., description="e.g., CompTIA, AWS, Microsoft, ISC2")
    level: str = Field(..., description="foundation/intermediate/advanced")
    prerequisites: List[str] = Field(default_factory=list)
    est_study_weeks: int = Field(..., ge=1, le=104)
    est_cost_range: str
    exam_details: Dict[str, Any] = Field(default_factory=dict, description="exam_code, passing_score, duration, num_questions")
    official_links: List[str] = Field(..., min_items=1, description="ONLY web-grounded URLs")
    what_it_unlocks: str
    alternatives: List[str] = Field(default_factory=list)
    study_materials: List[StudyMaterial] = Field(..., min_items=1, description="Detailed study resources in recommended order")
    study_plan_weeks: List[Dict[str, str]] = Field(default_factory=list, description="Week-by-week study plan")
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
class TechStackDetail(BaseModel):
    """Specific technology or tool in the stack"""
    name: str  # e.g., "React", "PostgreSQL", "AWS Lambda"
    category: str  # e.g., "Frontend Framework", "Database", "Cloud Service"
    why_this_tech: str = Field(..., min_length=50, description="Why this specific technology is valuable for the target role")
    learning_resources: List[str] = Field(..., min_items=1, description="URLs to learn this specific tech")

class ExperienceProject(BaseModel):
    """Portfolio project, volunteer work, or lab with detailed tech stack"""
    type: str = Field(..., description="portfolio/volunteer/lab/side-project/freelance")
    title: str
    description: str = Field(..., min_length=100, max_length=1000)
    skills_demonstrated: List[str] = Field(..., min_items=1)
    detailed_tech_stack: List[TechStackDetail] = Field(..., min_items=1, description="Specific technologies and why to use them")
    architecture_overview: str = Field(..., min_length=100, description="How the project is structured technically")
    time_commitment: str
    difficulty_level: str = Field(..., description="beginner/intermediate/advanced")
    step_by_step_guide: List[str] = Field(..., min_items=3, description="High-level steps to build this project")
    how_to_showcase: str = Field(..., description="How to present on resume/LinkedIn")
    example_resources: List[str] = Field(default_factory=list)
    github_example_repos: List[str] = Field(default_factory=list, description="Similar projects on GitHub for reference")


# ========== Events Schemas ==========
class Event(BaseModel):
    """Real networking/learning event with verified data"""
    name: str
    organizer: str = Field(..., description="Who runs this event - e.g., 'Linux Foundation', 'local tech meetup group'")
    type: str = Field(..., description="conference/meetup/virtual/career-fair/workshop")
    date_or_season: str
    location: str
    scope: str = Field(..., description="local/regional/national/international")
    price_range: str
    attendee_count: Optional[str] = Field(None, description="e.g., '500-1000 attendees', 'small group 20-30'")
    beginner_friendly: bool
    target_audience: str = Field(..., description="Who this event is for - e.g., 'Junior Developers', 'Security Professionals'")
    why_attend: str = Field(..., min_length=100, description="Detailed explanation of networking/learning opportunities")
    key_topics: List[str] = Field(default_factory=list, description="Main topics covered at event")
    notable_speakers: List[str] = Field(default_factory=list, description="Known speakers or companies presenting")
    registration_link: Optional[str] = Field(None, description="MUST be web-grounded, not hallucinated")
    recurring: bool = Field(default=False, description="Is this an annual/recurring event?")
    virtual_option_available: bool = Field(default=False)
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
    twelve_week_plan: List[WeeklyTask] = Field(..., min_items=10, max_items=14)  # Allow 10-14 weeks for flexibility
    six_month_plan: List[MonthlyPhase] = Field(..., min_items=5, max_items=7)   # Allow 5-7 months for flexibility
    apply_ready_checkpoint: str = Field(..., description="When user can start applying")


# ========== Resume Assets Schemas ==========
class ResumeBullet(BaseModel):
    """Single resume bullet with detailed guidance"""
    bullet_text: str = Field(..., min_length=50, max_length=300)
    why_this_works: str = Field(..., min_length=50, description="Detailed explanation of why this bullet is effective")
    what_to_emphasize: str = Field(..., description="What aspect of your experience to highlight")
    keywords_included: List[str] = Field(..., description="ATS keywords naturally incorporated")
    structure_explanation: str = Field(..., description="How this follows STAR/CAR method")

class SkillGrouping(BaseModel):
    """Grouped skills by category with explanations"""
    category: str  # e.g., "Technical Skills", "Cloud Platforms", "Programming Languages"
    skills: List[str] = Field(..., min_items=1)
    why_group_these: str = Field(..., min_length=50, description="Why these skills are grouped together")
    priority: str = Field(..., description="core/important/supplementary")

class ResumeAssets(BaseModel):
    """AI-generated resume content with extreme detail and guidance"""
    # Headline & Summary
    headline: str = Field(..., max_length=200)
    headline_explanation: str = Field(..., min_length=100, description="Why this headline positions you effectively")

    summary: str = Field(..., min_length=100, max_length=1000)
    summary_breakdown: str = Field(..., min_length=200, description="Detailed explanation of each sentence in the summary")
    summary_strategy: str = Field(..., min_length=100, description="Overall strategy behind this summary")

    # Skills Section with Grouping
    skills_grouped: List[SkillGrouping] = Field(..., min_items=2, description="Skills organized by category")
    skills_ordering_rationale: str = Field(..., min_length=100, description="Why skills are ordered this way")

    # Achievement Bullets
    target_role_bullets: List[ResumeBullet] = Field(..., min_items=3, max_items=10)
    bullets_overall_strategy: str = Field(..., min_length=150, description="How these bullets collectively position you")

    # Experience Reframing Guide
    how_to_reframe_current_role: str = Field(..., min_length=200, description="Detailed guide on repositioning current experience")
    experience_gaps_to_address: List[str] = Field(..., description="How to address gaps or pivots")

    # Keywords & ATS
    keywords_for_ats: List[str] = Field(..., min_items=5)
    keyword_placement_strategy: str = Field(..., min_length=100, description="Where and how to naturally incorporate keywords")

    # LinkedIn Guidance
    linkedin_headline: str
    linkedin_about_section: str = Field(..., min_length=200, max_length=2000)
    linkedin_strategy: str = Field(..., min_length=100, description="How to optimize LinkedIn for this transition")

    # Cover Letter Template
    cover_letter_template: str = Field(..., min_length=500, description="Customizable cover letter framework")
    cover_letter_guidance: str = Field(..., min_length=200, description="How to adapt this template")


# ========== Complete Career Plan Schema ==========
class CareerPlan(BaseModel):
    """The master schema for the entire career plan"""
    # Metadata
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = Field(default="1.0")

    # Core sections
    profile_summary: str = Field(..., min_length=50, max_length=500)  # Reduced from 100 to 50
    target_roles: List[TargetRole] = Field(..., min_items=1, max_items=6)
    skills_analysis: SkillsAnalysis
    skills_guidance: SkillsGuidance
    certification_path: List[Certification] = Field(..., min_items=1, max_items=8)
    education_options: List[EducationOption] = Field(..., min_items=1, max_items=5)
    experience_plan: List[ExperienceProject] = Field(..., min_items=1, max_items=10)  # Reduced from 2 to 1
    events: List[Event] = Field(..., min_items=1, max_items=15)  # Reduced from 3 to 1
    timeline: Timeline
    resume_assets: ResumeAssets

    # Source tracking
    research_sources: List[str] = Field(..., min_items=1, description="All web-grounded sources")  # Reduced from 3 to 1


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
    validation_errors: Optional[List[Dict[str, Any]]] = None


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
