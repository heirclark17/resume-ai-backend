"""
Career Path Research Service
Uses Perplexity for web-grounded research on certifications, events, and education options
"""
from typing import List, Dict, Any
from app.services.perplexity_client import PerplexityClient
from app.schemas.career_plan import Certification, EducationOption, Event
import json
import re


class CareerPathResearchService:
    """Performs web-grounded research for career path planning"""

    def __init__(self):
        self.perplexity = PerplexityClient()

    async def research_certifications(
        self,
        target_roles: List[str],
        current_experience: float,
        budget: str,
        current_role: str = "",
        current_industry: str = "",
        tools: List[str] = None,
        existing_certs: List[str] = None,
        already_started: bool = False,
        steps_taken: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Research real certifications with official links and costs

        IMPORTANT: Returns ONLY web-grounded data with verified URLs
        """

        roles_str = ", ".join(target_roles[:3])  # Limit to top 3 for focused results
        tools_str = ", ".join((tools or [])[:10]) if tools else "not specified"
        existing_certs_str = ", ".join((existing_certs or [])[:10]) if existing_certs else "none"

        # Build context-anchored query
        context_parts = []
        if current_role and current_industry:
            context_parts.append(f"The user is transitioning FROM {current_role} in {current_industry}.")
        if tools:
            context_parts.append(f"They currently use: {tools_str}.")
        if existing_certs:
            context_parts.append(f"They already hold: {existing_certs_str}. Do NOT recommend these again.")
        if already_started and steps_taken:
            context_parts.append(f"They've already started and completed: {steps_taken}. Recommend NEXT steps only.")

        context_block = " ".join(context_parts)

        query = f"""List ALL professional certifications for transitioning from {current_role or 'current role'} in {current_industry or 'current industry'} to these roles: {roles_str}.

{context_block}

Organize by level:
FOUNDATION/ENTRY LEVEL (start here):
INTERMEDIATE LEVEL (after foundation):
ADVANCED LEVEL (career accelerators):

For EACH certification, provide:
1. EXACT official certification name (e.g., "CompTIA Security+", "AWS Solutions Architect Associate")
2. Certifying body (e.g., CompTIA, AWS, ISC2, Microsoft)
3. Level: foundation, intermediate, or advanced
4. Prerequisites (what you need before attempting)
5. Est. study time in weeks for someone with {current_experience} years experience
6. Current exam cost in USD (exact, not range)
7. OFFICIAL certification page URL (from the certifying body's website)
8. What career doors it opens (specific roles and salary impact)
9. Alternative certifications that serve similar purpose
10. Recommended study order: which cert should come BEFORE and AFTER this one

Focus on certifications that are:
- Widely recognized in the industry
- Actually required or strongly preferred in job postings for {roles_str}
- Worth the investment for CAREER CHANGERS
- Have clear ROI and salary uplift data

Include budget-friendly options if budget is '{budget}'.
Include at least 4-6 certifications covering the full beginner-to-expert journey.
Include specific URLs only from official certification bodies."""

        try:
            result = await self.perplexity.research_with_citations(query)
            content = result.get("content", "")
            citations = result.get("citations", [])

            # Extract certification data from content
            certs = self._parse_certifications(content, citations)

            print(f"✓ Found {len(certs)} certifications from web research")
            return certs

        except Exception as e:
            print(f"✗ Error researching certifications: {e}")
            return []

    async def research_education_options(
        self,
        target_roles: List[str],
        current_education: str,
        location: str,
        budget: str,
        format_preference: str,
        current_role: str = "",
        current_industry: str = "",
        preferred_platforms: List[str] = None,
        existing_certs: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Research degrees, bootcamps, and online courses

        Returns web-grounded education options with real URLs
        """

        roles_str = ", ".join(target_roles[:3])

        # Build context
        context_parts = []
        if current_role and current_industry:
            context_parts.append(f"User is transitioning FROM {current_role} in {current_industry}.")
        if preferred_platforms:
            context_parts.append(f"Preferred learning platforms: {', '.join(preferred_platforms[:5])}.")
        if existing_certs:
            context_parts.append(f"Already holds: {', '.join(existing_certs[:5])}.")

        context_block = " ".join(context_parts)

        query = f"""Find specific education programs for career changers moving to: {roles_str}.

{context_block}

Current education: {current_education}
Location: {location}
Budget: {budget}
Format preference: {format_preference}

Find 4-5 options across these price points:
FREE OPTIONS: MOOCs, YouTube channels, free bootcamp prep
MID-RANGE ($100-$2,000): Coursera specializations, Udemy courses, edX certificates
PREMIUM ($5,000+): Bootcamps, degree programs, immersive training

For EACH option, provide:
1. EXACT program name and institution (e.g., "Google Cybersecurity Certificate on Coursera")
2. Type: degree/bootcamp/self-study/online-course
3. Duration (exact weeks or months)
4. Total cost (exact price, not range)
5. Format: online/in-person/hybrid
6. OFFICIAL enrollment/program URL (direct link to the program page)
7. Pros (3-5 specific benefits)
8. Cons (3-5 honest drawbacks)
9. Who it's best for (career changers, experienced pros, complete beginners)
10. Job placement rate or employment outcomes if available
11. Time commitment per week
12. Financing options (payment plans, scholarships, ISAs)

Include ONLY programs with:
- Verified enrollment links (Coursera, Udemy, edX, university websites)
- Proven outcomes or strong reviews
- Current availability (not discontinued programs)
Provide OFFICIAL URLs only (not affiliate links or blog posts)."""

        try:
            result = await self.perplexity.research_with_citations(query)
            content = result.get("content", "")
            citations = result.get("citations", [])

            options = self._parse_education_options(content, citations)

            print(f"✓ Found {len(options)} education options from web research")
            return options

        except Exception as e:
            print(f"✗ Error researching education: {e}")
            return []

    async def research_events(
        self,
        target_roles: List[str],
        location: str,
        beginner_friendly: bool = True,
        current_role: str = "",
        target_companies: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Research real networking events, conferences, and meetups

        CRITICAL: Returns ONLY events with verified registration links
        """

        roles_str = ", ".join(target_roles[:3])
        location_query = f"near {location}" if location else "virtual/online"

        # Build context
        context_parts = []
        if current_role:
            context_parts.append(f"User is transitioning from {current_role}.")
        if target_companies:
            context_parts.append(f"They're targeting companies like: {', '.join(target_companies[:3])}. Include events where these companies recruit or present.")

        context_block = " ".join(context_parts)

        query = f"""Find upcoming networking and learning events for someone interested in: {roles_str}.

{context_block}

Location: {location_query}
Beginner-friendly: {beginner_friendly}

For EACH event, provide:
1. Full event name
2. Event type: conference/meetup/virtual/career-fair/workshop
3. Date or season (e.g., "March 2026", "Q2 2026", "Annual - check site")
4. Location (city or "Virtual")
5. Typical price range or "Free"
6. Whether it's beginner-friendly (yes/no)
7. Why someone should attend (specific value)
8. OFFICIAL registration/info URL (event website, not news articles)

Include a MIX of:
- Major industry conferences (even if expensive - good to know about)
- Local meetups and user groups (usually free)
- Virtual events and webinars (accessible anywhere)
- Career fairs or hiring events
- Workshops and hands-on training

Focus on RECURRING or UPCOMING events (not past events).
Include OFFICIAL event URLs only (Eventbrite, Meetup.com, conference sites).
Prioritize events that help with:
- Learning new skills
- Meeting hiring managers or recruiters
- Building professional network
- Staying current with industry trends"""

        try:
            result = await self.perplexity.research_with_citations(query)
            content = result.get("content", "")
            citations = result.get("citations", [])

            events = self._parse_events(content, citations)

            print(f"✓ Found {len(events)} events from web research")
            return events

        except Exception as e:
            print(f"✗ Error researching events: {e}")
            return []

    def _extract_raw_research(self, content: str, citations: List[Dict]) -> Dict[str, Any]:
        """
        Return raw Perplexity content + citation URLs for GPT synthesis.
        Instead of parsing into fake objects, we pass the full research text
        to the synthesis prompt so GPT can extract real names, costs, and URLs.
        """
        citation_urls = [c.get("url", "") for c in citations if c.get("url")]
        return {
            "raw_content": content,
            "citation_urls": citation_urls
        }

    def _parse_certifications(self, content: str, citations: List[Dict]) -> List[Dict[str, Any]]:
        """
        Return raw certification research for GPT synthesis.
        The AI model is far better at extracting structured data from prose
        than regex-based parsing which was producing hardcoded placeholders.
        """
        raw = self._extract_raw_research(content, citations)
        # Return a single-item list with raw content for backward compat
        # The synthesis prompt will use raw_certification_content instead
        return [{
            "raw_content": raw["raw_content"],
            "citation_urls": raw["citation_urls"],
            "source_citations": raw["citation_urls"][:5]
        }]

    def _parse_education_options(self, content: str, citations: List[Dict]) -> List[Dict[str, Any]]:
        """Return raw education research for GPT synthesis."""
        raw = self._extract_raw_research(content, citations)
        return [{
            "raw_content": raw["raw_content"],
            "citation_urls": raw["citation_urls"],
            "source_citations": raw["citation_urls"][:5]
        }]

    def _parse_events(self, content: str, citations: List[Dict]) -> List[Dict[str, Any]]:
        """Return raw events research for GPT synthesis."""
        raw = self._extract_raw_research(content, citations)
        return [{
            "raw_content": raw["raw_content"],
            "citation_urls": raw["citation_urls"],
            "source_citations": raw["citation_urls"][:5]
        }]

    async def research_all(
        self,
        target_roles: List[str],
        location: str,
        current_experience: float,
        current_education: str,
        budget: str,
        format_preference: str,
        intake_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run all research in parallel and return combined results
        """

        print(f"🔍 Starting comprehensive research for roles: {', '.join(target_roles)}")

        # Extract intake context for enhanced queries
        ctx = intake_context or {}
        current_role = ctx.get("current_role_title", "")
        current_industry = ctx.get("current_industry", "")
        tools = ctx.get("tools", [])
        existing_certs = ctx.get("existing_certifications", [])
        already_started = ctx.get("already_started", False)
        steps_taken = ctx.get("steps_already_taken", "")
        preferred_platforms = ctx.get("preferred_platforms", [])
        target_companies = ctx.get("specific_companies", [])

        # Run all research concurrently
        import asyncio

        certs_task = self.research_certifications(
            target_roles, current_experience, budget,
            current_role=current_role, current_industry=current_industry,
            tools=tools, existing_certs=existing_certs,
            already_started=already_started, steps_taken=steps_taken
        )
        edu_task = self.research_education_options(
            target_roles, current_education, location, budget, format_preference,
            current_role=current_role, current_industry=current_industry,
            preferred_platforms=preferred_platforms, existing_certs=existing_certs
        )
        events_task = self.research_events(
            target_roles, location, beginner_friendly=True,
            current_role=current_role, target_companies=target_companies
        )

        certs, edu_options, events = await asyncio.gather(certs_task, edu_task, events_task)

        # Collect all source citations
        all_sources = set()
        for cert in certs:
            all_sources.update(cert.get("source_citations", []))
            all_sources.update(cert.get("citation_urls", []))
        for option in edu_options:
            all_sources.update(option.get("source_citations", []))
            all_sources.update(option.get("citation_urls", []))
        for event in events:
            all_sources.update(event.get("source_citations", []))
            all_sources.update(event.get("citation_urls", []))

        # Extract raw content for GPT synthesis prompt injection
        raw_cert_content = certs[0].get("raw_content", "") if certs else ""
        raw_edu_content = edu_options[0].get("raw_content", "") if edu_options else ""
        raw_events_content = events[0].get("raw_content", "") if events else ""

        cert_citation_urls = certs[0].get("citation_urls", []) if certs else []
        edu_citation_urls = edu_options[0].get("citation_urls", []) if edu_options else []
        events_citation_urls = events[0].get("citation_urls", []) if events else []

        print(f"✓ Research complete: cert content={len(raw_cert_content)} chars, edu content={len(raw_edu_content)} chars, events content={len(raw_events_content)} chars")
        print(f"✓ Total sources: {len(all_sources)}")

        return {
            "certifications": certs,
            "education_options": edu_options,
            "events": events,
            "research_sources": list(all_sources),
            # Raw content for direct injection into synthesis prompt
            "raw_certification_content": raw_cert_content,
            "raw_education_content": raw_edu_content,
            "raw_events_content": raw_events_content,
            "cert_citation_urls": cert_citation_urls,
            "edu_citation_urls": edu_citation_urls,
            "events_citation_urls": events_citation_urls,
        }
