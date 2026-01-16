# Job Extraction Optimization Strategy

## Current System Analysis (EXCELLENT Foundation!)

Your extraction system already implements industry best practices with a **4-layer fallback chain**:

### Layer 1: Firecrawl (Primary) ✅
- **Technology**: Firecrawl with AI-powered structured extraction
- **Strengths**:
  - Handles JavaScript rendering
  - Bypasses anti-bot protection
  - Structured schema extraction
  - High success rate on modern sites
- **Current Schema**: Company, title, description, location, salary, posted_date, employment_type, experience_level, skills_required

### Layer 2: OpenAI GPT-4.1-mini (Intelligent Fallback) ✅
- **Triggered When**: Firecrawl returns "Unknown Company" or "Unknown Position"
- **Technology**: GPT-4.1-mini with JSON mode
- **Strengths**:
  - Understands context and natural language
  - Can extract from markdown/text
  - Fast and cost-effective

### Layer 3: Playwright (Browser Automation) ✅
- **Technology**: Headless Chromium with anti-detection
- **Strengths**:
  - Handles JavaScript-heavy sites
  - Multiple extraction strategies (selectors, meta tags, URL patterns, regex)
  - Domain-specific logic (Greenhouse, Microsoft, Oracle, etc.)
- **Strategies Implemented**:
  - CSS selectors
  - Meta tags (OpenGraph)
  - URL pattern matching
  - Regex text extraction

### Layer 4: GPT-4 Vision (Screenshot API) ✅
- **Technology**: GPT-4 Turbo with Vision + Screenshot API
- **Strengths**:
  - Works on ANY site (even those blocking scrapers)
  - No browser dependencies in production
  - Extracts from visual layout
- **Fallback**: BeautifulSoup text extraction if no screenshot API

---

## Advanced Technologies to Increase Success Rate

### 1. **Perplexity API Integration** (Already Available!)

You have `perplexity_client.py` - this is GOLD for job extraction!

**Why Perplexity is Powerful:**
- Real-time web search with citations
- Can find company details even if not on job page
- Provides recent, verified information
- Better than GPT-4 for factual extraction

**Recommended Implementation:**

```python
# In firecrawl_client.py, after OpenAI fallback fails

if not company or company == 'Unknown Company':
    print("Using Perplexity to search for company info...")
    from app.services.perplexity_client import PerplexityClient

    perplexity = PerplexityClient()

    # Search for company based on job URL domain
    search_query = f"What company owns the website {extract_domain(job_url)}? Provide just the company name."
    company_info = await perplexity.search(search_query)
    company = extract_company_from_response(company_info)
```

**Use Cases:**
1. Extract company from URL domain when not visible on page
2. Verify extracted company name accuracy
3. Get additional context (company size, industry, location)

---

### 2. **Structured Data Extraction (Schema.org)**

Many job sites use structured data (JSON-LD) that's machine-readable.

**Implementation in Playwright:**

```python
async def _extract_structured_data(self, page) -> Optional[Dict]:
    """Extract job data from JSON-LD structured data"""

    # Look for JSON-LD script tags
    scripts = await page.query_selector_all('script[type="application/ld+json"]')

    for script in scripts:
        try:
            content = await script.inner_text()
            data = json.loads(content)

            # Check if it's a JobPosting schema
            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                return {
                    'company': data.get('hiringOrganization', {}).get('name', ''),
                    'title': data.get('title', ''),
                    'description': data.get('description', ''),
                    'location': data.get('jobLocation', {}).get('address', {}).get('addressLocality', ''),
                    'salary': data.get('baseSalary', {}).get('value', ''),
                    'posted_date': data.get('datePosted', ''),
                    'employment_type': data.get('employmentType', ''),
                }
        except:
            continue

    return None
```

**Why This Works:**
- **LinkedIn**: Uses JobPosting schema
- **Indeed**: Uses JobPosting schema
- **Company career pages**: Many use Schema.org
- **Google for Jobs**: Requires JobPosting markup

**Integration Point**: Add to `playwright_extractor.py` as Strategy 0 (before DOM selectors)

---

### 3. **Domain-Specific Extractors**

Create specialized extractors for high-traffic job sites.

**Sites to Target:**
1. **LinkedIn** (most common)
2. **Indeed**
3. **Greenhouse** (already partially implemented)
4. **Lever**
5. **Workday**
6. **Oracle/Taleo**
7. **SAP SuccessFactors**

**Example: LinkedIn Extractor**

```python
class LinkedInJobExtractor:
    """Specialized extractor for LinkedIn job postings"""

    LINKEDIN_SELECTORS = {
        'company': '.job-details-jobs-unified-top-card__company-name',
        'title': '.job-details-jobs-unified-top-card__job-title',
        'location': '.job-details-jobs-unified-top-card__bullet',
        'description': '.jobs-description__content',
        'posted_time': '.jobs-unified-top-card__posted-date',
    }

    async def extract(self, page) -> Dict:
        """Extract using LinkedIn-specific selectors"""
        data = {}

        for field, selector in self.LINKEDIN_SELECTORS.items():
            try:
                elem = await page.query_selector(selector)
                if elem:
                    data[field] = await elem.inner_text()
            except:
                data[field] = ''

        return data
```

**Benefits:**
- Higher accuracy for common sites
- Faster extraction (specific selectors)
- Handles site-specific quirks

---

### 4. **AI Prompt Engineering Enhancements**

Your OpenAI prompts are good, but can be optimized for higher accuracy.

**Current OpenAI Prompt Issues:**
1. Doesn't handle edge cases (company divisions, subsidiaries)
2. No confidence scoring
3. Could extract wrong company from multi-company pages

**Enhanced Prompt Strategy:**

```python
extraction_prompt = f"""You are an expert at extracting job posting information.

CONTEXT: This text is from a job posting page. Your goal is to identify the HIRING COMPANY and the exact JOB TITLE.

IMPORTANT RULES:
1. The company name should be the actual employer, not the job board
2. Ignore phrases like "powered by", "posted on", "apply via"
3. If multiple companies mentioned, choose the one hiring for this role
4. Company name should NOT include "Inc.", "LLC", "Ltd." unless essential
5. Job title should be concise, without location or company name

JOB PAGE CONTENT:
{markdown_content[:3000]}

ANALYSIS STEPS:
1. Identify all company names mentioned
2. Determine which is the hiring company (usually near job title)
3. Extract the exact job title (without suffixes like "| Company Name")
4. Rate your confidence (1-10) for each extraction

Return ONLY valid JSON:
{{
  "company": "exact company name",
  "title": "exact job title",
  "confidence": {{
    "company": 8,
    "title": 9
  }},
  "reasoning": "Brief explanation of extraction logic"
}}

Example:
{{
  "company": "Microsoft",
  "title": "Senior Cloud Security Engineer",
  "confidence": {{"company": 9, "title": 10}},
  "reasoning": "Company clearly stated in header. Job title from main H1 heading."
}}
"""
```

**Confidence Scoring Benefits:**
- Retry extraction if confidence < 7
- Trigger fallback methods earlier
- Log low-confidence extractions for analysis

---

### 5. **Multi-Model Verification**

Use multiple AI models to verify extraction accuracy.

**Strategy: Consensus Voting**

```python
async def extract_with_verification(self, job_url: str, markdown_content: str) -> Dict:
    """Extract company/title using multiple models, use consensus"""

    models = [
        "gpt-4.1-mini",      # Fast, cost-effective
        "claude-3-haiku",    # Different training data
        "gpt-4o-mini",       # Alternative GPT model
    ]

    extractions = []

    for model in models:
        try:
            result = await self._extract_with_model(model, markdown_content)
            extractions.append(result)
        except:
            continue

    # Use consensus - if 2+ models agree, use that value
    company = self._get_consensus([e['company'] for e in extractions])
    title = self._get_consensus([e['title'] for e in extractions])

    return {'company': company, 'title': title}

def _get_consensus(self, values: List[str]) -> str:
    """Get most common value from list"""
    from collections import Counter
    if not values:
        return ''

    # Count occurrences
    counts = Counter(values)

    # Return most common (if 2+ agree, use that)
    most_common = counts.most_common(1)[0]
    if most_common[1] >= 2:  # At least 2 models agree
        return most_common[0]

    # Otherwise return first extraction
    return values[0]
```

**Cost vs. Accuracy Trade-off:**
- Use single model for 80% of extractions
- Use multi-model for edge cases (low confidence, Unknown values)

---

### 6. **Caching & Rate Limiting Optimization**

**Current Implementation:** 20 requests/minute rate limit ✅

**Enhancements:**

#### A. URL Deduplication
```python
# Before extraction, check if URL already extracted recently
from hashlib import md5

def normalize_url(url: str) -> str:
    """Normalize URL for caching"""
    # Remove tracking params
    url = re.sub(r'[?&]utm_[^&]+', '', url)
    url = re.sub(r'[?&]ref=[^&]+', '', url)
    return url.lower().strip('/')

async def extract_with_cache(self, job_url: str) -> Dict:
    """Check cache before extracting"""
    normalized = normalize_url(job_url)
    cache_key = md5(normalized.encode()).hexdigest()

    # Check Redis/database cache
    cached = await self.get_cached_extraction(cache_key)
    if cached:
        print(f"✓ Using cached extraction for {job_url}")
        return cached

    # Extract fresh data
    result = await self.extract_job_details(job_url)

    # Cache for 7 days (job postings don't change often)
    await self.cache_extraction(cache_key, result, ttl=7*24*3600)

    return result
```

#### B. Smart Rate Limiting
```python
# Priority queue for extractions
class ExtractionQueue:
    """Prioritize extraction requests"""

    def __init__(self):
        self.high_priority = []  # User-initiated extractions
        self.low_priority = []   # Background/bulk extractions

    async def process(self):
        """Process high-priority first"""
        if self.high_priority:
            return await self._extract(self.high_priority.pop(0))
        elif self.low_priority:
            return await self._extract(self.low_priority.pop(0))
```

---

### 7. **Fallback to URL Pattern Matching**

When all else fails, extract from URL structure.

**Common URL Patterns:**

```python
URL_PATTERNS = {
    # LinkedIn: /jobs/view/123456789/
    r'linkedin\.com/jobs/view/(\d+)': lambda url: extract_linkedin_by_api(url),

    # Indeed: /viewjob?jk=abc123
    r'indeed\.com/viewjob\?jk=([a-zA-Z0-9]+)': lambda url: extract_indeed_by_api(url),

    # Greenhouse: /jobs/123456
    r'greenhouse\.io/([^/]+)/jobs/(\d+)': lambda url: {
        'company': url.split('/')[3].replace('-', ' ').title(),
        'job_id': url.split('/')[-1]
    },

    # Lever: /lever.co/company/job-slug
    r'jobs\.lever\.co/([^/]+)/([^/]+)': lambda url: {
        'company': url.split('/')[3].replace('-', ' ').title(),
        'title': url.split('/')[-1].replace('-', ' ').title()
    },
}

def extract_from_url_pattern(url: str) -> Optional[Dict]:
    """Extract basic info from URL structure"""
    for pattern, extractor in URL_PATTERNS.items():
        if re.search(pattern, url):
            return extractor(url)
    return None
```

---

### 8. **Company Name Normalization**

Ensure consistent company naming across extractions.

```python
COMPANY_ALIASES = {
    'jpmorgan chase & co': 'JPMorgan Chase',
    'jpmorgan': 'JPMorgan Chase',
    'chase': 'JPMorgan Chase',
    'microsoft corporation': 'Microsoft',
    'msft': 'Microsoft',
    'amazon.com': 'Amazon',
    'aws': 'Amazon Web Services',
    'google llc': 'Google',
    'alphabet': 'Google',
}

def normalize_company_name(company: str) -> str:
    """Normalize company name to canonical form"""
    company_lower = company.lower().strip()

    # Check aliases
    if company_lower in COMPANY_ALIASES:
        return COMPANY_ALIASES[company_lower]

    # Remove common suffixes
    company = re.sub(r'\s+(Inc\.?|LLC|Ltd\.?|Corporation|Corp\.?)$', '', company, flags=re.IGNORECASE)

    # Title case
    return company.strip().title()
```

---

## Recommended Implementation Priority

### Phase 1: High-Impact, Low-Effort (Implement This Week) 🎯

1. **Add Structured Data Extraction** to Playwright
   - File: `playwright_extractor.py`
   - Add `_extract_structured_data()` as first strategy
   - Estimated time: 2 hours
   - Success rate improvement: +15-20%

2. **Enhance OpenAI Prompts** with confidence scoring
   - File: `firecrawl_client.py` (line 190-201)
   - Add confidence field to extraction
   - Retry if confidence < 7
   - Estimated time: 1 hour
   - Success rate improvement: +10%

3. **Add Company Name Normalization**
   - File: New `app/utils/company_normalizer.py`
   - Import in all extractors
   - Estimated time: 1 hour
   - Consistency improvement: +30%

### Phase 2: Medium-Impact, Medium-Effort (Next 2 Weeks) 🚀

4. **Implement Domain-Specific Extractors**
   - LinkedIn extractor (highest priority - most common)
   - Indeed extractor
   - Greenhouse extractor (enhance existing)
   - Estimated time: 6-8 hours
   - Success rate improvement: +20% for supported sites

5. **Add Perplexity Fallback** for company verification
   - Integrate after OpenAI fallback
   - Use for Unknown Company cases
   - Estimated time: 2 hours
   - Success rate improvement: +5-10%

6. **Implement URL Pattern Matching**
   - Add as final fallback before error
   - Extract basic info from URL structure
   - Estimated time: 3 hours
   - Success rate improvement: +5%

### Phase 3: Advanced Optimization (Ongoing) 🔬

7. **Multi-Model Verification** (for edge cases)
   - Use only when single model has low confidence
   - Estimated time: 4 hours
   - Accuracy improvement: +5% on edge cases

8. **Extraction Caching** with Redis
   - Cache successful extractions for 7 days
   - Reduces API costs by 60-80%
   - Estimated time: 3-4 hours

9. **Analytics & Monitoring**
   - Log extraction success/failure rates by domain
   - Identify patterns in failures
   - Add to database for analysis
   - Estimated time: 4 hours

---

## Specific Code Improvements

### 1. Enhanced Firecrawl Client (firecrawl_client.py)

**Current Issue:** OpenAI fallback uses only first 3000 characters

**Improvement:**
```python
# Line 193 - Increase context window
extraction_prompt = f"""Extract the company name and job title from this job posting.

Job Posting Content:
{markdown_content[:8000]}  # INCREASED from 3000

Additional Context (if available):
- URL: {job_url}
- Domain: {extract_domain(job_url)}

Return ONLY a JSON object with this structure:
{{
  "company": "exact company name (not the job board)",
  "title": "exact job title (without company name or location)",
  "confidence": {{
    "company": 1-10,
    "title": 1-10
  }}
}}

IMPORTANT:
- Extract the HIRING COMPANY, not the job board (e.g., "Microsoft" not "LinkedIn")
- If company name includes domain (e.g., "microsoft.com"), extract just "Microsoft"
- Remove suffixes like Inc., LLC, Corporation unless essential
"""
```

### 2. Playwright Extractor Enhancement (playwright_extractor.py)

**Add at line 56 (before existing strategies):**

```python
# PRIORITY 0: Check for structured data (JSON-LD)
structured_data = await self._extract_structured_data(page)
if structured_data:
    print(f"[Playwright] Using structured data extraction")
    return structured_data

# Continue with existing strategies...
```

**Add new method:**

```python
async def _extract_structured_data(self, page) -> Optional[Dict[str, str]]:
    """Extract from Schema.org JSON-LD structured data"""
    try:
        scripts = await page.query_selector_all('script[type="application/ld+json"]')

        for script in scripts:
            try:
                content = await script.inner_text()
                data = json.loads(content)

                # Handle both single object and array
                if isinstance(data, list):
                    data = next((d for d in data if d.get('@type') == 'JobPosting'), None)

                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    return {
                        'company': data.get('hiringOrganization', {}).get('name', ''),
                        'title': data.get('title', ''),
                        'description': data.get('description', ''),
                        'location': self._extract_location_from_schema(data),
                        'salary': self._extract_salary_from_schema(data),
                    }
            except (json.JSONDecodeError, KeyError):
                continue

        return None
    except Exception as e:
        print(f"[Playwright] Structured data extraction failed: {e}")
        return None

def _extract_location_from_schema(self, data: dict) -> str:
    """Extract location from JobPosting schema"""
    job_location = data.get('jobLocation', {})

    if isinstance(job_location, dict):
        address = job_location.get('address', {})
        if isinstance(address, dict):
            city = address.get('addressLocality', '')
            state = address.get('addressRegion', '')
            return f"{city}, {state}".strip(', ')

    return ''

def _extract_salary_from_schema(self, data: dict) -> str:
    """Extract salary from JobPosting schema"""
    base_salary = data.get('baseSalary', {})

    if isinstance(base_salary, dict):
        value = base_salary.get('value', {})
        if isinstance(value, dict):
            min_val = value.get('minValue', '')
            max_val = value.get('maxValue', '')
            currency = base_salary.get('currency', '$')
            if min_val and max_val:
                return f"{currency}{min_val:,} - {currency}{max_val:,}"

    return ''
```

---

## Success Metrics to Track

**Add to database schema:**

```sql
CREATE TABLE job_extraction_analytics (
    id SERIAL PRIMARY KEY,
    job_url TEXT,
    domain TEXT,
    extraction_method TEXT,  -- 'firecrawl', 'openai', 'playwright', 'vision'
    success BOOLEAN,
    company_extracted TEXT,
    title_extracted TEXT,
    confidence_score FLOAT,
    extraction_time_ms INT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Query to find low-performing domains
SELECT
    domain,
    COUNT(*) as attempts,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
    ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM job_extraction_analytics
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY domain
ORDER BY attempts DESC
LIMIT 20;
```

**Key Metrics:**
- Overall success rate (target: >95%)
- Success rate by domain
- Average extraction time
- Method usage distribution
- Common failure patterns

---

## Expected Results After Implementation

### Current Performance (Estimated)
- **Overall Success Rate**: 85-90%
- **LinkedIn**: 90%
- **Indeed**: 85%
- **Company Career Pages**: 75%
- **Greenhouse**: 95%
- **Unknown Sites**: 70%

### After Phase 1 (Quick Wins)
- **Overall Success Rate**: 92-95%
- **LinkedIn**: 98% (structured data)
- **Indeed**: 95% (structured data)
- **Company Career Pages**: 85%
- **Greenhouse**: 98%
- **Unknown Sites**: 75%

### After Phase 2 (Domain-Specific)
- **Overall Success Rate**: 96-98%
- **LinkedIn**: 99%
- **Indeed**: 98%
- **Company Career Pages**: 92%
- **Greenhouse**: 99%
- **Unknown Sites**: 85%

### After Phase 3 (Full Optimization)
- **Overall Success Rate**: 98%+
- **All Major Sites**: 99%+
- **Company Career Pages**: 95%+
- **Unknown Sites**: 90%+

---

## Cost Analysis

**Current Costs (per 1000 extractions):**
- Firecrawl: ~$5-10 (depends on tier)
- OpenAI GPT-4.1-mini fallback: ~$0.50
- Playwright: Minimal (compute only)
- Vision: ~$3-5 (if using screenshot API)

**Estimated Monthly (1000 users, 3 jobs each):**
- 3000 extractions/month
- Cost: $20-30/month

**After Caching (Phase 3):**
- 60% cache hit rate
- 1200 fresh extractions/month
- Cost: $8-12/month
- **Savings: $12-18/month** (60% reduction)

---

## Monitoring & Debugging

**Add logging to track extraction flow:**

```python
import logging
from datetime import datetime

class ExtractionLogger:
    """Log extraction attempts for debugging and analytics"""

    def __init__(self):
        self.logger = logging.getLogger('job_extraction')

    async def log_attempt(self, job_url: str, method: str, success: bool, data: dict):
        """Log extraction attempt"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'url': job_url,
            'domain': extract_domain(job_url),
            'method': method,
            'success': success,
            'company': data.get('company', ''),
            'title': data.get('title', ''),
            'confidence': data.get('confidence', {}),
        }

        # Log to file
        self.logger.info(json.dumps(log_entry))

        # Log to database for analytics
        await self.save_to_database(log_entry)
```

---

## Recommended Next Steps

1. **This Week:**
   - Add structured data extraction to Playwright ✅
   - Enhance OpenAI prompts with confidence scoring ✅
   - Add company name normalization ✅

2. **Next Week:**
   - Implement LinkedIn-specific extractor
   - Add extraction analytics to database
   - Set up monitoring dashboard

3. **Next Month:**
   - Add Indeed extractor
   - Implement caching layer
   - Add Perplexity fallback for edge cases

4. **Ongoing:**
   - Monitor success rates by domain
   - Add domain-specific extractors as needed
   - Optimize prompts based on failure patterns

---

## Questions to Consider

1. **Which job sites do your users extract from most often?**
   - Prioritize domain-specific extractors for top 5 sites

2. **What's your acceptable cost per extraction?**
   - Determines which fallback methods to use

3. **Do you need real-time extraction or can it be async?**
   - Async allows for retry logic and better error handling

4. **Should extraction failures block resume tailoring?**
   - Current approach (return empty fields) is good - allows manual input

---

This document provides a comprehensive roadmap to achieve **98%+ extraction success rate** while maintaining cost efficiency. The current system is already excellent - these enhancements will make it world-class.
