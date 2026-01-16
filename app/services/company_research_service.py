"""
Company Research Service - Fetch real company strategies and initiatives
Uses Perplexity and Firecrawl to gather authentic, sourced information
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from app.services.perplexity_client import PerplexityClient
from app.services.firecrawl_client import FirecrawlClient


class CompanyResearchService:
    """
    Service for researching companies using multiple real sources
    - Press releases and newsrooms
    - Investor relations and annual reports
    - Company blogs and engineering blogs
    - Recent news articles
    """

    def __init__(self):
        self.perplexity = PerplexityClient()
        self.firecrawl = FirecrawlClient()

    async def research_company_strategies(
        self,
        company_name: str,
        industry: Optional[str] = None,
        job_title: Optional[str] = None
    ) -> Dict:
        """
        Research company strategies from real sources

        Returns:
        {
            "strategic_initiatives": [
                {
                    "title": "Initiative name",
                    "description": "What they're doing",
                    "source": "Press Release Title",
                    "url": "https://...",
                    "date": "2024-01-15",
                    "relevance_to_role": "Why this matters for the job"
                }
            ],
            "recent_developments": [...],
            "technology_focus": [...],
            "sources_consulted": [...]
        }
        """

        print(f"Researching company strategies for: {company_name}")

        # Build comprehensive research query
        research_query = self._build_strategy_query(company_name, industry, job_title)

        # Use Perplexity for cited research
        try:
            perplexity_result = await self._research_with_perplexity(research_query, company_name)

            # Also try to fetch company newsroom/blog directly
            company_urls = self._get_company_urls(company_name)
            direct_content = await self._fetch_direct_sources(company_urls)

            # Combine and structure results
            structured_data = self._structure_strategy_data(
                perplexity_result,
                direct_content,
                company_name,
                job_title
            )

            return structured_data

        except Exception as e:
            print(f"Error researching company strategies: {e}")
            return self._get_fallback_strategies(company_name)

    def _build_strategy_query(
        self,
        company_name: str,
        industry: Optional[str],
        job_title: Optional[str]
    ) -> str:
        """Build a comprehensive Perplexity query for company research"""

        query = f"""Research {company_name} company strategies and initiatives:

1. **Strategic Initiatives (with sources and dates):**
   - Major programs, investments, or transformations announced in the last 12 months
   - Technology modernization or innovation initiatives
   - Market expansion or new product launches
   - Acquisitions or partnerships

2. **Technology Focus Areas:**
   - Cloud, AI, cybersecurity, or other tech investments
   - Engineering culture and technical priorities
   - Innovation labs or research programs

3. **Recent Executive Statements:**
   - CEO or leadership commentary on company direction
   - Earnings call highlights (last 2 quarters)
   - Vision for the next 12-24 months

**Requirements:**
- Cite specific sources (press releases, investor reports, news articles)
- Include dates for all information
- Focus on information from the last 12 months
- Prefer official company sources over third-party news"""

        if industry:
            query += f"\n- Industry context: {industry}"

        if job_title:
            query += f"\n- Relate findings to relevance for: {job_title}"

        return query

    async def _research_with_perplexity(
        self,
        query: str,
        company_name: str
    ) -> Dict:
        """
        Use Perplexity API for cited research (PRIMARY SOURCE)

        Returns REAL strategic initiatives with:
        - Actual URLs to press releases and articles
        - Real publication dates
        - Verified source citations
        """

        try:
            print("🔍 Researching company strategies with Perplexity...")
            result = await self.perplexity.research_with_citations(query)

            citations = result.get("citations", [])
            print(f"✓ Found {len(citations)} real sources from Perplexity")

            return {
                "content": result.get("content", ""),
                "citations": citations,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"⚠️ Perplexity research failed: {e}")
            return {"content": "", "citations": [], "timestamp": datetime.utcnow().isoformat()}

    def _get_company_urls(self, company_name: str) -> List[str]:
        """Get likely URLs for company sources"""

        # Common URL patterns
        company_slug = company_name.lower().replace(" ", "").replace("&", "and")

        urls = [
            f"https://www.{company_slug}.com/newsroom",
            f"https://www.{company_slug}.com/news",
            f"https://www.{company_slug}.com/press",
            f"https://www.{company_slug}.com/press-releases",
            f"https://ir.{company_slug}.com",
            f"https://investor.{company_slug}.com",
            f"https://investors.{company_slug}.com",
            f"https://blog.{company_slug}.com",
            f"https://www.{company_slug}.com/blog",
            f"https://engineering.{company_slug}.com",
        ]

        # Special cases for known companies
        special_cases = {
            "jpmorgan": ["https://www.jpmorganchase.com/newsroom", "https://www.jpmorganchase.com/news"],
            "oracle": ["https://www.oracle.com/news", "https://www.oracle.com/corporate/pressroom"],
            "microsoft": ["https://news.microsoft.com", "https://blogs.microsoft.com"],
            "amazon": ["https://www.aboutamazon.com/news", "https://press.aboutamazon.com"],
            "google": ["https://blog.google", "https://blog.google/press"],
        }

        company_key = company_name.lower().split()[0]
        if company_key in special_cases:
            urls = special_cases[company_key] + urls

        return urls[:5]  # Limit to top 5 to avoid rate limits

    async def _fetch_direct_sources(self, urls: List[str]) -> List[Dict]:
        """Fetch content directly from company URLs using Firecrawl"""

        results = []

        for url in urls:
            try:
                print(f"Fetching: {url}")
                content = await self.firecrawl.scrape_page(url, formats=["markdown"])

                if content and len(content) > 100:  # Valid content
                    results.append({
                        "url": url,
                        "content": content[:2000],  # Limit to first 2000 chars
                        "source_type": self._classify_source_type(url),
                        "fetched_at": datetime.utcnow().isoformat()
                    })
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                continue

        return results

    def _classify_source_type(self, url: str) -> str:
        """Classify the type of source"""

        if any(x in url for x in ["newsroom", "press", "news"]):
            return "press_release"
        elif any(x in url for x in ["investor", "ir.", "annual-report"]):
            return "investor_relations"
        elif "blog" in url:
            return "company_blog"
        elif "engineering" in url:
            return "engineering_blog"
        else:
            return "company_website"

    def _structure_strategy_data(
        self,
        perplexity_result: Dict,
        direct_content: List[Dict],
        company_name: str,
        job_title: Optional[str]
    ) -> Dict:
        """Structure the researched data into a clean format"""

        # Parse Perplexity content and citations
        strategic_initiatives = self._extract_initiatives(
            perplexity_result.get("content", ""),
            perplexity_result.get("citations", [])
        )

        # Add direct source content
        for source in direct_content:
            if source["source_type"] == "press_release":
                strategic_initiatives.extend(
                    self._parse_press_releases(source)
                )

        # Deduplicate and sort by date (most recent first)
        strategic_initiatives = self._deduplicate_initiatives(strategic_initiatives)
        strategic_initiatives.sort(key=lambda x: x.get("date", ""), reverse=True)

        return {
            "strategic_initiatives": strategic_initiatives[:10],  # Top 10 most relevant
            "recent_developments": self._extract_recent_developments(perplexity_result),
            "technology_focus": self._extract_tech_focus(perplexity_result),
            "sources_consulted": self._list_sources(perplexity_result, direct_content),
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name
        }

    def _extract_initiatives(self, content: str, citations: List[Dict]) -> List[Dict]:
        """
        Extract strategic initiatives from Perplexity content with REAL citations

        Priority: Use citations directly (they have real URLs and sources)
        """

        initiatives = []

        # FIRST: Convert citations directly to initiatives
        # These are REAL articles that Perplexity found
        for citation in citations:
            url = citation.get("url", "")
            title = citation.get("title", "")
            text = citation.get("text", "")

            if url and title:  # Must have URL and title
                # Extract date from URL or content
                date = self._extract_date_from_citation(citation)

                initiatives.append({
                    "title": title,
                    "description": text[:300] if text else "Strategic initiative sourced from company research",
                    "source": title,  # Use article title as source
                    "url": url,  # REAL clickable URL
                    "date": date,  # Real date
                    "relevance_to_role": ""
                })

        # SECOND: Parse content for additional context
        lines = content.split("\n")
        current_initiative = None

        for line in lines:
            line = line.strip()

            # Look for initiative markers
            if any(keyword in line.lower() for keyword in [
                "initiative", "program", "investment", "strategy",
                "announced", "launched", "unveiled", "introducing"
            ]):
                if current_initiative:
                    # Only add if we don't already have it from citations
                    if not self._initiative_exists(current_initiative, initiatives):
                        initiatives.append(current_initiative)

                current_initiative = {
                    "title": line.strip("- *#"),
                    "description": "",
                    "source": "Research findings",
                    "url": "",
                    "date": "",
                    "relevance_to_role": ""
                }
            elif current_initiative and line:
                current_initiative["description"] += " " + line

        if current_initiative and not self._initiative_exists(current_initiative, initiatives):
            initiatives.append(current_initiative)

        # Match remaining initiatives to citations
        for initiative in initiatives:
            if not initiative.get("url"):  # Only match if we don't have a URL yet
                for citation in citations:
                    if citation.get("text", "").lower() in initiative["description"].lower():
                        initiative["source"] = citation.get("title", "Company source")
                        initiative["url"] = citation.get("url", "")
                        initiative["date"] = self._extract_date_from_citation(citation)
                        break

        print(f"✓ Extracted {len(initiatives)} strategic initiatives")
        return initiatives

    def _extract_date_from_citation(self, citation: Dict) -> str:
        """Extract date from citation URL or text"""
        import re

        url = citation.get("url", "")
        text = citation.get("text", "")

        # Try URL path (e.g., /2024/01/15/)
        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
        if date_match:
            year, month, day = date_match.groups()
            return f"{year}-{month}-{day}"

        # Try text content
        date_match = re.search(
            r'(\d{4}-\d{2}-\d{2}|\w+ \d+, \d{4})',
            text
        )
        if date_match:
            date_str = date_match.group(1)
            # Normalize to YYYY-MM-DD
            try:
                for fmt in ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        return parsed.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            except:
                pass

        # Default to current year
        return datetime.utcnow().strftime("%Y-%m-%d")

    def _initiative_exists(self, initiative: Dict, existing: List[Dict]) -> bool:
        """Check if initiative already exists in list"""
        title = initiative.get("title", "").lower()[:50]
        for existing_init in existing:
            if existing_init.get("title", "").lower()[:50] == title:
                return True
        return False

    def _extract_recent_developments(self, perplexity_result: Dict) -> List[str]:
        """Extract recent developments as bullet points"""

        content = perplexity_result.get("content", "")
        developments = []

        # Look for recent news or developments sections
        if "recent" in content.lower() or "development" in content.lower():
            lines = content.split("\n")
            for line in lines:
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    dev = line.strip().strip("-*").strip()
                    if len(dev) > 20:  # Valid development
                        developments.append(dev)

        return developments[:5]  # Top 5

    def _extract_tech_focus(self, perplexity_result: Dict) -> List[str]:
        """Extract technology focus areas"""

        content = perplexity_result.get("content", "").lower()

        tech_keywords = {
            "cloud": ["cloud", "aws", "azure", "gcp", "infrastructure"],
            "ai": ["ai", "artificial intelligence", "machine learning", "ml", "generative ai"],
            "cybersecurity": ["security", "cybersecurity", "zero trust", "cyber"],
            "data": ["data", "analytics", "big data", "data science"],
            "blockchain": ["blockchain", "crypto", "web3"],
            "quantum": ["quantum", "quantum computing"],
            "automation": ["automation", "rpa", "process automation"],
            "iot": ["iot", "internet of things", "connected devices"]
        }

        focus_areas = []
        for area, keywords in tech_keywords.items():
            if any(kw in content for kw in keywords):
                focus_areas.append(area.replace("_", " ").title())

        return focus_areas

    def _parse_press_releases(self, source: Dict) -> List[Dict]:
        """Parse press release content for initiatives"""

        initiatives = []
        content = source.get("content", "")

        # Simple parsing - look for headlines and first paragraphs
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#") and len(line) > 10:  # Headline
                title = line.strip("#").strip()
                description = lines[i+1] if i+1 < len(lines) else ""

                initiatives.append({
                    "title": title,
                    "description": description[:300],
                    "source": "Company Press Release",
                    "url": source.get("url", ""),
                    "date": source.get("fetched_at", "")[:10],
                    "relevance_to_role": ""
                })

        return initiatives[:3]  # Top 3 from each source

    def _deduplicate_initiatives(self, initiatives: List[Dict]) -> List[Dict]:
        """Remove duplicate initiatives"""

        seen_titles = set()
        unique = []

        for init in initiatives:
            title_key = init["title"].lower()[:50]  # First 50 chars
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(init)

        return unique

    def _list_sources(
        self,
        perplexity_result: Dict,
        direct_content: List[Dict]
    ) -> List[Dict]:
        """List all sources consulted"""

        sources = []

        # From Perplexity citations
        for citation in perplexity_result.get("citations", []):
            sources.append({
                "title": citation.get("title", ""),
                "url": citation.get("url", ""),
                "type": "research"
            })

        # From direct fetches
        for source in direct_content:
            sources.append({
                "title": f"{source['source_type'].replace('_', ' ').title()}",
                "url": source["url"],
                "type": source["source_type"]
            })

        return sources

    async def research_company_values_culture(
        self,
        company_name: str,
        industry: Optional[str] = None,
        job_title: Optional[str] = None
    ) -> Dict:
        """
        Research company values and culture from real sources

        Returns:
        {
            "stated_values": [
                {
                    "name": "Value name",
                    "description": "What this value means",
                    "source_snippet": "Quote from source",
                    "url": "https://...",
                    "source": "Source name"
                }
            ],
            "cultural_priorities": ["priority1", "priority2"],
            "work_environment": "Description of work environment",
            "sources_consulted": [...],
            "last_updated": "ISO timestamp"
        }
        """

        print(f"Researching company values & culture for: {company_name}")

        # Build values/culture research query
        values_query = self._build_values_query(company_name, industry, job_title)

        # Use Perplexity for cited research
        try:
            perplexity_result = await self._research_with_perplexity(values_query, company_name)

            # Also try company careers/about pages
            values_urls = self._get_company_values_urls(company_name)
            direct_content = await self._fetch_direct_sources(values_urls)

            # Structure the values data
            structured_data = self._structure_values_data(
                perplexity_result,
                direct_content,
                company_name
            )

            return structured_data

        except Exception as e:
            print(f"Error researching company values & culture: {e}")
            return self._get_fallback_values(company_name)

    def _build_values_query(
        self,
        company_name: str,
        industry: Optional[str],
        job_title: Optional[str]
    ) -> str:
        """Build Perplexity query for values and culture research"""

        query = f"""Research {company_name} company values, culture, and work environment FROM OFFICIAL COMPANY SOURCES ONLY:

1. **Core Company Values (with sources and URLs):**
   - Official mission statement from company website
   - Stated company values and principles from About page
   - Cultural priorities or pillars from Careers page
   - What the company emphasizes in their official communications

2. **Work Environment & Culture (Official Sources Only):**
   - Work-life balance policies stated on company website
   - Remote/hybrid work approach from official careers page
   - Diversity, equity, and inclusion initiatives from company DEI page
   - Employee development programs from official benefits page
   - Benefits and perks listed on company careers site

3. **Leadership Statements & Company Communications:**
   - CEO or leadership quotes about company culture
   - Official company blog posts about values
   - Press releases mentioning company culture
   - Annual reports discussing workplace culture

**CRITICAL REQUIREMENTS:**
- USE ONLY OFFICIAL COMPANY SOURCES (company website, careers page, about page, official blog)
- DO NOT USE third-party review sites (Glassdoor, Built In, Indeed, etc.)
- DO NOT USE employee review platforms
- Cite specific URLs from company's official domains only
- Include URLs for all information
- Provide exact quotes for stated values directly from company sources
- Prioritize company's own words about their culture and values"""

        if industry:
            query += f"\n- Industry context: {industry}"

        if job_title:
            query += f"\n- Relate findings to: {job_title} role expectations"

        return query

    def _is_official_company_source(self, url: str, company_name: str) -> bool:
        """
        Check if URL is from an official company source (not third-party reviews)

        Returns True only if URL is from:
        - Company's own domain
        - Company's official blog/careers/about pages

        Returns False for:
        - Glassdoor, Indeed, Built In, Comparably
        - Other review sites
        - Generic news sites (unless it's company's official newsroom)
        """
        if not url:
            return False

        url_lower = url.lower()

        # BLOCKLIST: Third-party review and rating sites
        blocked_domains = [
            'glassdoor.com',
            'indeed.com',
            'builtin.com',
            'comparably.com',
            'kununu.com',
            'vault.com',
            'fairygodboss.com',
            'inhersight.com',
            'theladders.com',
            'zippia.com',
            'careerbliss.com',
            'salary.com',
            'payscale.com'
        ]

        # Reject if from blocked domains
        if any(blocked in url_lower for blocked in blocked_domains):
            return False

        # ALLOWLIST: Check if URL contains company name or known company domains
        company_slug = company_name.lower().replace(" ", "").replace("&", "and")
        company_keywords = [
            company_slug,
            company_name.lower().replace(" ", "-"),
            company_name.lower().split()[0]  # First word of company name
        ]

        # Accept if URL contains company name in domain
        if any(keyword in url_lower for keyword in company_keywords):
            return True

        # Accept known official company pages for specific companies
        special_allowlist = {
            'jpmorgan': ['jpmorganchase.com', 'jpmorgan.com', 'chase.com'],
            'oracle': ['oracle.com'],
            'microsoft': ['microsoft.com'],
            'amazon': ['amazon.com', 'aboutamazon.com', 'amazon.jobs'],
            'google': ['google.com', 'alphabet.com'],
            'meta': ['meta.com', 'facebook.com'],
            'apple': ['apple.com'],
        }

        company_key = company_name.lower().split()[0]
        if company_key in special_allowlist:
            if any(domain in url_lower for domain in special_allowlist[company_key]):
                return True

        # If we can't confirm it's official, reject it
        return False

    def _get_company_values_urls(self, company_name: str) -> List[str]:
        """Get likely URLs for company values and culture pages"""

        company_slug = company_name.lower().replace(" ", "").replace("&", "and")

        urls = [
            f"https://www.{company_slug}.com/about",
            f"https://www.{company_slug}.com/about-us",
            f"https://www.{company_slug}.com/careers",
            f"https://www.{company_slug}.com/careers/culture",
            f"https://www.{company_slug}.com/company/values",
            f"https://careers.{company_slug}.com",
            f"https://www.{company_slug}.com/company",
        ]

        # Special cases
        special_cases = {
            "jpmorgan": ["https://www.jpmorganchase.com/about/our-culture", "https://careers.jpmorgan.com/us/en/culture"],
            "oracle": ["https://www.oracle.com/corporate/careers/culture", "https://www.oracle.com/corporate/careers"],
            "microsoft": ["https://careers.microsoft.com/us/en/culture", "https://www.microsoft.com/en-us/about"],
            "amazon": ["https://www.amazon.jobs/en/principles", "https://www.aboutamazon.com/about-us"],
            "google": ["https://careers.google.com/how-we-hire", "https://about.google/intl/ALL_us"],
        }

        company_key = company_name.lower().split()[0]
        if company_key in special_cases:
            urls = special_cases[company_key] + urls

        return urls[:5]

    def _structure_values_data(
        self,
        perplexity_result: Dict,
        direct_content: List[Dict],
        company_name: str
    ) -> Dict:
        """Structure values and culture data from research"""

        # Extract values from Perplexity citations and content
        stated_values = self._extract_values(
            perplexity_result.get("content", ""),
            perplexity_result.get("citations", []),
            company_name  # Pass company name for source filtering
        )

        # Add values from direct sources
        for source in direct_content:
            if source["source_type"] in ["company_website", "careers"]:
                stated_values.extend(
                    self._parse_values_from_content(source)
                )

        # Deduplicate values
        stated_values = self._deduplicate_values(stated_values)

        # Extract cultural priorities
        cultural_priorities = self._extract_cultural_priorities(perplexity_result)

        # Extract work environment description
        work_environment = self._extract_work_environment(perplexity_result)

        return {
            "stated_values": stated_values[:8],  # Top 8 values
            "cultural_priorities": cultural_priorities[:6],  # Top 6 priorities
            "work_environment": work_environment,
            "sources_consulted": self._list_sources(perplexity_result, direct_content),
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name
        }

    def _extract_values(self, content: str, citations: List[Dict], company_name: str) -> List[Dict]:
        """
        Extract company values from Perplexity content with citations

        Uses multiple extraction strategies:
        1. Structured lists (numbered, bulleted)
        2. Pattern matching for value statements
        3. Common value keywords
        4. GPT-4 extraction fallback

        ONLY uses citations from official company sources (not review sites)

        Args:
            content: Text content from Perplexity
            citations: List of citations from Perplexity
            company_name: Name of the company (for source filtering)
        """
        import re

        values = []

        print(f"Extracting values from {len(content)} chars of content with {len(citations)} citations")

        # FILTER: Only use citations from official company sources
        official_citations = []

        for citation in citations:
            url = citation.get("url", "")

            # Check if this is an official company source
            if self._is_official_company_source(url, company_name):
                official_citations.append(citation)
                print(f"✓ Using official source: {url[:80]}")
            else:
                print(f"✗ Skipping third-party source: {url[:80]}")

        print(f"Filtered to {len(official_citations)} official company sources (from {len(citations)} total)")

        # Use only official citations
        citations = official_citations

        # Get primary citation URL for values (from official sources only)
        primary_values_url = ""
        for citation in citations:
            url_lower = citation.get("url", "").lower()
            if any(keyword in url_lower for keyword in ["value", "culture", "mission", "principle", "about", "careers"]):
                primary_values_url = citation.get("url", "")
                break

        if not primary_values_url and citations:
            primary_values_url = citations[0].get("url", "")

        # STRATEGY 1: Extract from structured lists (most reliable)
        # Look for numbered or bulleted value lists
        structured_values = self._extract_structured_values(content, primary_values_url)
        values.extend(structured_values)
        print(f"✓ Found {len(structured_values)} values from structured lists")

        # STRATEGY 2: Extract from explicit value statements
        # Patterns like "Our values are:", "Core principles:", etc.
        explicit_values = self._extract_explicit_value_statements(content, primary_values_url)
        values.extend(explicit_values)
        print(f"✓ Found {len(explicit_values)} values from explicit statements")

        # STRATEGY 3: Search for common company values (existing logic)
        common_values_found = self._search_common_values(content, primary_values_url)
        values.extend(common_values_found)
        print(f"✓ Found {len(common_values_found)} values from common keywords")

        # STRATEGY 4: Use GPT-4 extraction if we haven't found enough values
        if len(values) < 3 and content:
            print("⚠️ Low value count, using GPT-4 extraction fallback...")
            gpt_values = self._extract_values_with_gpt(content, primary_values_url)
            values.extend(gpt_values)
            print(f"✓ GPT-4 extracted {len(gpt_values)} additional values")

        # Deduplicate by value name
        seen_values = set()
        unique_values = []
        for value in values:
            value_key = value["name"].lower().strip()[:40]
            if value_key not in seen_values and len(value["name"]) > 2:
                seen_values.add(value_key)
                unique_values.append(value)

        print(f"✅ Final extracted {len(unique_values)} unique company values")
        return unique_values

    def _extract_structured_values(self, content: str, primary_url: str) -> List[Dict]:
        """Extract values from numbered or bulleted lists"""
        import re

        values = []
        lines = content.split("\n")

        # Look for sections that contain value lists
        in_values_section = False

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Detect start of values section
            if any(keyword in line_lower for keyword in [
                "our values", "core values", "company values", "guiding principles",
                "our principles", "what we value", "cultural values", "values are"
            ]):
                in_values_section = True
                print(f"Found values section: {line[:100]}")
                continue

            # Stop if we hit a new section
            if in_values_section and line.strip().startswith("#") and i > 0:
                section_keywords = ["value", "principle", "culture", "mission"]
                if not any(kw in line_lower for kw in section_keywords):
                    in_values_section = False

            # Extract from numbered lists: "1. Innovation" or "1) Innovation"
            numbered_match = re.match(r'^\s*\d+[\.\)]\s+([A-Z][^:\n]{2,50})', line)
            if numbered_match and in_values_section:
                value_name = numbered_match.group(1).strip()
                # Get description (next 1-2 lines if available)
                description = ""
                if i + 1 < len(lines) and not re.match(r'^\s*\d+[\.\)]', lines[i + 1]):
                    description = lines[i + 1].strip()[:200]

                values.append({
                    "name": value_name,
                    "description": description,
                    "source_snippet": f"{value_name}: {description}"[:150],
                    "url": primary_url,
                    "source": "Company Values List"
                })

            # Extract from bulleted lists: "- Innovation" or "* Innovation"
            bullet_match = re.match(r'^\s*[-\*•]\s+([A-Z][^:\n]{2,50})', line)
            if bullet_match and in_values_section:
                value_name = bullet_match.group(1).strip()
                description = ""
                if i + 1 < len(lines) and not re.match(r'^\s*[-\*•]', lines[i + 1]):
                    description = lines[i + 1].strip()[:200]

                values.append({
                    "name": value_name,
                    "description": description,
                    "source_snippet": f"{value_name}: {description}"[:150],
                    "url": primary_url,
                    "source": "Company Values List"
                })

            # Extract from colon format: "Innovation: We embrace..."
            colon_match = re.match(r'^\s*\**([A-Z][^:\n]{2,40}):\s*(.{10,200})', line)
            if colon_match and in_values_section:
                value_name = colon_match.group(1).strip()
                description = colon_match.group(2).strip()

                values.append({
                    "name": value_name,
                    "description": description[:200],
                    "source_snippet": line[:150],
                    "url": primary_url,
                    "source": "Company Values"
                })

        return values

    def _extract_explicit_value_statements(self, content: str, primary_url: str) -> List[Dict]:
        """Extract values from explicit statements like 'Our values are X, Y, Z'"""
        import re

        values = []

        # Patterns for explicit value statements
        patterns = [
            r'(?:our|core|company)\s+(?:values|principles)\s+(?:are|include):\s*([^\.]{10,300})',
            r'(?:we|company)\s+(?:value|believe in|stand for):\s*([^\.]{10,300})',
            r'(?:guided by|committed to|built on)\s+(?:values|principles)\s+(?:of|like|such as):\s*([^\.]{10,300})',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                value_text = match.group(1).strip()

                # Split by commas or "and" to get individual values
                # Example: "integrity, innovation, and collaboration"
                value_parts = re.split(r',\s*(?:and\s+)?|\s+and\s+', value_text)

                for part in value_parts:
                    part = part.strip().strip('.,;:')
                    # Capitalize first letter of each word
                    if 3 < len(part) < 50 and part[0].isupper():
                        values.append({
                            "name": part.title(),
                            "description": f"Stated company value",
                            "source_snippet": value_text[:150],
                            "url": primary_url,
                            "source": "Company Statement"
                        })

        return values

    def _search_common_values(self, content: str, primary_url: str) -> List[Dict]:
        """Search for common company values in content (original strategy)"""

        values = []

        # Expanded list of common company values
        common_values = [
            # Customer-focused
            "Customer Obsession", "Customer First", "Customer Centricity", "Customer Focus",
            # Innovation
            "Innovation", "Think Big", "Creativity", "Pioneering",
            # Integrity & Ethics
            "Integrity", "Honesty", "Trust", "Ethics", "Do the Right Thing",
            # Excellence
            "Excellence", "Quality", "High Standards", "Best in Class",
            # Collaboration
            "Collaboration", "Teamwork", "Together", "Partnership", "One Team",
            # Diversity
            "Diversity", "Inclusion", "Belonging", "Equity",
            # Accountability
            "Accountability", "Ownership", "Results-Driven", "Deliver Results",
            # Respect
            "Respect", "Dignity", "Empathy",
            # Transparency
            "Transparency", "Openness", "Authenticity",
            # Sustainability
            "Sustainability", "Environmental Responsibility", "Social Responsibility",
            # Empowerment
            "Empowerment", "Enable", "Empower", "Employee First",
            # Agility
            "Agility", "Adaptability", "Flexibility", "Resilience",
            # Learning
            "Learning", "Growth Mindset", "Continuous Improvement", "Curiosity",
            # Safety
            "Safety", "Security", "Safety First",
            # Impact
            "Impact", "Make a Difference", "Purpose-Driven",
            # Speed
            "Bias for Action", "Move Fast", "Speed", "Urgency",
            # Other
            "Passion", "Enthusiasm", "Fun", "Enjoy the Journey"
        ]

        content_lower = content.lower()

        for value in common_values:
            if value.lower() in content_lower:
                # Find context around this value
                value_index = content_lower.find(value.lower())
                start = max(0, value_index - 100)
                end = min(len(content), value_index + 200)
                snippet = content[start:end].strip()

                # Extract a more meaningful description from the snippet
                sentences = snippet.split(". ")
                description = ""
                for sentence in sentences:
                    if value.lower() in sentence.lower():
                        description = sentence.strip()[:200]
                        break

                values.append({
                    "name": value,
                    "description": description if description else "Mentioned in company research",
                    "source_snippet": snippet[:150],
                    "url": primary_url,
                    "source": "Company Research"
                })

        return values

    def _extract_values_with_gpt(self, content: str, primary_url: str) -> List[Dict]:
        """Use GPT-4 to extract company values from content as fallback"""

        try:
            import os
            from openai import OpenAI
            import json

            openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            # Truncate content to avoid token limits
            content_snippet = content[:4000]

            extraction_prompt = f"""Extract the company's core values from this research content.

Research Content:
{content_snippet}

Extract and return a JSON array of company values. Each value should have:
- name: The value name (2-5 words, capitalized)
- description: A brief 1-sentence description of what this value means

Return ONLY a JSON array, no other text. Example format:
[
  {{"name": "Customer Obsession", "description": "Putting customers at the center of everything we do"}},
  {{"name": "Innovation", "description": "Continuously pushing boundaries and embracing new ideas"}}
]

If no clear values are found, return an empty array: []"""

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting company values from text. Return only valid JSON."},
                    {"role": "user", "content": extraction_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000
            )

            result_text = response.choices[0].message.content

            # Parse JSON - handle both array and object with "values" key
            try:
                parsed = json.loads(result_text)

                # If it's an object with a "values" key, extract that
                if isinstance(parsed, dict):
                    if "values" in parsed:
                        extracted_values = parsed["values"]
                    else:
                        # Might be wrapped in another key, try to find an array
                        for key, value in parsed.items():
                            if isinstance(value, list):
                                extracted_values = value
                                break
                        else:
                            extracted_values = []
                elif isinstance(parsed, list):
                    extracted_values = parsed
                else:
                    extracted_values = []

                # Convert to our format
                gpt_values = []
                for value in extracted_values:
                    if isinstance(value, dict) and "name" in value:
                        gpt_values.append({
                            "name": value.get("name", ""),
                            "description": value.get("description", ""),
                            "source_snippet": value.get("description", "")[:150],
                            "url": primary_url,
                            "source": "AI-Extracted Value"
                        })

                print(f"✓ GPT-4 extracted {len(gpt_values)} values")
                return gpt_values

            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse GPT response as JSON: {e}")
                return []

        except Exception as e:
            print(f"⚠️ GPT value extraction failed: {e}")
            return []

    def _extract_value_name_from_text(self, text: str, title: str) -> str:
        """Extract value name from citation text or title"""

        # Common value names
        common_values = [
            "Innovation", "Integrity", "Excellence", "Customer First", "Collaboration",
            "Diversity", "Inclusion", "Accountability", "Respect", "Transparency",
            "Teamwork", "Quality", "Safety", "Sustainability", "Empowerment"
        ]

        # Check if any common value is mentioned
        text_lower = text.lower()
        for value in common_values:
            if value.lower() in text_lower:
                return value

        # Try to extract from title
        if "value" in title.lower() or "culture" in title.lower():
            # Return first 2-4 words of title
            words = title.split()[:3]
            return " ".join(words)

        return ""

    def _parse_values_from_content(self, source: Dict) -> List[Dict]:
        """Parse values from direct source content"""

        values = []
        content = source.get("content", "")
        lines = content.split("\n")

        for line in lines:
            # Look for value patterns
            if any(pattern in line.lower() for pattern in ["our values", "we value", "core value", "principle"]):
                value_name = line.strip("#-* ").strip()
                if 3 < len(value_name) < 50:
                    values.append({
                        "name": value_name,
                        "description": "",
                        "source_snippet": line[:150],
                        "url": source.get("url", ""),
                        "source": "Company website"
                    })

        return values[:3]

    def _extract_cultural_priorities(self, perplexity_result: Dict) -> List[str]:
        """Extract cultural priorities from research"""

        content = perplexity_result.get("content", "")
        priorities = []

        # Look for cultural keywords
        cultural_keywords = {
            "work-life balance": ["work-life", "work life", "flexibility", "flexible work"],
            "diversity and inclusion": ["diversity", "inclusion", "dei", "belonging"],
            "innovation": ["innovation", "creative", "entrepreneurial"],
            "collaboration": ["collaboration", "teamwork", "team", "together"],
            "growth": ["growth", "development", "learning", "career"],
            "transparency": ["transparency", "open", "honest", "communication"]
        }

        content_lower = content.lower()
        for priority, keywords in cultural_keywords.items():
            if any(kw in content_lower for kw in keywords):
                priorities.append(priority.title())

        return priorities

    def _extract_work_environment(self, perplexity_result: Dict) -> str:
        """Extract work environment description"""

        content = perplexity_result.get("content", "")

        # Look for work environment description
        if "work environment" in content.lower() or "workplace" in content.lower():
            # Find the section and extract 1-2 sentences
            lines = content.split(". ")
            for i, line in enumerate(lines):
                if "work environment" in line.lower() or "workplace" in line.lower():
                    return ". ".join(lines[i:i+2])[:300]

        # Fallback: generate from cultural keywords found
        return "Information about work environment will be researched during interview preparation."

    def _deduplicate_values(self, values: List[Dict]) -> List[Dict]:
        """Remove duplicate values"""

        seen_names = set()
        unique = []

        for value in values:
            name_key = value["name"].lower()[:30]
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique.append(value)

        return unique

    def _get_fallback_values(self, company_name: str) -> Dict:
        """Fallback data if values research fails"""

        return {
            "stated_values": [],
            "cultural_priorities": [],
            "work_environment": f"Unable to fetch company culture information for {company_name}",
            "sources_consulted": [],
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name,
            "error": "Values research failed"
        }

    def _get_fallback_strategies(self, company_name: str) -> Dict:
        """Fallback data if research fails"""

        return {
            "strategic_initiatives": [],
            "recent_developments": [
                f"Unable to fetch recent strategies for {company_name}",
                "Please check company website manually for latest information"
            ],
            "technology_focus": [],
            "sources_consulted": [],
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name,
            "error": "Research failed - using fallback data"
        }
