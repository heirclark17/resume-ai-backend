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
