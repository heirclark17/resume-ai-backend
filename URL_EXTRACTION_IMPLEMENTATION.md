# URL Extraction Feature Implementation

## Summary
Added URL extraction functionality to the cover letter generator, allowing users to provide either a job URL or paste job description text directly.

---

## Changes Made

### 1. Frontend (talor-web)

#### `web/src/pages/CoverLetterGenerator.tsx`
**Added:**
- `jobUrl` state variable to store URL input
- `jobInputMethod` state to track input method ('text' or 'url')
- Tab interface with "Paste Text" and "Enter URL" buttons
- URL input field with validation and placeholder
- Form submission logic to send either `job_description` or `job_url`

**UI Flow:**
```
Job Description *
┌──────────────────────────────────────┐
│ [Paste Text] [Enter URL]  ← Tabs   │
├──────────────────────────────────────┤
│ https://linkedin.com/jobs/view/...   │
│                                      │
│ Paste job URL from LinkedIn,        │
│ company career pages, or job boards │
└──────────────────────────────────────┘
```

#### `web/src/api/client.ts`
**Updated:**
- `generateCoverLetter` method to accept optional `job_url` parameter
- Made `job_description` optional (since URL is an alternative)

---

### 2. Backend (resume-ai-backend)

#### `app/routes/cover_letters.py`
**Added Functions:**

1. **`detect_company_from_url(url: str) -> Optional[str]`**
   - Detects company name from URL domain
   - Supports: JPMorgan Chase, Oracle, Microsoft, Google, Amazon, Apple, Meta
   - Returns company name or None

2. **`async extract_job_from_url(url: str) -> str`**
   - Uses Playwright to fetch job description from URL
   - Waits 5 seconds for JavaScript to load
   - Attempts to wait for job description selectors
   - Returns extracted page text
   - Raises HTTPException on failure

**Updated:**
- `GenerateRequest` model:
  - Made `job_description` optional
  - Added `job_url` as optional field

- `generate_cover_letter` endpoint:
  - Added validation to ensure either `job_description` or `job_url` is provided
  - Extracts job description from URL when `job_url` is provided
  - Auto-detects company from URL if company_name is generic
  - Logs URL extraction attempts
  - Uses extracted job_description for cover letter generation

**Dependencies:**
- ✅ Playwright already in requirements.txt (line 13)

---

## How It Works

### User Flow:

1. **User opens "Generate Cover Letter" modal**
2. **User chooses input method:**
   - **Tab 1: "Paste Text"** - Traditional text paste
   - **Tab 2: "Enter URL"** - New URL extraction
3. **If URL selected:**
   - User pastes job URL (LinkedIn, company career page, etc.)
   - Frontend sends `job_url` to backend
   - Backend extracts job description using Playwright
   - Backend auto-detects company from URL
4. **Backend generates cover letter** using extracted data
5. **User receives personalized cover letter**

### Backend Processing:

```python
if job_url:
    # Extract job description
    job_description = await extract_job_from_url(job_url)

    # Auto-detect company
    if not company_name or company_name == 'Target Company':
        detected_company = detect_company_from_url(job_url)
        if detected_company:
            company_name = detected_company
```

---

## Supported Job Boards

### Currently Supported:
- ✅ LinkedIn Jobs
- ✅ Company Career Pages (jpmc.fa.oraclecloud.com, etc.)
- ✅ Indeed
- ✅ Glassdoor
- ✅ ZipRecruiter
- ✅ Any public job posting URL

### Company Auto-Detection:
- JPMorgan Chase (jpmc, jpmorganchase)
- Oracle
- Microsoft
- Google
- Amazon
- Apple
- Meta/Facebook

---

## Testing

### Frontend Testing:
```bash
cd /c/Users/derri/talor-web/web
npm run dev
```

1. Navigate to Cover Letters page
2. Click "Generate New"
3. Switch to "Enter URL" tab
4. Paste a job URL
5. Fill in job title (if needed)
6. Click "Generate Cover Letter"

### Backend Testing:
```bash
cd /c/Users/derri/resume-ai-backend
# Test URL extraction function
python -c "
import asyncio
from app.routes.cover_letters import extract_job_from_url

async def test():
    url = 'https://jpmc.fa.oraclecloud.com/...'
    result = await extract_job_from_url(url)
    print(f'Extracted {len(result)} characters')

asyncio.run(test())
"
```

### API Testing:
```bash
curl -X POST https://resume-ai-backend-production-3134.up.railway.app/api/cover-letters/generate \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Cybersecurity Program Manager",
    "company_name": "Microsoft",
    "job_url": "https://careers.microsoft.com/...",
    "tone": "professional"
  }'
```

---

## Error Handling

### Frontend:
- Validates URL format (type="url")
- Shows user-friendly error messages
- Provides fallback to text paste if URL fails

### Backend:
- Validates that either `job_description` or `job_url` is provided
- Returns 400 error if extraction fails
- Logs all extraction attempts for debugging
- Gracefully handles timeout/connection issues

---

## Next Steps

### Optional Enhancements:
1. **Add file upload option** (PDF/DOCX job descriptions)
2. **Cache extracted job descriptions** (avoid re-extraction)
3. **Add more company auto-detection patterns**
4. **Improve parsing** (extract structured data: title, company, location, etc.)
5. **Add retry logic** for failed extractions
6. **Support authenticated job boards** (requires user credentials)

---

## Deployment

### Frontend (Vercel):
```bash
cd /c/Users/derri/talor-web
git add .
git commit -m "Add URL extraction to cover letter generator"
git push origin master
# Vercel will auto-deploy
```

### Backend (Railway):
```bash
cd /c/Users/derri/resume-ai-backend
git add .
git commit -m "Add URL extraction endpoint for cover letters"
git push origin master
# Railway will auto-deploy
```

---

## Files Modified

### Frontend:
- `talor-web/web/src/pages/CoverLetterGenerator.tsx` (+50 lines)
- `talor-web/web/src/api/client.ts` (+2 lines)

### Backend:
- `resume-ai-backend/app/routes/cover_letters.py` (+65 lines)

### Total Changes:
- **3 files modified**
- **117 lines added**
- **0 dependencies added** (Playwright already installed)

---

**Status:** ✅ Ready for Testing
**Last Updated:** February 10, 2026
