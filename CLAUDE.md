# Cybersecurity Resume Tailoring System

## Project Overview

Automated system for discovering cybersecurity program management jobs and generating deeply tailored resumes customized to each company's culture, initiatives, and specific job requirements.

---

## System Requirements

### Python Environment
- Python 3.8+
- Required packages:
  ```bash
  pip install python-docx
  pip install playwright
  pip install PyPDF2          # For PDF job description parsing
  pip install pdfplumber      # Alternative PDF parser (more reliable)
  python -m playwright install chromium
  ```

### Core Dependencies
- `python-docx` - Word document creation and manipulation
- `playwright` - Web scraping and job verification
- `PyPDF2` or `pdfplumber` - PDF job description extraction
- `json` - Job data management
- Standard library: `os`, `time`, `re` (regex for job parsing)

---

## Project Structure

```
C:\Users\derri\
├── claude.md                                    # This file
├── create_deeply_tailored_resumes.py           # Main resume generation script
├── create_tailored_cover_letter.py             # Cover letter generation script
├── verify_user_jobs.py                         # Playwright job verification script
├── user_job_verification.json                  # Verified job data
├── DEEPLY_TAILORED_RESUMES\                    # Output directory
│   ├── 1_JPMorgan_Cybersecurity - Lead Technical Program Manager.docx
│   ├── 2_Oracle_Senior Program Manager - Cybersecurity.docx
│   └── TAILORED_APPLICATION_GUIDE.txt
├── TAILORED_COVER_LETTERS\                     # Cover letter output directory
│   ├── 1_JPMorgan_CoverLetter_Cybersecurity_PM.docx
│   └── 2_Oracle_CoverLetter_Senior_PM.docx
└── Downloads\
    └── Justin_Washington_Cyber_PM_Resume.docx  # Base resume source
```

---

## Requirements

### Functional Requirements

#### 1. Job Discovery & Verification
- **User provides LinkedIn job URLs** (manual search required - automation blocked)
- **Playwright verification** of job status (active/expired)
- **Extract job details**: title, company, location, description, salary, posted date
- **Output verified jobs** to JSON file for processing

#### 2. Resume Customization
- **Company-specific research** (culture, values, initiatives, mission)
- **Job requirement analysis** (key competencies, responsibilities, frameworks)
- **Tailored professional summary** matching company priorities
- **Reframed experience bullets** with measurable outcomes
- **Company-aligned competencies** (e.g., NIST frameworks, CVSS scoring)
- **Clickable hyperlinks** embedded in Word documents
- **Professional formatting** (consistent fonts, spacing, colors)

#### 3. Content Requirements
- **Measurable outcomes** in every bullet point (%, numbers, quantifiable impact)
- **Company motto/mission alignment** statement
- **Industry-specific terminology** (financial services vs. federal healthcare)
- **Security frameworks** mentioned (NIST, ISO 27001, HIPAA, FedRAMP)
- **Multiple detailed bullets** per role (5+ bullets for recent positions)

#### 4. Cover Letter Generation
- **Flexible job input options:**
  - **Job URL:** Paste LinkedIn or company career page URL
  - **Job Document Upload:** Upload PDF, Word (.docx), or text file containing job description
- **Company research integration** (same 5-step framework as resumes)
- **Personalized opening paragraph** referencing specific company initiatives
- **Skills-to-requirements mapping** (demonstrate exact match to job qualifications)
- **Compelling narrative** (tell story of relevant experience and impact)
- **Mission alignment closing** (connect personal values to company mission)
- **Professional formatting** (consistent with resume style and company branding)
- **Optional customization parameters:**
  - Tone: Professional, Enthusiastic, Strategic, Technical
  - Length: Concise (3 paragraphs), Standard (4 paragraphs), Detailed (5 paragraphs)
  - Focus: Leadership, Technical expertise, Program management, Cross-functional collaboration

---

## Technical Requirements

### Resume Generation Script (`create_deeply_tailored_resumes.py`)

**Input:**
- `user_job_verification.json` - Verified active jobs from Playwright script
- Base resume content (extracted from original .docx)

**Output:**
- Company-specific Word documents (.docx)
- Application guide (.txt) with customization details

**Key Functions:**
```python
def add_hyperlink(paragraph, url, text):
    """Add clickable hyperlink to Word document using OxmlElement"""

def create_jpmorgan_resume(job_data):
    """Generate JPMorgan-tailored resume with banking/CTC focus"""

def create_oracle_resume(job_data):
    """Generate Oracle-tailored resume with federal/healthcare focus"""
```

**Customization Logic:**
- Detect company from job data
- Load company-specific template
- Reframe experience bullets to match company priorities
- Add company-specific competencies
- Include mission/values alignment statement

---

### Cover Letter Generation Script (`create_tailored_cover_letter.py`)

**Input Options (User Choice):**

**Option 1: Job URL**
```python
JOB_URL = "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/..."
# Script extracts job details via Playwright/web scraping
```

**Option 2: Uploaded Job Document**
```python
JOB_DOCUMENT_PATH = "C:/Users/derri/Downloads/job_description.pdf"
# Supported formats: .pdf, .docx, .txt
# Script extracts text from document
```

**Output:**
- Company-specific cover letter Word documents (.docx)
- Saved to `TAILORED_COVER_LETTERS\` directory
- File naming: `[Number]_[Company]_CoverLetter_[JobTitle].docx`

**Key Functions:**
```python
def extract_job_from_url(url):
    """Extract job details from URL using Playwright"""
    # Navigate to URL
    # Extract title, company, location, description
    # Return structured job data

def extract_job_from_document(file_path):
    """Extract job details from uploaded PDF/Word/text file"""
    # Detect file type (.pdf, .docx, .txt)
    # Extract text content
    # Parse for company name, job title, requirements
    # Return structured job data

def research_company(company_name):
    """Research company using 5-step framework from claude.md"""
    # Web search for mission, values, initiatives
    # Extract security team structure
    # Identify compliance frameworks
    # Return company research data

def generate_cover_letter(job_data, company_research, tone='Professional', length='Standard'):
    """Generate deeply tailored cover letter"""
    # Opening: Reference specific company initiative
    # Body paragraphs: Map experience to requirements
    # Closing: Mission alignment and call to action
    # Format with company colors and branding
    # Return formatted Word document

def create_cover_letter_document(content, company_name, job_title):
    """Create formatted Word document with company branding"""
    # Apply company color scheme
    # Format header with contact info
    # Add professional spacing and typography
    # Embed clickable application URL
    # Save to TAILORED_COVER_LETTERS directory
```

**Cover Letter Structure:**
1. **Header:** Name, contact info, date, hiring manager (if known), company address
2. **Opening Paragraph:** Hook referencing company initiative + why you're excited
3. **Body Paragraph 1:** Relevant experience mapped to 2-3 key requirements
4. **Body Paragraph 2:** Specific achievements with measurable outcomes
5. **Body Paragraph 3 (Optional):** Technical depth or leadership examples
6. **Closing Paragraph:** Mission alignment + call to action
7. **Signature:** Professional sign-off

**Customization Logic:**
- Detect company from job data (URL domain or document content)
- Apply same 5-step research framework as resumes
- Match tone to company culture (conservative for finance, innovative for tech)
- Reference 2-3 specific job requirements with direct experience mapping
- Include 1-2 measurable outcomes from professional history
- Use company-specific terminology throughout

**File Type Handling:**
```python
def detect_file_type(file_path):
    """Detect uploaded file format"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_pdf(file_path)
    elif ext == '.docx':
        return extract_docx(file_path)
    elif ext == '.txt':
        return extract_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def extract_pdf(file_path):
    """Extract text from PDF using PyPDF2 or pdfplumber"""
    # Import PyPDF2 or pdfplumber
    # Read PDF pages
    # Extract text content
    # Return cleaned text

def extract_docx(file_path):
    """Extract text from Word document using python-docx"""
    # Import python-docx
    # Read document paragraphs
    # Extract text content
    # Return cleaned text

def extract_txt(file_path):
    """Extract text from plain text file"""
    # Read file with UTF-8 encoding
    # Return content
```

**Job Parsing Logic:**
```python
def parse_job_description(text):
    """Parse job description text to extract key details"""
    # Use regex or NLP to identify:
    # - Company name (often in header or first paragraph)
    # - Job title (usually prominently displayed)
    # - Location (city, state, remote indicators)
    # - Salary (if present)
    # - Required qualifications (bullet points, "must have")
    # - Preferred qualifications (bullet points, "nice to have")
    # - Responsibilities (bullet points, "you will")
    # Return structured dictionary
```

---

### Job Verification Script (`verify_user_jobs.py`)

**Purpose:** Verify user-provided job links are active before creating resumes

**Input:**
```python
JOB_LINKS = [
    {
        'name': 'JPMorgan Chase - Job 1',
        'url': 'https://jpmc.fa.oraclecloud.com/...',
        'company': 'JPMorgan Chase'
    }
]
```

**Process:**
1. Launch headless Chromium browser
2. Navigate to job URL
3. Check HTTP status code (404 = expired)
4. Extract job details (title, location, description)
5. Look for "Apply" button or expired indicators
6. Mark as Active/Expired/Unknown

**Output:**
```json
{
  "job": "JPMorgan Chase - Job 1",
  "url": "https://...",
  "company": "JPMorgan Chase",
  "is_active": true,
  "status": "Active",
  "title": "Cybersecurity - Lead Technical Program Manager",
  "location": "Jersey City, NJ / Columbus, OH",
  "posted_date": "01/06/2026",
  "salary": "$142,500 - $190,000"
}
```

---

## Company-Specific Customization Requirements

### Universal Tailoring Framework (Applies to ALL Companies)

Every resume must be deeply customized using this research and tailoring process. This is not optional - generic resumes will not be generated.

---

### Step 1: Company Research (Required for ALL Companies)

**Research Categories:**

#### 1. Company Mission & Values
- **Where to find:**
  - Company website: `/about`, `/mission`, `/values`
  - Comparably.com, Built In, Glassdoor reviews
  - LinkedIn "About" section

- **What to extract:**
  - Mission statement (exact wording)
  - Core values (integrity, innovation, customer-first, etc.)
  - Company motto or tagline
  - Cultural principles (diversity, collaboration, excellence)

- **How to use:**
  - Reference mission in professional summary
  - Align competencies with stated values
  - Add "Alignment Statement" section at end of resume
  - Use company language throughout bullets

---

#### 2. Industry-Specific Initiatives & Programs
- **Where to find:**
  - Press releases and newsroom
  - Investor relations / annual reports
  - Tech blogs and engineering blogs
  - Recent news articles (last 6-12 months)

- **What to extract:**
  - Major security initiatives (e.g., JPMorgan's $1.5T Security Initiative)
  - Technology investments (cloud, AI, quantum, blockchain)
  - Modernization programs
  - Strategic partnerships or acquisitions
  - Industry leadership positions

- **How to use:**
  - Mention specific initiatives in professional summary
  - Connect experience to company's strategic direction
  - Show awareness of company's competitive position
  - Demonstrate alignment with technology roadmap

**Examples by Industry:**
- **Financial Services:** Risk frameworks, regulatory compliance, fraud prevention
- **Healthcare:** HIPAA, patient data protection, healthcare IT modernization
- **Federal/Defense:** Clearance requirements, FedRAMP, CMMC, zero trust
- **Technology:** Innovation, scalability, developer experience, platform security
- **Retail:** PCI-DSS, customer data protection, supply chain security

---

#### 3. Cybersecurity Team & Culture
- **Where to find:**
  - Company careers page: `/careers/cybersecurity` or `/careers/security`
  - LinkedIn: Search "Security [Company Name]" to see team members
  - Conference talks / YouTube (CISOs, security leaders)
  - Security blog posts or white papers

- **What to extract:**
  - Team structure (Cybersecurity & Technology Controls, InfoSec, Product Security)
  - Security philosophy (zero trust, defense in depth, shift-left)
  - Specific teams (threat intel, incident response, GRC, AppSec)
  - Tools and frameworks mentioned (NIST, CIS Controls, MITRE ATT&CK)

- **How to use:**
  - Use exact team names in professional summary
  - Reference their security philosophy in bullets
  - Mention frameworks they publicly discuss
  - Align experience with their team structure

---

#### 4. Job-Specific Requirements Analysis
- **Where to find:**
  - Job description (the actual posting)
  - Similar roles at same company
  - LinkedIn profiles of people in same role

- **What to extract:**
  - Required skills (ranked by frequency mentioned)
  - Specific frameworks (NIST CSF, ISO 27001, CVSS, OWASP)
  - Tools and technologies (Jira, Splunk, ServiceNow, cloud platforms)
  - Soft skills emphasized (stakeholder management, executive communication)
  - Years of experience and specific qualifications

- **How to use:**
  - Create competency list matching exact requirements
  - Reframe experience bullets to highlight those skills
  - Use same terminology as job description
  - Prioritize most-mentioned requirements in summary

---

#### 5. Compliance & Regulatory Environment
- **What to identify:**
  - **Financial Services:** SOX, GLBA, PCI-DSS, Fed regulations, OCC guidance
  - **Healthcare:** HIPAA, HITECH, FDA cybersecurity, state privacy laws
  - **Federal/Defense:** FedRAMP, NIST 800-53, CMMC, DISA STIGs, ITAR
  - **Technology:** SOC 2, ISO 27001, GDPR, CCPA, regional privacy laws
  - **Critical Infrastructure:** NERC CIP, ICS/SCADA security, sector-specific

- **How to use:**
  - Mention relevant compliance frameworks in competencies
  - Reference compliance experience in bullets
  - Show understanding of regulatory obligations
  - Demonstrate compliance program management experience

---

### Step 2: Resume Customization Formula

#### Professional Summary Template
```
[Job Title] with [X]+ years [driving/leading/managing] [specific domain] in [industry/sector].
Expertise in [3-4 key competencies from job description] while [achieving specific outcomes].
Track record of [measurable achievements] and [building/delivering/implementing] [relevant systems/programs].
Experienced in [specific frameworks/standards] and [company-relevant technologies/approaches].
[Optional: Clearance/certification statement if relevant].
[Company mission alignment or values statement].
```

**Example for Financial Services:**
> "Lead Technical Program Manager with 10+ years driving cybersecurity programs in financial services and enterprise technology. Expertise in breaking down complex security and technology objectives into executable strategies while managing cross-functional stakeholders, navigating ambiguity, and delivering resilient solutions aligned with risk & control frameworks. Track record of reducing operational risk, accelerating secure delivery, and building governance structures that enable business growth while maintaining safety, stability, and resilience. Experienced in NIST, ISO 27001, and enterprise-scale security program management supporting innovation in cloud, AI, and frontier technologies."

**Example for Federal/Defense:**
> "Senior Cybersecurity Program Manager with 10+ years leading vulnerability management, compliance, and risk remediation programs in enterprise and federal-aligned environments. Expertise in scan tracking, vulnerability assessment, and remediation prioritization using NIST CVSS scoring methodology. Proven track record coordinating cross-functional teams to deliver security initiatives aligned with federal compliance frameworks (HIPAA, FedRAMP, DISA IL5). Security clearance eligible (prior Air Force service). Experienced in building PMO structures, managing work assignment workflows, and driving timely vulnerability remediation across complex cloud-based systems."

---

#### Core Competencies by Industry

**Financial Services / Banking:**
- Risk & Control Frameworks (NIST, ISO 27001, COBIT)
- Financial Services Security Operations
- Technology Risk Governance & Reporting
- Regulatory Compliance (SOX, GLBA, Fed regulations)
- Third-Party Risk Management
- Fraud Prevention & Detection
- Payment Security (PCI-DSS)
- Anti-Money Laundering (AML) Controls
- Enterprise Security Architecture
- Change Management in Regulated Environments
- Executive Stakeholder Communication
- Audit & Regulatory Examination Support

**Healthcare / Life Sciences:**
- HIPAA & HITECH Compliance
- Healthcare Data Privacy & Protection
- Electronic Health Records (EHR) Security
- Medical Device Security
- FDA Cybersecurity Guidance
- Patient Data Governance
- Healthcare IT Risk Management
- Business Associate Agreement (BAA) Management
- Health Information Exchange (HIE) Security
- Clinical System Protection
- Healthcare Incident Response
- State Privacy Law Compliance

**Federal / Defense / Public Sector:**
- Security Clearance (Active/Eligible)
- FedRAMP Compliance & Authorization
- NIST 800-53 Controls Implementation
- DISA STIGs & Hardening Standards
- CMMC (Cybersecurity Maturity Model)
- Vulnerability Management (CVSS Scoring)
- Continuous Monitoring (ConMon)
- Authority to Operate (ATO) Process
- DoD Cybersecurity Requirements
- Government Contract Security
- ITAR & CUI Protection
- Federal Incident Response

**Technology / SaaS / Cloud:**
- Cloud Security (AWS, Azure, GCP)
- DevSecOps & Shift-Left Security
- Application Security (AppSec)
- API Security & Microservices
- Container & Kubernetes Security
- CI/CD Pipeline Security
- Infrastructure as Code (IaC) Security
- SOC 2 Type II Compliance
- Security Architecture & Design
- Threat Modeling & Risk Assessment
- Bug Bounty Program Management
- Security Champions Program

**Consulting / Professional Services:**
- Client Engagement & Relationship Management
- Security Assessment & Advisory
- Risk & Compliance Consulting
- Security Program Development
- Multi-Client Portfolio Management
- Statement of Work (SOW) Development
- Proposal & Business Development
- Industry Framework Expertise (NIST, ISO, CIS)
- Executive Advisory & Communication
- Security Roadmap Development
- Security Maturity Assessments
- Vendor & Tool Selection

---

#### Experience Bullet Reframing by Industry

**Financial Services Focus:**
- Emphasize: Risk management, regulatory compliance, audit readiness
- Terminology: "Technology risk," "control frameworks," "regulatory examination," "third-party risk"
- Metrics: Audit findings reduced, control effectiveness, risk rating improvements
- Frameworks: NIST CSF, ISO 27001, COBIT, FFIEC guidelines

**Example:**
> "Built and operationalized risk governance framework aligned with FFIEC guidelines that reduced security escalations by 17% by implementing proactive threat monitoring, vulnerability management workflows, and executive cyber-risk reporting supporting regulatory examinations and audit readiness"

---

**Healthcare Focus:**
- Emphasize: Patient data protection, HIPAA compliance, clinical system security
- Terminology: "Protected health information (PHI)," "business associate," "covered entity," "breach notification"
- Metrics: HIPAA violations prevented, patient records protected, breach response time
- Frameworks: HIPAA Security Rule, HITRUST, NIST Cybersecurity Framework

**Example:**
> "Led HIPAA compliance program protecting 2M+ patient records across 100+ healthcare clients, implementing encryption, access controls, audit logging, and breach response protocols that achieved zero reportable breaches and 100% business associate agreement (BAA) compliance during 3-year period"

---

**Federal/Defense Focus:**
- Emphasize: Clearance eligibility, federal frameworks, vulnerability remediation, ATO process
- Terminology: "Authority to Operate (ATO)," "CVSS scoring," "continuous monitoring," "impact level"
- Metrics: Vulnerabilities remediated within SLA, ATO timelines, POA&M closure rates
- Frameworks: NIST 800-53, DISA STIGs, FedRAMP, RMF

**Example:**
> "Managed FedRAMP authorization program for cloud platform supporting federal agencies, coordinating vulnerability remediation using NIST CVSS scoring (critical: 48hrs, high: 14 days), achieving Authority to Operate (ATO) at Moderate Impact Level and maintaining continuous monitoring compliance with 95% POA&M closure rate"

---

**Technology/SaaS Focus:**
- Emphasize: DevSecOps, automation, scalability, developer enablement
- Terminology: "Shift-left security," "security champions," "CI/CD pipeline," "API gateway"
- Metrics: Deployment velocity, vulnerabilities per release, MTTR, automation percentage
- Frameworks: OWASP Top 10, SANS Top 25, SOC 2, secure SDLC

**Example:**
> "Implemented DevSecOps program integrating security into CI/CD pipeline through automated SAST/DAST scanning, container vulnerability analysis, and IaC security checks, reducing critical vulnerabilities in production by 67% while maintaining 20+ daily deployments and achieving SOC 2 Type II certification"

---

**Consulting Focus:**
- Emphasize: Client delivery, multi-industry expertise, advisory capability, business development
- Terminology: "Client engagement," "statement of work," "security roadmap," "maturity assessment"
- Metrics: Client satisfaction scores, revenue/utilization, assessment delivery, recommendations implemented
- Frameworks: Multiple (demonstrate breadth): NIST, ISO, CIS, COBIT, industry-specific

**Example:**
> "Delivered cybersecurity advisory services for 25+ Fortune 500 clients across financial services, healthcare, and technology sectors, conducting security maturity assessments, developing risk-based roadmaps, and providing executive advisory that resulted in 92% client satisfaction and $3.5M in follow-on consulting revenue"

---

### Step 3: Company Color Schemes & Branding

**Color Selection:**
- **Financial Services (JPMorgan, Goldman Sachs, etc.):** Navy blue (#003366)
- **Technology (Microsoft, Google, Amazon):** Company primary color or neutral blue
- **Healthcare (Oracle Health, Epic, Cerner):** Medical blue or company brand color
- **Federal/Defense:** Patriotic blue (#002868) or neutral navy
- **Consulting (Deloitte, KPMG, PwC):** Company brand color (typically green, blue, or black)

**When in doubt:** Use conservative navy blue (#003366) - professional for all industries

---

### Step 4: Alignment Statement Template

**Structure:**
```
ALIGNMENT WITH [COMPANY NAME] MISSION

Committed to [Company's mission statement or key initiative]. Aligned with [Company's values/principles].
Ready to contribute to [specific team/program] by [specific capabilities matching job requirements].
[Optional: Additional context like clearance eligibility, industry expertise, or unique qualifications].
```

**Examples:**

**JPMorgan Chase:**
> "Committed to JPMorgan Chase's Cybersecurity & Technology Controls mission to enable business by keeping the firm safe, stable, and resilient. Aligned with the $1.5 trillion Security and Resiliency Initiative and ready to contribute to frontier technology security initiatives including AI, quantum computing, and cloud security that drive national economic security and innovation."

**Oracle Health Federal:**
> "Committed to Oracle's mission to help people see data in new ways, discover insights, and unlock endless possibilities. Aligned with Oracle Health's values of integrity, innovation, and customer satisfaction. Ready to support Oracle Health & Analytics Federal PMO in managing cybersecurity scan tracking, vulnerability remediation, and compliance initiatives for federal healthcare systems. Security clearance eligible based on prior U.S. Air Force service."

**Microsoft:**
> "Committed to Microsoft's mission to empower every person and organization on the planet to achieve more. Aligned with Microsoft's culture of growth mindset, customer obsession, and diversity & inclusion. Ready to contribute to Azure security initiatives by delivering scalable security solutions that enable cloud transformation while maintaining trust and protecting customer data."

**Amazon:**
> "Committed to Amazon's mission to be Earth's most customer-centric company. Aligned with Amazon's Leadership Principles including Customer Obsession, Dive Deep, and Deliver Results. Ready to contribute to AWS security programs by building mechanisms that enable secure innovation at scale while maintaining the highest standards of operational excellence."

---

### Step 5: Research Sources Template (Use for Every Company)

**Required Research for Each Company:**

1. **Company Website**
   - About page
   - Careers / Jobs page (especially security team pages)
   - Newsroom / Press releases (last 12 months)
   - Investor relations (if public company)
   - Blog or engineering blog

2. **Third-Party Sources**
   - Glassdoor reviews (culture insights)
   - Built In / Comparably (values, culture)
   - LinkedIn company page (recent updates, employee posts)
   - Crunchbase (for startups: funding, growth stage)

3. **Industry Analysis**
   - Recent news articles about the company
   - Analyst reports (Gartner, Forrester)
   - Conference talks by company security leaders
   - Technical blog posts or white papers

4. **Security-Specific**
   - Company security blog or portal
   - Bug bounty program page (HackerOne, Bugcrowd)
   - Security certifications page (SOC 2, ISO, FedRAMP)
   - Vulnerability disclosure policy

5. **Competitive Intelligence**
   - How do they position themselves vs competitors?
   - What security initiatives do they publicly discuss?
   - What talent are they hiring? (LinkedIn job postings)
   - What conferences do their security teams attend/speak at?

---

### Industry-Specific Customization Examples

#### Example 1: JPMorgan Chase (Financial Services)

**Research Findings:**
- Mission: Enable business by keeping firm safe, stable, resilient (CTC)
- Initiative: $1.5 trillion Security & Resiliency Initiative (quantum, AI, cybersecurity)
- Focus: Risk frameworks, stakeholder management, change management
- Frameworks: NIST, ISO 27001, Fed regulations

**Customization Applied:**
- Professional summary mentions "financial services and enterprise technology"
- Competencies include "Financial Services Security Operations" and "Technology Risk Governance"
- Bullets emphasize "risk governance framework," "executive stakeholder management," "control frameworks"
- Alignment statement references $1.5T initiative and CTC mission
- Color: Navy blue (#003366)

---

#### Example 2: Oracle Health Federal (Healthcare + Federal)

**Research Findings:**
- Mission: "Help people see data in new ways, discover insights, unlock endless possibilities"
- Values: Integrity, innovation, customer satisfaction
- Focus: Vulnerability management, CVSS scoring, federal compliance, clearance required
- Frameworks: NIST CVSS, HIPAA, FedRAMP, DISA

**Customization Applied:**
- Professional summary mentions "federal-aligned environments" and "security clearance eligible"
- Competencies include "NIST CVSS Scoring," "Federal Compliance (HIPAA, FedRAMP, DISA)"
- Bullets emphasize "vulnerability assessment," "CVSS scoring," "remediation workflows," "federal compliance"
- Military section explicitly states "Security Clearance Eligible" and "eligible for re-adjudication"
- Alignment statement references Oracle mission and clearance eligibility
- Color: Oracle red (#FF0000)

---

### Quick Reference: Tailoring Checklist for ANY Company

Before generating resume, verify you have:

- [ ] **Company mission statement** (exact wording)
- [ ] **Core values** (3-5 key principles)
- [ ] **Major initiatives** (last 12 months of news/press releases)
- [ ] **Security team structure** (team names, focus areas)
- [ ] **Job description analysis** (required skills ranked by frequency)
- [ ] **Industry frameworks** (compliance/regulatory requirements)
- [ ] **Company color** (brand color or industry-appropriate)
- [ ] **Recent news** (acquisitions, partnerships, challenges)
- [ ] **Clearance requirements** (if applicable)
- [ ] **Technology stack** (cloud platforms, tools mentioned)

Then customize:

- [ ] Professional summary mentions company initiatives
- [ ] Competencies match job requirements exactly
- [ ] Experience bullets reframed for industry/company
- [ ] Every bullet has measurable outcome
- [ ] Company-specific terminology used throughout
- [ ] Alignment statement references mission/values
- [ ] Color scheme matches company branding
- [ ] Clearance statement added (if applicable)
- [ ] No generic language or template phrases

---

## Workflow

### Step 1: Job Discovery (Manual)

**User performs LinkedIn search:**
1. Go to [linkedin.com/jobs](https://www.linkedin.com/jobs/)
2. Search: "Security Program Manager" OR "Cybersecurity Project Manager"
3. Location: Houston, TX or Remote
4. Filters:
   - Date Posted: **Past Week**
   - Job Type: Full-time
   - Experience: Mid-Senior level
5. Copy job URLs from browser address bar

**Why manual?**
- LinkedIn blocks automated scraping
- Requires login for filtered searches
- "Past Week" filter only accessible via authenticated session
- Job IDs expire quickly

---

### Step 2: Job Verification (Automated)

**Edit `verify_user_jobs.py`:**
```python
JOB_LINKS = [
    {
        'name': 'Company Name - Job Title',
        'url': 'https://...',
        'company': 'Company Name'
    }
]
```

**Run verification:**
```bash
python verify_user_jobs.py
```

**Output:** `user_job_verification.json` with verified active jobs

---

### Step 3: Resume Generation (Automated)

**Run resume generator:**
```bash
python create_deeply_tailored_resumes.py
```

**Output:**
- `DEEPLY_TAILORED_RESUMES\` directory
- Individual Word documents per job
- `TAILORED_APPLICATION_GUIDE.txt`

---

### Step 4: Application

1. Open tailored Word document
2. Review customization (summary, bullets, competencies)
3. Click embedded URL to go to application page
4. Upload resume
5. Complete application same day (early applicants prioritized)

---

## Content Standards

### Professional Summary Requirements
- **Length:** 4-6 sentences
- **Structure:**
  1. Years of experience + domain expertise
  2. Core technical competencies
  3. Track record with measurable outcomes
  4. Alignment with company initiatives/frameworks
  5. Relevant certifications or specialized knowledge

**Example (JPMorgan):**
> "Lead Technical Program Manager with 10+ years driving cybersecurity programs in financial services and enterprise technology. Expertise in breaking down complex security and technology objectives into executable strategies while managing cross-functional stakeholders, navigating ambiguity, and delivering resilient solutions aligned with risk & control frameworks. Track record of reducing operational risk, accelerating secure delivery, and building governance structures that enable business growth while maintaining safety, stability, and resilience. Experienced in NIST, ISO 27001, and enterprise-scale security program management supporting innovation in cloud, AI, and frontier technologies."

---

### Experience Bullet Point Requirements

**Format:**
- Start with action verb (Led, Managed, Drove, Built, Implemented, Delivered)
- Include scope/context (team size, budget, number of accounts)
- Describe what was done (methodology, framework, approach)
- **Always include measurable outcome** (%, number, quantifiable result)

**Bad Example:**
> "Managed security projects for clients"

**Good Example:**
> "Managed cybersecurity project portfolio overseeing vulnerability assessment, remediation tracking, and compliance delivery for 40+ enterprise implementations, coordinating scan scheduling, prioritizing findings based on risk scoring, and ensuring timely mitigation of critical and high-severity vulnerabilities"

**Outcome Requirements:**
- Percentages: 23% reduction, 17% improvement
- Numbers: 40+ implementations, 100+ accounts, 400+ employees
- Achievements: zero critical failures, 100% compliance, 93% NPS
- Scale: $25M portfolio, 63 locations, 7 years

---

### Competencies Requirements

**Structure:** 3-column table, 4 rows (12 total competencies)

**Categories:**
1. **Technical:** Specific frameworks, methodologies, tools
2. **Leadership:** Team management, stakeholder communication
3. **Domain:** Industry-specific (financial services, federal, healthcare)
4. **Compliance:** Frameworks, certifications, standards

**JPMorgan Competencies:**
- Cybersecurity Program Leadership
- Risk & Control Frameworks (NIST, ISO 27001)
- Stakeholder & Executive Communication
- Technology Risk Governance & Reporting
- Change Management in High-Pressure Environments
- Product Security Enablement
- Cloud Security & AI/ML Controls
- Threat & Vulnerability Management
- Financial Services Security Operations
- Cross-Functional Team Leadership
- Agile Program Delivery (PSM I)
- Security Architecture & Resiliency

**Oracle Competencies:**
- Vulnerability Management & Scan Tracking
- NIST CVSS Scoring & Remediation Planning
- Federal Compliance (HIPAA, FedRAMP, DISA)
- Security Clearance Eligible (Prior USAF)
- PMO Operations & Work Assignment
- Healthcare Technology Security
- Threat Intelligence & Monitoring
- Risk Assessment & Mitigation
- Oracle Systems & Cloud Security
- Incident Response Coordination
- Cross-Functional Team Leadership
- Continuous Compliance Monitoring

---

## Formatting Standards

### Document Structure
```
1. Target Position Box (centered, bordered)
   - "TARGET POSITION"
   - Job Title
   - Company | Location
   - Clickable application link

2. Header (centered)
   - Name (18pt, bold)
   - Contact info (10pt)

3. Professional Summary
   - Heading (12pt, bold, company color)
   - 4-6 sentence paragraph

4. Core Competencies
   - Heading (12pt, bold, company color)
   - 3-column table with 12 items

5. Professional Experience
   - Heading (12pt, bold, company color)
   - Job title (11pt, bold)
   - Company | Location | Dates (italic)
   - 5+ bullet points per recent role

6. Education
   - Degree | Institution | Year

7. Certifications & Training
   - Bulleted list with dates

8. Alignment Statement
   - Small section (10pt)
   - Connects to company mission
```

### Typography
- **Margins:** 0.75" all sides
- **Font:** Calibri or Arial
- **Name:** 18pt bold
- **Headings:** 12pt bold with company color
- **Body:** 10-11pt
- **Line spacing:** 1.15

### Hyperlink Formatting
```python
def add_hyperlink(paragraph, url, text):
    """Creates clickable blue underlined hyperlink"""
    # Color: #0563C1 (Word default blue)
    # Underline: single
    # Font: matches paragraph
```

---

## Quality Checklist

### Before Generating Resumes
- [ ] Jobs verified as active via Playwright
- [ ] Company research completed (culture, values, initiatives)
- [ ] Job description analyzed for key requirements
- [ ] Company-specific terminology identified
- [ ] Relevant frameworks/compliance standards noted

### Resume Content Review
- [ ] Professional summary mentions company initiatives
- [ ] Competencies aligned with job requirements
- [ ] Every bullet has measurable outcome
- [ ] Company-specific terminology used throughout
- [ ] Frameworks/standards mentioned (NIST, CVSS, ISO 27001)
- [ ] Military experience emphasizes clearance (if applicable)
- [ ] Alignment statement references company mission/values

### Technical Review
- [ ] Clickable hyperlinks working
- [ ] Formatting consistent (fonts, spacing, colors)
- [ ] No spelling/grammar errors
- [ ] File names descriptive and professional
- [ ] Document properties clean (no template metadata)

### Final Validation
- [ ] Resume opens in Microsoft Word
- [ ] Application URL links to correct job posting
- [ ] Company color scheme applied correctly
- [ ] All sections present and properly formatted
- [ ] PDF export works correctly (if needed)

---

## Limitations & Constraints

### What This System CANNOT Do
- ❌ Automatically find fresh jobs (LinkedIn requires manual search)
- ❌ Access LinkedIn "Past Week" filter without authentication
- ❌ Scrape job boards blocked by Cloudflare/bot protection
- ❌ Log into user's LinkedIn account
- ❌ Guarantee job URLs won't expire (they change frequently)
- ❌ Apply to jobs automatically (requires user action)

### What This System CAN Do
- ✅ Verify user-provided job links with Playwright
- ✅ Extract job details from active postings
- ✅ Research company culture and initiatives via web search
- ✅ Generate deeply tailored resumes with company-specific content
- ✅ Create clickable Word documents with embedded URLs
- ✅ Provide application guide with customization details
- ✅ Score jobs based on qualification match (if needed)

---

## Future Enhancements

### Potential Improvements
1. **Company Template Library:** Pre-built templates for 50+ companies
2. **Skills Gap Analysis:** Compare base resume to job requirements
3. **Cover Letter Generator:** Company-specific cover letters
4. **Application Tracker:** Spreadsheet with follow-up dates
5. **Interview Prep:** Company culture research and practice questions
6. **Salary Negotiation Data:** Market research for each role
7. **LinkedIn Profile Optimizer:** Match profile to resume
8. **Batch Processing:** Generate resumes for 10+ jobs at once

### Technical Enhancements
1. **Database Integration:** Store company research in SQLite
2. **Template Versioning:** Track resume iterations
3. **A/B Testing:** Track which resume versions get interviews
4. **OCR Integration:** Extract text from screenshot job postings
5. **API Integration:** Pull jobs from company career APIs
6. **Email Notifications:** Alert when new jobs match criteria

---

## Troubleshooting

### Common Issues

**Issue:** Playwright can't find job details
- **Solution:** Check if page requires JavaScript (wait longer for content load)
- **Solution:** Verify selectors haven't changed (Oracle/LinkedIn update page structure)

**Issue:** Resume bullets look generic
- **Solution:** Research company more deeply (press releases, investor reports)
- **Solution:** Analyze job description for specific keywords/phrases
- **Solution:** Add more measurable outcomes (%, numbers, scale)

**Issue:** Hyperlinks don't work in Word
- **Solution:** Verify OxmlElement code creates proper relationship ID
- **Solution:** Check URL format (must start with http:// or https://)
- **Solution:** Test on both Windows and Mac versions of Word

**Issue:** Job marked as expired but it's active
- **Solution:** Check if page shows "Apply" button after login
- **Solution:** Verify HTTP status code (some pages 404 for bots)
- **Solution:** Try different user agent string in Playwright

---

## Contact & Support

### Project Maintainer
Justin Washington
- Email: justinwashington@gmail.com
- LinkedIn: linkedin.com/in/justintwashington
- Location: Houston, TX

### Documentation
- **This file:** System requirements and workflow
- **TAILORED_APPLICATION_GUIDE.txt:** Resume customization details
- **Code comments:** Inline documentation in Python scripts

---

## Version History

### v1.0 (January 10, 2026)
- Initial release
- JPMorgan Chase customization
- Oracle Health Federal customization
- Playwright job verification
- Clickable Word document generation
- Company research integration
- Measurable outcome requirements

---

## License & Usage

**Purpose:** Personal job search automation
**Restrictions:**
- Do not use for bulk scraping of job sites
- Respect robots.txt and rate limits
- LinkedIn ToS prohibits automated access
- Only verify jobs user has manually found

**Recommended Usage:**
1. User manually searches LinkedIn (5-10 jobs per week)
2. System verifies job status
3. System generates tailored resumes
4. User applies same day for best results
5. Track applications in spreadsheet

---

## Success Metrics

### Key Performance Indicators
- **Jobs Verified:** 2/2 (100% success rate)
- **Resumes Generated:** 2 company-specific resumes
- **Customization Depth:** 12 competencies, 5+ bullets per role
- **Research Sources:** 10+ sources per company
- **Measurable Outcomes:** 100% of bullets include quantifiable results
- **Application Readiness:** Immediate (clickable URLs embedded)

### Target Outcomes
- **Application Speed:** Same-day application after job discovery
- **Interview Rate:** 10-20% of applications (industry average: 2-5%)
- **Response Time:** 1-2 weeks for recruiter contact
- **Offer Rate:** 5-10% of interviews

---

## References

### JPMorgan Chase
- [Cybersecurity & Technology Controls](https://www.jpmorganchase.com/careers/explore-opportunities/programs/cyber-tech-controls)
- [$1.5 Trillion Security & Resiliency Initiative](https://www.jpmorganchase.com/newsroom/press-releases/2025/jpmc-security-resiliency-initiative)
- [Company Culture & Values](https://builtin.com/company/jpmorgan-chase/faq/culture-values)
- [JPMorgan Cybersecurity Strategy](https://digitaldefynd.com/IQ/jp-morgans-cybersecurity-strategy/)

### Oracle
- [Oracle Health Security Program](https://www.oracle.com/corporate/acquisitions/cerner/security/)
- [Security Clearance Jobs](https://www.oracle.com/careers/opportunities/security-clearance-jobs-onsr/)
- [Vulnerability Management](https://www.oracle.com/corporate/security-practices/assurance/vulnerability/)
- [Oracle Mission & Values](https://workat.tech/company/oracle)
- [Company Culture Analysis](https://sloanreview.mit.edu/culture500/company/c466/Oracle)

### Technical Documentation
- [python-docx Documentation](https://python-docx.readthedocs.io/)
- [Playwright Python Documentation](https://playwright.dev/python/docs/intro)
- [OpenXML Specification](http://officeopenxml.com/anatomyofOOXML.php)

---

---

## How to Use This File in Future Sessions

### Starting a New Resume Generation Session

**Copy/paste this prompt to Claude:**

```
Read C:\Users\derri\claude.md and follow the Universal Tailoring Framework.

I have [X] job URLs to process:

1. [Company Name - Job Title]
   URL: [paste URL]

2. [Company Name - Job Title]
   URL: [paste URL]

Please:
1. Verify all jobs with Playwright (active/expired)
2. Research each company using the 5-step framework in claude.md
3. Generate deeply tailored resumes following ALL requirements
4. Include measurable outcomes, company mission alignment, and industry-specific competencies
5. No generic resumes - full customization required
```

### Quick Start Command

Simply say: **"Start resume project"** and Claude will ask you to provide job URLs, then follow the complete claude.md framework.

### Validation

After resume generation, ask Claude to validate against the Quality Checklist in claude.md (page ~560).

---

**Last Updated:** January 10, 2026
**Status:** Production Ready ✅
