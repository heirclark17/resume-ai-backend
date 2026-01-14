"""
Interview Questions Scraper Service - Fetch real interview questions
Sources: Glassdoor, Reddit, Blind, company interview experiences
"""

import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.services.perplexity_client import PerplexityClient
from app.services.firecrawl_client import FirecrawlClient


class InterviewQuestionsScraperService:
    """
    Scrape and aggregate real interview questions from multiple sources
    - Reddit (r/cscareerquestions, r/ExperiencedDevs, r/cybersecurity)
    - Glassdoor interview experiences
    - Blind interview discussions
    - Company-specific interview prep sites

    Includes difficulty ratings, frequency, and sources
    """

    def __init__(self):
        self.perplexity = PerplexityClient()
        self.firecrawl = FirecrawlClient()

    async def scrape_interview_questions(
        self,
        company_name: str,
        job_title: Optional[str] = None,
        role_category: Optional[str] = None,
        max_questions: int = 30
    ) -> Dict:
        """
        Scrape real interview questions for a company/role

        Returns:
        {
            "questions": [
                {
                    "question": "Describe a time when...",
                    "type": "behavioral",
                    "difficulty": "medium",
                    "frequency": "high",
                    "source": "Glassdoor",
                    "source_url": "https://...",
                    "date": "2024-01-15",
                    "context": "Asked in final round",
                    "tips": "Focus on leadership and metrics"
                }
            ],
            "total_questions": 25,
            "question_types": {
                "behavioral": 10,
                "technical": 8,
                "situational": 7
            },
            "difficulty_breakdown": {
                "easy": 5,
                "medium": 15,
                "hard": 5
            },
            "sources": ["Glassdoor", "Reddit", "Blind"],
            "last_updated": "2024-01-15T..."
        }
        """

        print(f"Scraping interview questions for: {company_name} - {job_title}")

        try:
            # Build comprehensive search query
            search_query = self._build_search_query(company_name, job_title, role_category)

            # Search via Perplexity for interview experiences
            perplexity_questions = await self._search_via_perplexity(search_query, company_name)

            # Try Reddit-specific search
            reddit_questions = await self._search_reddit(company_name, job_title)

            # Combine and deduplicate
            all_questions = self._combine_questions(perplexity_questions, reddit_questions)

            # Categorize and rank
            categorized_questions = self._categorize_questions(all_questions)
            ranked_questions = self._rank_by_relevance(categorized_questions, job_title)

            # Limit to max_questions
            final_questions = ranked_questions[:max_questions]

            # Generate statistics
            stats = self._generate_statistics(final_questions)

            return {
                "questions": final_questions,
                "total_questions": len(final_questions),
                "question_types": stats["types"],
                "difficulty_breakdown": stats["difficulty"],
                "sources": list(set([q["source"] for q in final_questions])),
                "last_updated": datetime.utcnow().isoformat(),
                "company_name": company_name,
                "job_title": job_title
            }

        except Exception as e:
            print(f"Error scraping interview questions: {e}")
            return self._get_fallback_questions(company_name, job_title)

    def _build_search_query(
        self,
        company_name: str,
        job_title: Optional[str],
        role_category: Optional[str]
    ) -> str:
        """Build comprehensive search query for interview questions"""

        role_term = job_title or role_category or "interview"

        query = f"""Find real interview questions asked at {company_name} for {role_term} positions:

**Sources to check:**
- Glassdoor interview experiences
- Reddit (r/cscareerquestions, r/ExperiencedDevs, r/cybersecurity)
- Blind company discussions
- Interview prep sites (LeetCode, Pramp, InterviewQuery)

**For each question found, provide:**
- Exact question text
- Question type (behavioral, technical, situational, case study)
- Interview round (phone screen, technical round, final round, etc.)
- Difficulty level (easy, medium, hard)
- How often it's asked (frequency: high/medium/low)
- Source and date if available
- Any tips or context from interviewees

**Question types to prioritize:**
- Behavioral (STAR format): leadership, conflict, failure, success stories
- Technical: architecture, security frameworks, risk assessment
- Situational: handling incidents, stakeholder conflicts, resource constraints
- Role-specific: program management, cybersecurity concepts, compliance

**Focus on questions from the last 12-18 months.**
**Include both common and unique/challenging questions.**
"""

        if "program manager" in role_term.lower() or "pm" in role_term.lower():
            query += """
**Program Manager specific questions:**
- Stakeholder management scenarios
- Cross-functional team leadership
- Roadmap and prioritization
- Metrics and OKRs
- Risk and mitigation strategies
"""

        if "security" in role_term.lower() or "cyber" in role_term.lower():
            query += """
**Cybersecurity specific questions:**
- Security framework knowledge (NIST, ISO 27001)
- Incident response scenarios
- Vulnerability management
- Compliance and audit
- Risk assessment methodologies
"""

        return query

    async def _search_via_perplexity(
        self,
        query: str,
        company_name: str
    ) -> List[Dict]:
        """Search for interview questions using Perplexity"""

        try:
            result = await self.perplexity.research_with_citations(query)

            questions = self._parse_questions_from_perplexity(
                result.get("content", ""),
                result.get("citations", [])
            )

            return questions

        except Exception as e:
            print(f"Perplexity search failed: {e}")
            return []

    def _parse_questions_from_perplexity(
        self,
        content: str,
        citations: List[Dict]
    ) -> List[Dict]:
        """Parse interview questions from Perplexity response"""

        questions = []
        lines = content.split("\n")

        current_question = None
        question_buffer = []

        for i, line in enumerate(lines):
            line = line.strip()

            # Look for question markers
            is_question = (
                line.endswith("?") or
                "asked" in line.lower() or
                any(line.startswith(prefix) for prefix in ["- ", "* ", "Q:", "Question:"])
            )

            if is_question and len(line) > 20:
                # Save previous question
                if current_question and question_buffer:
                    current_question["context"] = " ".join(question_buffer[:2])
                    questions.append(current_question)
                    question_buffer = []

                # Clean question text
                question_text = line.strip("-*Q: ").strip()
                if question_text.startswith("Question:"):
                    question_text = question_text[9:].strip()

                # Extract type from surrounding context
                context_lines = lines[max(0, i-2):min(len(lines), i+3)]
                context_text = " ".join(context_lines).lower()

                question_type = self._determine_question_type(question_text, context_text)
                difficulty = self._determine_difficulty(context_text)
                frequency = self._determine_frequency(context_text)

                current_question = {
                    "question": question_text,
                    "type": question_type,
                    "difficulty": difficulty,
                    "frequency": frequency,
                    "source": "Interview Experience",
                    "source_url": "",
                    "date": "",
                    "context": "",
                    "tips": ""
                }

            elif current_question and line and not line.startswith("#"):
                # Add context/tips
                question_buffer.append(line)

        # Add last question
        if current_question and current_question.get("question"):
            if question_buffer:
                current_question["context"] = " ".join(question_buffer[:2])
            questions.append(current_question)

        # Match citations to questions
        for question in questions:
            for citation in citations:
                # Try to match based on proximity or keywords
                if citation.get("url"):
                    source_name = self._extract_source_name(citation.get("url", ""))
                    if source_name and not question["source_url"]:
                        question["source"] = source_name
                        question["source_url"] = citation.get("url", "")
                        break

        return questions

    def _determine_question_type(self, question_text: str, context: str) -> str:
        """Determine question type from text and context"""

        question_lower = question_text.lower()
        context_lower = context.lower()

        # Behavioral indicators
        behavioral_keywords = [
            "tell me about a time",
            "describe a situation",
            "give an example",
            "how did you handle",
            "experience with",
            "challenge you faced"
        ]
        if any(kw in question_lower for kw in behavioral_keywords):
            return "behavioral"

        # Technical indicators
        technical_keywords = [
            "how would you design",
            "explain how",
            "what is the difference",
            "implement",
            "architecture",
            "framework",
            "algorithm",
            "optimize"
        ]
        if any(kw in question_lower for kw in technical_keywords):
            return "technical"

        # Case study indicators
        case_keywords = [
            "case study",
            "scenario:",
            "imagine you are",
            "you are presented with",
            "analyze"
        ]
        if any(kw in context_lower for kw in case_keywords):
            return "case_study"

        # Situational indicators
        situational_keywords = [
            "what would you do",
            "how would you approach",
            "if you were",
            "handle a situation"
        ]
        if any(kw in question_lower for kw in situational_keywords):
            return "situational"

        return "general"

    def _determine_difficulty(self, context: str) -> str:
        """Determine difficulty from context"""

        context_lower = context.lower()

        if any(word in context_lower for word in ["hard", "difficult", "challenging", "tough", "complex"]):
            return "hard"
        elif any(word in context_lower for word in ["easy", "simple", "straightforward", "basic"]):
            return "easy"
        else:
            return "medium"

    def _determine_frequency(self, context: str) -> str:
        """Determine how often question is asked"""

        context_lower = context.lower()

        high_freq = ["always", "every", "common", "frequently", "often", "typical"]
        low_freq = ["rare", "unusual", "unique", "occasionally", "seldom"]

        if any(word in context_lower for word in high_freq):
            return "high"
        elif any(word in context_lower for word in low_freq):
            return "low"
        else:
            return "medium"

    async def _search_reddit(
        self,
        company_name: str,
        job_title: Optional[str]
    ) -> List[Dict]:
        """Search Reddit for interview experiences"""

        # Reddit-specific query
        role_term = job_title or "interview"
        reddit_query = f"""Search Reddit for {company_name} interview questions and experiences:

Check these subreddits:
- r/cscareerquestions
- r/ExperiencedDevs
- r/cybersecurity
- r/ITCareerQuestions

Find posts about:
- "{company_name} interview"
- "{company_name} {role_term}"
- "{company_name} hiring process"

Extract actual questions asked in interviews (not just general discussion).
Include any difficulty ratings or tips mentioned by candidates.
"""

        try:
            result = await self.perplexity.research_with_citations(reddit_query)
            questions = self._parse_questions_from_perplexity(
                result.get("content", ""),
                result.get("citations", [])
            )

            # Mark as Reddit source
            for q in questions:
                if "reddit" in q.get("source_url", "").lower():
                    q["source"] = "Reddit"

            return questions

        except Exception as e:
            print(f"Reddit search failed: {e}")
            return []

    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL"""

        if not url:
            return "Interview Experience"

        url_lower = url.lower()

        if "glassdoor" in url_lower:
            return "Glassdoor"
        elif "reddit.com" in url_lower:
            return "Reddit"
        elif "teamblind.com" in url_lower or "blind.com" in url_lower:
            return "Blind"
        elif "leetcode" in url_lower:
            return "LeetCode"
        elif "interviewing.io" in url_lower:
            return "Interviewing.io"
        else:
            # Extract domain
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                domain = match.group(1)
                return domain.replace(".com", "").title()

        return "Interview Experience"

    def _combine_questions(
        self,
        perplexity_questions: List[Dict],
        reddit_questions: List[Dict]
    ) -> List[Dict]:
        """Combine and deduplicate questions"""

        all_questions = perplexity_questions + reddit_questions

        # Deduplicate by question text (first 50 chars)
        seen_questions = set()
        unique_questions = []

        for q in all_questions:
            question_key = q["question"][:50].lower()
            if question_key not in seen_questions and len(q["question"]) > 15:
                seen_questions.add(question_key)
                unique_questions.append(q)

        return unique_questions

    def _categorize_questions(self, questions: List[Dict]) -> List[Dict]:
        """Further categorize and enrich questions"""

        for question in questions:
            # Ensure all required fields
            if not question.get("type"):
                question["type"] = self._determine_question_type(
                    question["question"],
                    question.get("context", "")
                )

            if not question.get("difficulty"):
                question["difficulty"] = "medium"

            if not question.get("frequency"):
                question["frequency"] = "medium"

            # Add default values
            question.setdefault("source", "Interview Experience")
            question.setdefault("source_url", "")
            question.setdefault("date", "")
            question.setdefault("context", "")
            question.setdefault("tips", "")

        return questions

    def _rank_by_relevance(
        self,
        questions: List[Dict],
        job_title: Optional[str]
    ) -> List[Dict]:
        """Rank questions by relevance"""

        # Score each question
        for question in questions:
            score = 0

            # High frequency = higher priority
            if question["frequency"] == "high":
                score += 3
            elif question["frequency"] == "medium":
                score += 2

            # Behavioral questions are valuable
            if question["type"] == "behavioral":
                score += 2

            # Recent questions
            if question.get("date"):
                try:
                    date_obj = datetime.strptime(question["date"][:10], "%Y-%m-%d")
                    days_old = (datetime.utcnow() - date_obj).days
                    if days_old < 180:  # Last 6 months
                        score += 2
                    elif days_old < 365:  # Last year
                        score += 1
                except Exception:
                    pass

            # Source credibility
            if question["source"] in ["Glassdoor", "Reddit", "Blind"]:
                score += 1

            # Job title relevance
            if job_title:
                job_lower = job_title.lower()
                question_lower = question["question"].lower()
                context_lower = question.get("context", "").lower()

                if "program manager" in job_lower or "pm" in job_lower:
                    pm_keywords = ["stakeholder", "roadmap", "team", "prioritize", "delivery"]
                    if any(kw in question_lower or kw in context_lower for kw in pm_keywords):
                        score += 2

                if "security" in job_lower or "cyber" in job_lower:
                    security_keywords = ["security", "risk", "vulnerability", "compliance", "incident"]
                    if any(kw in question_lower or kw in context_lower for kw in security_keywords):
                        score += 2

            question["relevance_score"] = score

        # Sort by relevance
        questions.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        return questions

    def _generate_statistics(self, questions: List[Dict]) -> Dict:
        """Generate question statistics"""

        types = {}
        difficulty = {}

        for q in questions:
            # Count types
            q_type = q.get("type", "general")
            types[q_type] = types.get(q_type, 0) + 1

            # Count difficulty
            q_diff = q.get("difficulty", "medium")
            difficulty[q_diff] = difficulty.get(q_diff, 0) + 1

        return {
            "types": types,
            "difficulty": difficulty
        }

    def _get_fallback_questions(self, company_name: str, job_title: Optional[str]) -> Dict:
        """Fallback generic questions if scraping fails"""

        generic_behavioral = [
            {
                "question": "Tell me about a time when you had to manage a complex project with multiple stakeholders. How did you ensure alignment and deliver results?",
                "type": "behavioral",
                "difficulty": "medium",
                "frequency": "high",
                "source": "Common Interview Question",
                "source_url": "",
                "date": "",
                "context": "Often asked in program manager interviews",
                "tips": "Use STAR format, emphasize communication and measurable outcomes"
            },
            {
                "question": "Describe a situation where you had to handle a high-pressure deadline with limited resources. What was your approach?",
                "type": "behavioral",
                "difficulty": "medium",
                "frequency": "high",
                "source": "Common Interview Question",
                "source_url": "",
                "date": "",
                "context": "Tests prioritization and resource management",
                "tips": "Focus on decision-making process and impact"
            },
            {
                "question": "Give an example of a time when you had to influence stakeholders without direct authority. How did you gain buy-in?",
                "type": "behavioral",
                "difficulty": "medium",
                "frequency": "high",
                "source": "Common Interview Question",
                "source_url": "",
                "date": "",
                "context": "Common for cross-functional roles",
                "tips": "Highlight communication, data-driven approach, and relationships"
            },
            {
                "question": "Tell me about a project that failed or didn't meet expectations. What did you learn?",
                "type": "behavioral",
                "difficulty": "hard",
                "frequency": "medium",
                "source": "Common Interview Question",
                "source_url": "",
                "date": "",
                "context": "Assesses self-awareness and growth mindset",
                "tips": "Be honest, focus on learnings and how you applied them"
            },
            {
                "question": "Describe your approach to managing risks in a complex program or project.",
                "type": "technical",
                "difficulty": "medium",
                "frequency": "high",
                "source": "Common Interview Question",
                "source_url": "",
                "date": "",
                "context": "Tests risk management methodology",
                "tips": "Mention frameworks, mitigation strategies, and communication"
            }
        ]

        # Add cybersecurity-specific if relevant
        if job_title and ("security" in job_title.lower() or "cyber" in job_title.lower()):
            generic_behavioral.extend([
                {
                    "question": "How would you prioritize vulnerabilities across multiple systems with limited remediation resources?",
                    "type": "situational",
                    "difficulty": "medium",
                    "frequency": "high",
                    "source": "Common Security Interview Question",
                    "source_url": "",
                    "date": "",
                    "context": "Tests risk-based prioritization",
                    "tips": "Mention CVSS scoring, business impact, and SLAs"
                },
                {
                    "question": "Explain your experience with security frameworks like NIST, ISO 27001, or industry-specific compliance requirements.",
                    "type": "technical",
                    "difficulty": "medium",
                    "frequency": "high",
                    "source": "Common Security Interview Question",
                    "source_url": "",
                    "date": "",
                    "context": "Assesses framework knowledge",
                    "tips": "Give specific examples of implementation and outcomes"
                }
            ])

        types = {"behavioral": 3, "technical": 1, "situational": 1}
        difficulty = {"medium": 4, "hard": 1}

        if job_title and "security" in job_title.lower():
            types["situational"] += 1
            types["technical"] += 1

        return {
            "questions": generic_behavioral,
            "total_questions": len(generic_behavioral),
            "question_types": types,
            "difficulty_breakdown": difficulty,
            "sources": ["Common Interview Questions"],
            "last_updated": datetime.utcnow().isoformat(),
            "company_name": company_name,
            "job_title": job_title,
            "note": "Generic questions - unable to fetch company-specific questions. Recommend manual research on Glassdoor and Reddit."
        }
