# Career Path Designer - Complete Implementation

## Overview

The Career Path Designer is a comprehensive AI-powered feature that guides users from career change intent to a complete end-to-end transition plan. It uses **Perplexity for web-grounded research** and **OpenAI for personalized synthesis** with strict schema validation.

## Architecture

### Two-Pass AI System

**PASS 1: Research (Perplexity)**
- Web-grounded facts about certifications, events, and education options
- ALL URLs are verified from web citations (no hallucinations)
- Returns official links, costs, prerequisites, dates

**PASS 2: Synthesis (OpenAI)**
- Personalized career plan matching strict JSON schema
- Skills mapping, timeline, resume assets
- Schema validation + automatic repair if needed
- Ensures minimum required items in all arrays

### Tech Stack

**Backend:**
- FastAPI routes: `/api/career-path/*`
- Perplexity for web research (sonar model)
- OpenAI for synthesis (gpt-4-turbo-preview with JSON mode)
- Pydantic schemas for validation
- PostgreSQL for persistence

**Frontend:**
- React + TypeScript wizard UI
- Type-safe with `career-plan.ts` types
- Responsive mobile-first design
- Real-time validation

## Data Flow

```
1. User fills intake form
   ↓
2. Research Service (Perplexity)
   - Certifications with official links
   - Education options (degrees/bootcamps)
   - Events with registration URLs
   ↓
3. Synthesis Service (OpenAI)
   - Target roles (3-6 suggestions)
   - Transferable skills mapping
   - Skills gap analysis
   - Certification sequencing
   - Experience builder projects
   - 12-week + 6-month timeline
   - Resume assets (bullets, summary, keywords)
   ↓
4. Schema Validation
   - CareerPlan.validate()
   - Auto-repair if errors detected
   ↓
5. Save to database
   - career_plans table
   - intake_json, research_json, plan_json
   ↓
6. Display results
   - Multi-section wizard UI
   - Export & refresh capabilities
```

## Files Created

### Backend

```
backend/app/
├── models/career_plan.py              # SQLAlchemy model
├── schemas/career_plan.py             # Pydantic schemas (30+ types)
├── routes/career_path.py              # API endpoints
├── services/
│   ├── career_path_research_service.py    # Perplexity research
│   └── career_path_synthesis_service.py   # OpenAI synthesis + validation
└── migrations/
    └── add_career_plans_table.sql     # Database schema

backend/run_career_path_migration.py   # Migration script
```

### Frontend

```
web/src/
├── types/career-plan.ts               # TypeScript types
├── pages/CareerPathDesigner.tsx       # Main wizard UI
└── api/client.ts                      # API methods (updated)
```

## API Endpoints

### POST `/api/career-path/research`
Research certifications, education, and events.

**Request:**
```json
{
  "target_roles": ["Cybersecurity Analyst", "Security Engineer"],
  "location": "Austin, TX",
  "education_level": "bachelors",
  "budget": "medium"
}
```

**Response:**
```json
{
  "certifications": [...],
  "education_options": [...],
  "events": [...],
  "research_sources": ["https://...", "https://..."]
}
```

### POST `/api/career-path/generate`
Generate complete career plan.

**Request:**
```json
{
  "intake": {
    "current_role_title": "Project Manager",
    "current_industry": "Healthcare",
    "years_experience": 8,
    "top_tasks": ["Coordinate teams", "Track milestones", "Manage budgets"],
    "tools": ["Jira", "MS Project", "Excel"],
    "strengths": ["Communication", "Organization"],
    "target_role_interest": "Cybersecurity Program Manager",
    "time_per_week": 15,
    "budget": "medium",
    "timeline": "6months",
    "education_level": "bachelors",
    "location": "Remote",
    "in_person_vs_remote": "remote"
  }
}
```

**Response:**
```json
{
  "success": true,
  "plan": { /* Complete CareerPlan object */ },
  "plan_id": 42
}
```

### GET `/api/career-path/{plan_id}`
Retrieve saved plan.

### GET `/api/career-path/`
List all plans for user.

### POST `/api/career-path/refresh-events`
Re-fetch events without regenerating plan.

**Request:**
```json
{
  "plan_id": 42,
  "location": "Austin, TX"
}
```

### DELETE `/api/career-path/{plan_id}`
Soft delete a plan.

## Environment Variables

**Required:**
```bash
# Backend (.env)
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...

# Optional overrides
CAREER_PATH_MODEL=gpt-4-turbo-preview  # OpenAI model for synthesis
```

**Frontend (.env):**
```bash
VITE_API_URL=https://resume-ai-backend-production-3134.up.railway.app
```

## Database Schema

**Table: `career_plans`**

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_id | INTEGER | Future auth integration |
| session_user_id | VARCHAR(255) | Session-based user |
| intake_json | JSONB | User input |
| research_json | JSONB | Perplexity research data |
| plan_json | JSONB | Complete career plan |
| version | VARCHAR(10) | Schema version |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |
| is_deleted | BOOLEAN | Soft delete flag |
| deleted_at | TIMESTAMP | Deletion time |
| deleted_by | VARCHAR(255) | Who deleted |

**Indexes:**
- user_id
- session_user_id
- created_at
- is_deleted

## CareerPlan Schema (Simplified)

```typescript
interface CareerPlan {
  generatedAt: string
  version: string
  profileSummary: string

  targetRoles: TargetRole[]       // 1-6 roles with bridge roles
  skillsAnalysis: {
    alreadyHave: TransferableSkill[]    // Min 3
    canReframe: ReframableSkill[]
    needToBuild: GapSkill[]             // Min 1
  }

  certificationPath: Certification[]    // 1-8 certs, sequenced
  educationOptions: EducationOption[]   // 1-5 options
  experiencePlan: ExperienceProject[]   // 2-10 projects
  events: Event[]                       // 3-15 events

  timeline: {
    twelveWeekPlan: WeeklyTask[]        // Exactly 12
    sixMonthPlan: MonthlyPhase[]        // Exactly 6
    applyReadyCheckpoint: string
  }

  resumeAssets: {
    headline: string
    summary: string
    skillsSection: string[]             // 8-20 skills
    targetRoleBullets: string[]         // 6-10 bullets
    keywordsForAts: string[]            // 10+ keywords
  }

  researchSources: string[]             // All web-grounded sources
}
```

## Validation & Repair

The system enforces strict schema compliance:

1. **Initial Validation:** Pydantic schema validation
2. **Auto-Repair:** If validation fails, sends invalid JSON + errors to OpenAI with repair prompt
3. **Second Validation:** Re-validate repaired JSON
4. **Failure Handling:** Return detailed error messages to user

**Example Repair:**
```
Input: Missing "alreadyHave" skills (required min: 3)
Repair Prompt: "Fix validation error: Field 'alreadyHave' requires min 3 items"
Output: Repaired JSON with 3+ transferable skills
```

## Usage Examples

### Running Locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run_career_path_migration.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd web
npm install
npm run dev
```

### Testing API

**Generate Plan:**
```bash
curl -X POST http://localhost:8000/api/career-path/generate \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test-user-123" \
  -d '{
    "intake": {
      "current_role_title": "Data Analyst",
      "current_industry": "Finance",
      "years_experience": 5,
      "top_tasks": ["SQL queries", "Data visualization", "Reporting"],
      "tools": ["Python", "Tableau", "Excel"],
      "strengths": ["Analytical thinking", "Problem solving"],
      "time_per_week": 10,
      "budget": "low",
      "timeline": "6months",
      "education_level": "bachelors",
      "location": "Remote",
      "in_person_vs_remote": "remote"
    }
  }'
```

**List Plans:**
```bash
curl http://localhost:8000/api/career-path/ \
  -H "X-User-ID: test-user-123"
```

## Key Features

### ✅ Web-Grounded Research
- **No hallucinated URLs** - All links verified from Perplexity citations
- Real certification bodies, event registrations, program sites

### ✅ Strict Schema Validation
- Pydantic validation ensures data quality
- Automatic repair if OpenAI returns invalid JSON
- Minimum/maximum item constraints enforced

### ✅ Personalized Synthesis
- Skills mapping from user's actual experience
- Realistic timelines based on time availability
- Budget-conscious recommendations

### ✅ Actionable Deliverables
- Week-by-week 12-week plan
- Month-by-month 6-month roadmap
- Resume bullets ready to copy
- LinkedIn headline suggestions

### ✅ Refresh Capability
- Events can be refreshed without full regeneration
- Useful as registration dates approach
- Preserves rest of plan

## Quality Assurance

**Pre-deployment Checklist:**
- [x] Schema validation enforced
- [x] Perplexity citations extracted correctly
- [x] OpenAI repair mechanism tested
- [x] Database migration completed
- [x] Frontend form validation
- [x] API error handling
- [x] Mobile responsiveness

## Limitations & Future Enhancements

**Current Limitations:**
- Session-based user ID (no true auth yet)
- English only
- US-centric event research
- No calendar integration

**Future Enhancements:**
1. Integration with user's actual resume data
2. Progress tracking (checkboxes for weekly tasks)
3. Calendar export (ICS files)
4. Email reminders for milestones
5. Community features (share plans, success stories)
6. AI-powered progress coaching
7. Job board integration
8. Interview scheduling automation

## Support

For issues or questions:
1. Check validation errors in response
2. Verify OPENAI_API_KEY and PERPLEXITY_API_KEY are set
3. Ensure database migration ran successfully
4. Check Railway logs for backend errors
5. Use browser DevTools for frontend debugging

## License

Proprietary - Part of Talor Resume AI Platform

---

**Last Updated:** 2026-01-17
**Version:** 1.0
**Status:** Production Ready ✅
