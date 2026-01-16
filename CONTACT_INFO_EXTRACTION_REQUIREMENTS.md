# Contact Information Extraction - CRITICAL REQUIREMENT

## Priority: URGENT - BLOCKING ATS COMPLIANCE

**Date:** January 16, 2026
**Status:** ❌ NOT IMPLEMENTED
**Impact:** Exported resumes failing ATS parsing, missing candidate identity

---

## Current Problems

### Problem 1: Export Filename Missing Candidate Name
**Current Output:**
```
User7ab0cdc9_Unknown_Position_TailoredResume.docx
```

**Expected Output:**
```
Diamond_Dixon_Senior_Cybersecurity_Manager_TailoredResume.docx
```

**Root Cause:** Backend uses `user_id` instead of candidate `name` because contact info is not extracted from uploaded resumes.

### Problem 2: Missing ATS-Required Contact Information
**Current State:** Resume parser extracts:
- ✅ Summary
- ✅ Skills
- ✅ Experience (header, location, dates, bullets)
- ✅ Education
- ✅ Certifications
- ❌ **Name** (CRITICAL)
- ❌ **Email** (CRITICAL)
- ❌ **Phone** (CRITICAL)
- ❌ **LinkedIn** (Recommended)
- ❌ **Location** (Recommended)

**Impact:**
- ATS systems reject resumes without contact information
- Recruiters cannot contact candidates
- Export filename doesn't identify candidate

---

## Required Implementation

### 1. Resume Parser Enhancement

**File:** `app/services/resume_parser.py` (or wherever resume parsing occurs)

**Add Contact Info Extraction Function:**

```python
import re
from docx import Document
from typing import Dict, Optional

def extract_contact_info_from_docx(file_path: str) -> Dict[str, Optional[str]]:
    """
    Extract contact information from DOCX resume.

    Returns:
        {
            "name": str or None,
            "email": str or None,
            "phone": str or None,
            "linkedin": str or None,
            "location": str or None
        }
    """
    doc = Document(file_path)

    # Extract all text for regex matching
    full_text = '\n'.join([para.text for para in doc.paragraphs])

    # 1. EXTRACT NAME
    # Name is typically in first 2-3 paragraphs with large font (18-24pt)
    name = None
    for para in doc.paragraphs[:5]:
        if para.runs and len(para.runs) > 0:
            # Check if paragraph has large font size
            for run in para.runs:
                if run.font.size and run.font.size.pt >= 16:
                    text = para.text.strip()
                    # Validate it looks like a name (2-4 words, capitalized)
                    words = text.split()
                    if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if len(w) > 0):
                        name = text
                        break
            if name:
                break

    # 2. EXTRACT EMAIL
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, full_text)
    email = email_match.group() if email_match else None

    # 3. EXTRACT PHONE
    # Match formats: (555) 123-4567, 555-123-4567, 555.123.4567, 5551234567
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_match = re.search(phone_pattern, full_text)
    phone = phone_match.group() if phone_match else None

    # 4. EXTRACT LINKEDIN
    linkedin_patterns = [
        r'linkedin\.com/in/[\w-]+',
        r'www\.linkedin\.com/in/[\w-]+',
        r'https?://(?:www\.)?linkedin\.com/in/[\w-]+'
    ]
    linkedin = None
    for pattern in linkedin_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            linkedin = match.group()
            # Clean up to standard format
            if not linkedin.startswith('http'):
                linkedin = 'https://' + linkedin
            break

    # 5. EXTRACT LOCATION
    # Match "City, ST" format (Houston, TX) or "City, State" (Houston, Texas)
    location_pattern = r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}(?:\s+\d{5})?'
    location_match = re.search(location_pattern, full_text)
    location = location_match.group() if location_match else None

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "location": location
    }


def extract_contact_info_from_pdf(file_path: str) -> Dict[str, Optional[str]]:
    """
    Extract contact information from PDF resume.
    Use PyPDF2 or pdfplumber to extract text, then apply same regex patterns.
    """
    import PyPDF2  # or pdfplumber

    # Extract text from PDF
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        full_text = ''
        for page in pdf_reader.pages:
            full_text += page.extract_text()

    # Apply same regex patterns as DOCX
    # (Reuse the regex logic from extract_contact_info_from_docx)

    name_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$'  # Simplified for PDF
    name_match = re.search(name_pattern, full_text, re.MULTILINE)
    name = name_match.group(1) if name_match else None

    # ... (same email, phone, linkedin, location extraction as above)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "location": location
    }
```

### 2. Update Resume Upload Endpoint

**File:** `app/routers/resumes.py` (or wherever `/api/resumes/upload` is defined)

**Modify upload handler to include contact info:**

```python
@router.post("/upload")
async def upload_resume(file: UploadFile, user_id: str = Header(...)):
    """Upload and parse resume file"""

    # ... existing file saving logic ...

    # Parse resume content
    if file_path.endswith('.docx'):
        parsed_data = parse_docx_resume(file_path)
        contact_info = extract_contact_info_from_docx(file_path)
    elif file_path.endswith('.pdf'):
        parsed_data = parse_pdf_resume(file_path)
        contact_info = extract_contact_info_from_pdf(file_path)
    else:
        raise HTTPException(400, "Unsupported file type")

    # Merge contact info into parsed_data
    parsed_data.update(contact_info)

    # Save to database (add contact fields to resume table if needed)
    resume = Resume(
        user_id=user_id,
        filename=file.filename,

        # Contact information (ADD THESE COLUMNS)
        name=contact_info.get('name'),
        email=contact_info.get('email'),
        phone=contact_info.get('phone'),
        linkedin=contact_info.get('linkedin'),
        location=contact_info.get('location'),

        # Existing fields
        summary=parsed_data.get('summary'),
        skills=json.dumps(parsed_data.get('skills', [])),
        experience=json.dumps(parsed_data.get('experience', [])),
        education=parsed_data.get('education'),
        certifications=parsed_data.get('certifications'),
    )

    db.add(resume)
    db.commit()

    # Return response with contact info
    return {
        "success": True,
        "data": {
            "resume_id": resume.id,
            "filename": file.filename,
            "parsed_data": {
                # Contact Information (NEW)
                "name": contact_info.get('name'),
                "email": contact_info.get('email'),
                "phone": contact_info.get('phone'),
                "linkedin": contact_info.get('linkedin'),
                "location": contact_info.get('location'),

                # Existing fields
                "summary": parsed_data.get('summary'),
                "skills": parsed_data.get('skills'),
                "experience": parsed_data.get('experience'),
                "education": parsed_data.get('education'),
                "certifications": parsed_data.get('certifications')
            }
        }
    }
```

### 3. Database Schema Update

**Add columns to `resumes` table:**

```sql
-- Migration: Add contact information columns

ALTER TABLE resumes ADD COLUMN name VARCHAR(255);
ALTER TABLE resumes ADD COLUMN email VARCHAR(255);
ALTER TABLE resumes ADD COLUMN phone VARCHAR(50);
ALTER TABLE resumes ADD COLUMN linkedin VARCHAR(500);
ALTER TABLE resumes ADD COLUMN location VARCHAR(255);

-- Create index for name lookups
CREATE INDEX idx_resumes_name ON resumes(name);
CREATE INDEX idx_resumes_email ON resumes(email);
```

**Or using Alembic migration:**

```python
# migrations/versions/add_contact_info_to_resumes.py

def upgrade():
    op.add_column('resumes', sa.Column('name', sa.String(255), nullable=True))
    op.add_column('resumes', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('resumes', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('resumes', sa.Column('linkedin', sa.String(500), nullable=True))
    op.add_column('resumes', sa.Column('location', sa.String(255), nullable=True))

    op.create_index('idx_resumes_name', 'resumes', ['name'])
    op.create_index('idx_resumes_email', 'resumes', ['email'])

def downgrade():
    op.drop_index('idx_resumes_email')
    op.drop_index('idx_resumes_name')
    op.drop_column('resumes', 'location')
    op.drop_column('resumes', 'linkedin')
    op.drop_column('resumes', 'phone')
    op.drop_column('resumes', 'email')
    op.drop_column('resumes', 'name')
```

### 4. Update Export Filename Generation

**File:** `app/services/docx_exporter.py` (or wherever DOCX export happens)

**Change from:**
```python
filename = f"User{user_id}_{company or 'Unknown_Company'}_{job_title or 'Unknown_Position'}_TailoredResume.docx"
```

**Change to:**
```python
# Get candidate name from base resume
candidate_name = base_resume.name or "Candidate"
candidate_name_safe = candidate_name.replace(' ', '_')

# Clean job title and company for filename
job_title_safe = (job_title or "Position").replace(' ', '_')
company_safe = (company or "Company").replace(' ', '_')

filename = f"{candidate_name_safe}_{job_title_safe}_TailoredResume.docx"

# Example output: Diamond_Dixon_Senior_Cybersecurity_Manager_TailoredResume.docx
```

### 5. Include Contact Info in DOCX Export

**In the DOCX generation code, add contact header:**

```python
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_tailored_resume_docx(base_resume, tailored_data, output_path):
    doc = Document()

    # === CONTACT INFORMATION HEADER ===
    # This is CRITICAL for ATS parsing

    # Candidate Name (18-24pt, bold, centered)
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(base_resume.name or "Name Not Available")
    name_run.font.size = Pt(20)
    name_run.font.bold = True

    # Contact Details (centered, 10-11pt)
    contact_para = doc.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact_parts = []
    if base_resume.phone:
        contact_parts.append(base_resume.phone)
    if base_resume.email:
        contact_parts.append(base_resume.email)
    if base_resume.linkedin:
        contact_parts.append(base_resume.linkedin)
    if base_resume.location:
        contact_parts.append(base_resume.location)

    contact_text = " | ".join(contact_parts)
    contact_run = contact_para.add_run(contact_text)
    contact_run.font.size = Pt(11)

    # Add spacing after header
    doc.add_paragraph()  # Blank line

    # === PROFESSIONAL SUMMARY ===
    summary_heading = doc.add_paragraph("PROFESSIONAL SUMMARY")
    summary_heading.runs[0].font.bold = True
    summary_heading.runs[0].font.size = Pt(12)

    summary_para = doc.add_paragraph(tailored_data.tailored_summary)
    summary_para.runs[0].font.size = Pt(11)

    # ... rest of resume sections ...

    doc.save(output_path)
```

---

## Testing Checklist

After implementing the above changes:

### 1. Upload Resume Test
```bash
# Upload a resume and check response
curl -X POST https://resume-ai-backend-production-3134.up.railway.app/api/resumes/upload \
  -H "X-User-ID: test_user" \
  -F "file=@Diamond_Resume.docx"
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "resume_id": 123,
    "parsed_data": {
      "name": "Diamond Marie Dixon",
      "email": "diamond@example.com",
      "phone": "(555) 123-4567",
      "linkedin": "https://linkedin.com/in/diamond",
      "location": "Houston, TX",
      "summary": "...",
      "skills": [...],
      "experience": [...],
      "education": "...",
      "certifications": "..."
    }
  }
}
```

### 2. Frontend Console Log Test
After uploading in frontend UI, check browser console for:
```
=== RAW BACKEND PARSED_DATA ===
Available parsed_data fields: name, email, phone, linkedin, location, summary, skills, experience, education, certifications

=== CONTACT INFORMATION DEBUG ===
Name: Diamond Marie Dixon
Email: diamond@example.com
Phone: (555) 123-4567
LinkedIn: https://linkedin.com/in/diamond
Location: Houston, TX
```

### 3. Export Filename Test
Generate a tailored resume and verify filename format:
```
✅ Diamond_Dixon_Senior_Cybersecurity_Manager_TailoredResume.docx
❌ User7ab0cdc9_Unknown_Position_TailoredResume.docx
```

### 4. ATS Compliance Test
Use the Python analyzer:
```bash
python analyze_exported_resume.py "exported-tailored-resume.docx"
```

**Expected Output:**
```
✓ Name found: 'Diamond Marie Dixon' (20pt)
✓ Phone number found: (555) 123-4567
✓ Email found: diamond@example.com
✓ LinkedIn profile present

ATS COMPLIANCE SCORE: 95.0%
Rating: EXCELLENT - Ready for ATS submission
```

---

## Additional Requirement: Job URL Extraction Endpoint

The frontend now includes a "smart URL extraction" feature that requires a new backend endpoint.

### Endpoint Specification

```python
@router.post("/api/jobs/extract")
async def extract_job_details(request: JobURLRequest):
    """
    Extract company name, job title, and description from job posting URL.

    Request Body:
        {
            "job_url": "https://www.linkedin.com/jobs/view/..."
        }

    Response:
        {
            "success": true,
            "data": {
                "company": "Microsoft",
                "job_title": "Senior Security Program Manager",
                "description": "Full job description text..."
            }
        }

    Errors:
        {
            "success": false,
            "error": "Could not extract job details from URL"
        }
    """

    job_url = request.job_url

    try:
        # Use BeautifulSoup or Playwright to scrape job page

        if "linkedin.com/jobs" in job_url:
            # LinkedIn-specific extraction
            company, title, description = extract_from_linkedin(job_url)

        elif "indeed.com" in job_url:
            # Indeed-specific extraction
            company, title, description = extract_from_indeed(job_url)

        else:
            # Generic extraction using meta tags and common patterns
            company, title, description = extract_from_generic_site(job_url)

        return {
            "success": True,
            "data": {
                "company": company,
                "job_title": title,
                "description": description
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Could not extract job details: {str(e)}"
        }


def extract_from_linkedin(job_url: str) -> tuple:
    """Extract from LinkedIn job posting"""
    # Use Playwright or Selenium (LinkedIn requires JS rendering)
    # Look for:
    # - Company: <meta property="og:site_name"> or .topcard__org-name-link
    # - Title: <h1 class="topcard__title"> or <meta property="og:title">
    # - Description: .show-more-less-html__markup

    return company, title, description


def extract_from_indeed(job_url: str) -> tuple:
    """Extract from Indeed job posting"""
    # Indeed structure:
    # - Company: <div class="jobsearch-InlineCompanyRating">
    # - Title: <h1 class="jobsearch-JobInfoHeader-title">
    # - Description: <div id="jobDescriptionText">

    return company, title, description


def extract_from_generic_site(job_url: str) -> tuple:
    """Extract from any job posting using common patterns"""
    # Fallback using meta tags:
    # - <meta property="og:title">
    # - <meta property="og:description">
    # - <title> tag
    # - Look for common CSS classes: .job-title, .company-name, .job-description

    return company, title, description
```

---

## Priority & Timeline

**Priority:** 🔴 CRITICAL - P0
**Timeline:** ASAP (blocks ATS compliance)
**Estimated Effort:** 4-6 hours
**Dependencies:** None

**Breakdown:**
1. Contact info extraction function: 2 hours
2. Database migration: 30 minutes
3. Upload endpoint update: 1 hour
4. Export filename fix: 30 minutes
5. DOCX contact header: 1 hour
6. Job URL extraction endpoint: 2 hours (optional, can be deferred)
7. Testing: 1 hour

---

## Success Criteria

✅ Uploaded resumes return `name`, `email`, `phone` in response
✅ Frontend console shows contact info in debug logs
✅ Export filename uses candidate name: `[Name]_[Title]_TailoredResume.docx`
✅ Exported DOCX contains contact header with name, email, phone
✅ ATS analyzer shows 90%+ compliance score
✅ No "User[ID]" or "Unknown_Position" in export filenames

---

## Current Frontend Status

✅ Frontend interfaces updated to handle contact info
✅ Upload page shows visual validation for missing contact fields
✅ Debug logging in place to show backend response
✅ Smart URL extraction UI implemented (requires backend endpoint)
✅ Contact info fields added to BaseResume and ParsedResume interfaces

**Waiting on:** Backend implementation of contact info extraction

---

## Contact for Questions

**Frontend Lead:** Claude Sonnet 4.5
**Implementation Required By:** Backend Team
**Test Resume Available:** `C:\Users\derri\Downloads\Diamond_Marie_Dixon_Resume_Final (4) (2).docx`
**ATS Analyzer Tool:** `C:\Users\derri\projects\resume-ai-app\analyze_exported_resume.py`
**Full Requirements:** `C:\Users\derri\projects\resume-ai-app\ATS_EXPORT_REQUIREMENTS.md`

---

**Last Updated:** January 16, 2026
**Document Version:** 1.0
