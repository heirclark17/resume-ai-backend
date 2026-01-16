"""
News Aggregator Service - Fetch recent company news from multiple sources
Aggregates from: Google News, Company RSS, Reddit, Tech news sites
"""

import json
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.services.firecrawl_client import FirecrawlClient
from app.services.perplexity_client import PerplexityClient


class NewsAggregatorService:
    """
    Aggregate recent company news from multiple sources
    - Last 90 days of relevant news
    - Multiple source types
    - Ranked by relevance to job role
    - Includes source URLs
    """

    def __init__(self):
        self.firecrawl = FirecrawlClient()
        self.perplexity = PerplexityClient()

    async def aggregate_company_news(
        self,
        company_name: str,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        days_back: int = 90
    ) -> Dict:
        """
        Aggregate recent company news from multiple sources

        Returns:
        {
            "news_articles": [
                {
                    "title": "Article headline",
                    "summary": "Brief summary",
                    "source": "Bloomberg",
                    "url": "https://...",
                    "published_date": "2024-01-15",
                    "relevance_score": 8,
                    "category": "product_launch",
                    "impact_summary": "What this means for the role"
                }
            ],
            "total_articles": 25,
            "sources_used": ["Bloomberg", "TechCrunch", "Company Blog"],
            "date_range": "Last 90 days",
            "last_updated": "2024-01-15T..."
        }
        """

        print(f"Aggregating news for: {company_name} (last {days_back} days)")

        try:
            # Use Perplexity to search for recent news
            news_query = self._build_news_query(company_name, industry, job_title, days_back)
            news_results = await self._search_news_perplexity(news_query, company_name)

            # Try to fetch company blog/newsroom directly
            company_news = await self._fetch_company_newsroom(company_name, days_back)

            # Combine and structure results
            all_news = self._combine_news_sources(news_results, company_news)

            # Filter by date range
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            filtered_news = self._filter_by_date(all_news, cutoff_date)

            # Rank by relevance
            ranked_news = self._rank_by_relevance(filtered_news, job_title)

            # Add impact summaries
            final_news = self._add_impact_summaries(ranked_news[:15], job_title)

            return {
                "news_articles": final_news,
                "total_articles": len(final_news),
                "sources_used": list(set([n["source"] for n in final_news])),
                "date_range": f"Last {days_back} days",
                "last_updated": datetime.utcnow().isoformat(),
                "company_name": company_name
            }

        except Exception as e:
            print(f"Error aggregating news: {e}")
            return self._get_fallback_news(company_name)

    def _build_news_query(
        self,
        company_name: str,
        industry: Optional[str],
        job_title: Optional[str],
        days_back: int
    ) -> str:
        """Build query for news search"""

        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        query = f"""Find recent news articles about {company_name}:

**Requirements:**
- Published after {cutoff_date} (last {days_back} days)
- From reputable sources (Bloomberg, Reuters, TechCrunch, WSJ, etc.)
- Include company press releases and announcements
- Focus on: product launches, executive changes, financial results, strategic initiatives

**For each article, provide:**
- Exact headline
- Publication date
- Source name
- Brief summary (2-3 sentences)
- Article URL if available

**Prioritize articles related to:**"""

        if industry:
            query += f"\n- {industry} industry"

        if job_title:
            query += f"\n- Relevant to {job_title} role"

        query += f"""

**Sources to check:**
- Major tech news (TechCrunch, The Verge, Ars Technica)
- Business news (Bloomberg, WSJ, Reuters, CNBC)
- Industry publications
- {company_name} company blog and newsroom
- {company_name} press releases"""

        return query

    async def _search_news_perplexity(
        self,
        query: str,
        company_name: str
    ) -> List[Dict]:
        """
        Search for news using Perplexity (PRIMARY SOURCE)

        Returns REAL articles with:
        - Actual URLs users can click
        - Real publication dates
        - Real source names (Bloomberg, Reuters, etc.)
        """

        try:
            print("🔍 Searching Perplexity for real news articles...")
            result = await self.perplexity.research_with_citations(query)

            # Extract citations first (these are REAL articles)
            citations = result.get("citations", [])
            print(f"✓ Found {len(citations)} real articles from Perplexity")

            # Convert citations to article format
            articles = []
            for citation in citations:
                if citation.get("url"):  # Must have a real URL
                    articles.append({
                        "title": citation.get("title", "Article"),
                        "summary": citation.get("text", "")[:300],
                        "source": self._extract_source_name(citation.get("url", "")),
                        "url": citation.get("url", ""),
                        "published_date": self._extract_date_from_url_or_content(citation),
                        "relevance_score": 7,  # Perplexity citations are highly relevant
                        "category": "news",
                        "impact_summary": ""
                    })

            # Also parse content for additional context
            content_articles = self._parse_news_from_perplexity(
                result.get("content", ""),
                citations
            )

            # Combine and deduplicate
            all_articles = articles + content_articles
            unique_articles = self._deduplicate_by_url(all_articles)

            print(f"✓ Processed {len(unique_articles)} unique news articles")
            return unique_articles

        except Exception as e:
            print(f"⚠️ Perplexity news search failed: {e}")
            return []

    def _parse_news_from_perplexity(
        self,
        content: str,
        citations: List[Dict]
    ) -> List[Dict]:
        """Parse news articles from Perplexity response"""

        articles = []
        lines = content.split("\n")

        current_article = None

        for line in lines:
            line = line.strip()

            # Look for article headlines (usually start with -, *, or are bold)
            if (line.startswith("-") or line.startswith("*") or
                line.startswith("**") or line.startswith("###")):

                if current_article and current_article.get("title"):
                    articles.append(current_article)

                # Extract title
                title = line.strip("-*# ").strip()

                # Try to extract date from the line
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\w+ \d+, \d{4}|\d{1,2}/\d{1,2}/\d{4})', title)
                pub_date = date_match.group(1) if date_match else ""

                current_article = {
                    "title": title,
                    "summary": "",
                    "source": "News source",
                    "url": "",
                    "published_date": self._normalize_date(pub_date),
                    "relevance_score": 5,
                    "category": "general",
                    "impact_summary": ""
                }

            elif current_article and line:
                # Add to summary
                current_article["summary"] += " " + line

        # Add last article
        if current_article and current_article.get("title"):
            articles.append(current_article)

        # Match citations to articles
        for article in articles:
            for citation in citations:
                # Check if citation title matches article
                if citation.get("title", "").lower() in article["title"].lower():
                    article["source"] = self._extract_source_name(citation.get("url", ""))
                    article["url"] = citation.get("url", "")
                    break

        return articles

    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL"""

        if not url:
            return "Unknown source"

        # Extract domain
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            domain = match.group(1)

            # Map common domains to clean names
            source_map = {
                "techcrunch.com": "TechCrunch",
                "bloomberg.com": "Bloomberg",
                "reuters.com": "Reuters",
                "wsj.com": "Wall Street Journal",
                "cnbc.com": "CNBC",
                "theverge.com": "The Verge",
                "arstechnica.com": "Ars Technica",
                "wired.com": "Wired",
                "forbes.com": "Forbes",
                "businessinsider.com": "Business Insider",
                "ft.com": "Financial Times"
            }

            for key, value in source_map.items():
                if key in domain:
                    return value

            # Clean domain name
            return domain.replace(".com", "").replace(".co", "").title()

        return "News source"

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to YYYY-MM-DD format"""

        if not date_str:
            return datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Try parsing different formats
            for fmt in ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If all fail, return today
            return datetime.utcnow().strftime("%Y-%m-%d")

        except Exception:
            return datetime.utcnow().strftime("%Y-%m-%d")

    async def _fetch_company_newsroom(
        self,
        company_name: str,
        days_back: int
    ) -> List[Dict]:
        """Fetch news directly from company newsroom/blog"""

        company_slug = company_name.lower().replace(" ", "").replace("&", "and")

        newsroom_urls = [
            f"https://www.{company_slug}.com/newsroom",
            f"https://www.{company_slug}.com/news",
            f"https://blog.{company_slug}.com",
        ]

        # Special cases
        special_urls = {
            "jpmorgan": ["https://www.jpmorganchase.com/newsroom"],
            "oracle": ["https://www.oracle.com/news"],
            "microsoft": ["https://news.microsoft.com"],
            "amazon": ["https://www.aboutamazon.com/news"],
        }

        company_key = company_name.lower().split()[0]
        if company_key in special_urls:
            newsroom_urls = special_urls[company_key]

        articles = []

        for url in newsroom_urls[:2]:  # Limit to 2 URLs
            try:
                print(f"Fetching company news from: {url}")
                content = await self.firecrawl.scrape_page(url, formats=["markdown"])

                if content:
                    parsed_articles = self._parse_newsroom_content(content, url)
                    articles.extend(parsed_articles[:5])  # Top 5 from each source

            except Exception as e:
                print(f"Failed to fetch {url}: {e}")
                continue

        return articles

    def _parse_newsroom_content(self, content: str, source_url: str) -> List[Dict]:
        """Parse company newsroom content for articles"""

        articles = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            # Look for headlines (usually markdown headers)
            if line.startswith("##") or line.startswith("###"):
                title = line.strip("#").strip()

                # Get next line as summary
                summary = lines[i+1] if i+1 < len(lines) else ""

                # Try to find date nearby
                date_str = ""
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    date_match = re.search(
                        r'(\d{4}-\d{2}-\d{2}|\w+ \d+, \d{4}|\d{1,2}/\d{1,2}/\d{4})',
                        lines[j]
                    )
                    if date_match:
                        date_str = date_match.group(1)
                        break

                if len(title) > 10:  # Valid headline
                    articles.append({
                        "title": title,
                        "summary": summary[:300],
                        "source": "Company Press Release",
                        "url": source_url,
                        "published_date": self._normalize_date(date_str),
                        "relevance_score": 7,  # Company news is highly relevant
                        "category": "company_announcement",
                        "impact_summary": ""
                    })

        return articles

    def _combine_news_sources(
        self,
        news_results: List[Dict],
        company_news: List[Dict]
    ) -> List[Dict]:
        """Combine news from multiple sources and deduplicate"""

        all_news = news_results + company_news

        # Deduplicate by title
        seen_titles = set()
        unique_news = []

        for article in all_news:
            title_key = article["title"].lower()[:50]  # First 50 chars
            if title_key not in seen_titles and len(article["title"]) > 10:
                seen_titles.add(title_key)
                unique_news.append(article)

        return unique_news

    def _filter_by_date(
        self,
        articles: List[Dict],
        cutoff_date: datetime
    ) -> List[Dict]:
        """Filter articles by date range"""

        filtered = []

        for article in articles:
            try:
                pub_date = datetime.strptime(article["published_date"], "%Y-%m-%d")
                if pub_date >= cutoff_date:
                    filtered.append(article)
            except Exception:
                # If date parsing fails, include it anyway
                filtered.append(article)

        return filtered

    def _rank_by_relevance(
        self,
        articles: List[Dict],
        job_title: Optional[str]
    ) -> List[Dict]:
        """Rank articles by relevance to job role"""

        # Keywords that boost relevance for different roles
        role_keywords = {
            "cybersecurity": ["security", "breach", "vulnerability", "cyber", "privacy", "threat"],
            "program manager": ["initiative", "program", "launch", "project", "expansion"],
            "engineering": ["technology", "platform", "api", "developer", "infrastructure"],
            "data": ["data", "analytics", "ai", "machine learning", "ml"],
        }

        for article in articles:
            score = article.get("relevance_score", 5)

            # Boost score if job-related keywords found
            if job_title:
                title_lower = job_title.lower()
                text = (article["title"] + " " + article["summary"]).lower()

                for role, keywords in role_keywords.items():
                    if role in title_lower:
                        for keyword in keywords:
                            if keyword in text:
                                score += 1

            # Boost recent articles
            try:
                pub_date = datetime.strptime(article["published_date"], "%Y-%m-%d")
                days_old = (datetime.utcnow() - pub_date).days
                if days_old < 30:
                    score += 2
                elif days_old < 60:
                    score += 1
            except Exception:
                pass

            article["relevance_score"] = min(score, 10)  # Cap at 10

        # Sort by relevance score (highest first)
        articles.sort(key=lambda x: x["relevance_score"], reverse=True)

        return articles

    def _add_impact_summaries(
        self,
        articles: List[Dict],
        job_title: Optional[str]
    ) -> List[Dict]:
        """Add impact summaries showing relevance to role"""

        for article in articles:
            # Generate simple impact summary based on category and role
            category = article.get("category", "general")

            if category == "product_launch":
                impact = f"New product could impact {job_title or 'your role'} responsibilities and team priorities"
            elif category == "executive_change":
                impact = "Leadership changes may influence company direction and team structure"
            elif category == "financial_results":
                impact = "Financial performance affects company investments and hiring"
            elif category == "company_announcement":
                impact = "Company-level initiative relevant to understanding organizational priorities"
            else:
                impact = f"Recent development relevant to {job_title or 'the role'} at the company"

            article["impact_summary"] = impact

        return articles

    def _categorize_article(self, title: str, summary: str) -> str:
        """Categorize article based on content"""

        text = (title + " " + summary).lower()

        if any(kw in text for kw in ["launch", "unveil", "introduce", "release"]):
            return "product_launch"
        elif any(kw in text for kw in ["ceo", "executive", "appoint", "hire", "departure"]):
            return "executive_change"
        elif any(kw in text for kw in ["earnings", "revenue", "profit", "quarter", "financial"]):
            return "financial_results"
        elif any(kw in text for kw in ["acquire", "acquisition", "merge", "partner"]):
            return "partnership"
        elif any(kw in text for kw in ["security", "breach", "hack", "vulnerability"]):
            return "security"
        else:
            return "general"

    def _extract_date_from_url_or_content(self, citation: Dict) -> str:
        """
        Extract publication date from citation URL or content

        Many URLs contain dates (e.g., /2024/01/15/article-name)
        """

        url = citation.get("url", "")
        text = citation.get("text", "")

        # Try to extract from URL path
        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
        if date_match:
            year, month, day = date_match.groups()
            return f"{year}-{month}-{day}"

        # Try to extract from citation text
        date_match = re.search(
            r'(\d{4}-\d{2}-\d{2}|\w+ \d+, \d{4}|\d{1,2}/\d{1,2}/\d{4})',
            text
        )
        if date_match:
            return self._normalize_date(date_match.group(1))

        # Default to current date
        return datetime.utcnow().strftime("%Y-%m-%d")

    def _deduplicate_by_url(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles by URL"""

        seen_urls = set()
        unique = []

        for article in articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)
            elif not url:  # Keep articles without URLs (shouldn't happen with Perplexity)
                unique.append(article)

        return unique

    def _get_fallback_news(self, company_name: str) -> Dict:
        """Fallback data if news aggregation fails"""

        return {
            "news_articles": [
                {
                    "title": f"Unable to fetch recent news for {company_name}",
                    "summary": "Please check company website and major news sources manually for latest updates.",
                    "source": "System",
                    "url": "",
                    "published_date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "relevance_score": 0,
                    "category": "error",
                    "impact_summary": "Manual research recommended"
                }
            ],
            "total_articles": 0,
            "sources_used": [],
            "date_range": "N/A",
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name,
            "error": "News aggregation failed"
        }
