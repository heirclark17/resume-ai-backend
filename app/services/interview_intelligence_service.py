"""
Interview Intelligence Service - Sales Navigator-inspired features
Provides relevance scoring, talking points, and job alignment for interview prep
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from openai import AsyncOpenAI
from app.config import get_settings


class InterviewIntelligenceService:
    """
    Service for analyzing interview prep content and providing actionable intelligence
    Similar to LinkedIn Sales Navigator's Buyer Intent Signals
    """

    def __init__(self):
        settings = get_settings()
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def score_relevance(
        self,
        content_items: List[Dict],
        job_description: str,
        job_title: str,
        content_type: str = "strategy"  # "strategy" or "news"
    ) -> List[Dict]:
        """
        Score content relevance to the specific job (like Buyer Intent Score)

        Args:
            content_items: List of strategic initiatives or news items
            job_description: Full job description
            job_title: Job title
            content_type: Type of content being scored

        Returns:
            Enhanced content items with relevance_score (0-10), priority, and alignment details
        """

        print(f"Scoring relevance for {len(content_items)} {content_type} items...")

        # Build scoring prompt
        prompt = f"""You are an interview preparation expert. Score how relevant each piece of company information is for a candidate interviewing for this role.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:1500]}

CONTENT TO SCORE ({content_type.upper()}):
{json.dumps(content_items[:10], indent=2)}

For each item, provide:
1. **relevance_score** (0-10): How relevant is this to the specific job?
   - 9-10: Critical - Directly relates to core job responsibilities
   - 7-8: High - Important for understanding the role context
   - 5-6: Medium - Useful background information
   - 0-4: Low - Interesting but not directly relevant

2. **priority**: "Critical", "High", or "Medium" (DO NOT use "Context")

3. **why_it_matters**: 1-sentence explanation of why this is relevant to THIS specific role

4. **job_alignment**: Which specific job requirements or responsibilities does this connect to?

5. **talking_point**: How could a candidate reference this in the interview? (30-50 words)

6. **example_statements**: 2 specific example statements showing how to mention THIS PARTICULAR initiative in the interview (each 20-30 words)

7. **questions_to_ask**: 2 smart, specific questions about THIS PARTICULAR initiative to ask the interviewer (each 15-25 words)

Return ONLY a JSON object with this structure:
{{
  "scored_items": [
    {{
      "original_item": {{...}},
      "relevance_score": 9.5,
      "priority": "Critical",
      "why_it_matters": "This initiative directly relates to the core responsibility of...",
      "job_alignment": ["Requirement 1", "Responsibility 2"],
      "talking_point": "I'm excited about [initiative] because it aligns with my experience in...",
      "example_statements": [
        "I was impressed to learn about [specific initiative] and how it connects to [specific aspect of role]...",
        "Given my experience with [relevant skill], I'm eager to contribute to [specific initiative aspect]..."
      ],
      "questions_to_ask": [
        "How does [specific initiative] impact the team's roadmap for the next 6-12 months?",
        "What role would this position play in supporting [specific initiative aspect]?"
      ]
    }}
  ]
}}"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interview preparation coach who helps candidates understand which company information matters most for specific roles. You provide relevance scores and actionable talking points."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=4000
            )

            result = json.loads(response.choices[0].message.content)
            scored_items = result.get("scored_items", [])

            print(f"✓ Scored {len(scored_items)} items with relevance ratings")
            return scored_items

        except Exception as e:
            print(f"⚠️ Relevance scoring failed: {e}")
            # Return original items with default scores
            return [{
                "original_item": item,
                "relevance_score": 5.0,
                "priority": "Medium",
                "why_it_matters": "Relevant company information",
                "job_alignment": [],
                "talking_point": "",
                "example_statements": [],
                "questions_to_ask": []
            } for item in content_items]

    async def generate_talking_points(
        self,
        content: Dict,
        job_description: str,
        job_title: str,
        company_name: str
    ) -> Dict:
        """
        Generate specific talking points for how to use company research in interviews

        Returns:
        {
            "how_to_use_in_interview": "2-3 sentence explanation",
            "example_statements": ["Statement 1", "Statement 2"],
            "questions_to_ask": ["Question 1", "Question 2"],
            "dos_and_donts": {
                "dos": ["Do this", "Do that"],
                "donts": ["Don't do this"]
            }
        }
        """

        print(f"Generating talking points for {company_name} {job_title} interview...")

        prompt = f"""You are an interview coach helping a candidate prepare for this role.

JOB: {job_title} at {company_name}

JOB DESCRIPTION:
{job_description[:1500]}

COMPANY RESEARCH:
{json.dumps(content, indent=2)[:2000]}

Generate actionable talking points. Return ONLY a JSON object:

{{
  "how_to_use_in_interview": "2-3 sentence explanation of when and how to bring this up",
  "example_statements": [
    "I was excited to learn about [specific initiative]...",
    "Given your focus on [area], I'd love to contribute by..."
  ],
  "questions_to_ask": [
    "How does [initiative] impact the team's roadmap?",
    "What role would I play in supporting [strategy]?"
  ],
  "dos_and_donts": {{
    "dos": [
      "Reference specific initiatives by name",
      "Connect to your relevant experience"
    ],
    "donts": [
      "Don't just repeat what's on the website",
      "Don't make assumptions about implementation"
    ]
  }},
  "prep_time_minutes": 15
}}"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interview coach who creates specific, actionable talking points. Focus on HOW to use information, not just WHAT to say."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1500
            )

            result = json.loads(response.choices[0].message.content)
            print("✓ Generated talking points")
            return result

        except Exception as e:
            print(f"⚠️ Talking points generation failed: {e}")
            return {
                "how_to_use_in_interview": "Reference this information when discussing your fit for the role.",
                "example_statements": [],
                "questions_to_ask": [],
                "dos_and_donts": {"dos": [], "donts": []},
                "prep_time_minutes": 10
            }

    async def analyze_job_alignment(
        self,
        company_research: Dict,
        job_description: str,
        job_title: str,
        company_name: str
    ) -> Dict:
        """
        Analyze how company research aligns with specific job requirements

        Returns:
        {
            "requirement_mapping": [
                {
                    "requirement": "Experience with cloud security",
                    "company_evidence": ["Initiative X", "Strategy Y"],
                    "how_to_discuss": "When discussing this requirement, mention...",
                    "match_strength": 9
                }
            ],
            "overall_alignment_score": 8.5,
            "top_alignment_areas": ["Area 1", "Area 2"],
            "gaps_to_address": ["Gap 1"]
        }
        """

        print(f"Analyzing job alignment for {job_title} at {company_name}...")

        prompt = f"""You are an interview strategist. Analyze how this company's initiatives align with the job requirements.

JOB: {job_title} at {company_name}

JOB DESCRIPTION:
{job_description[:2000]}

COMPANY RESEARCH:
{json.dumps(company_research, indent=2)[:2000]}

Map job requirements to company initiatives. Return ONLY a JSON object:

{{
  "requirement_mapping": [
    {{
      "requirement": "Specific requirement from job description",
      "company_evidence": ["Initiative or strategy that relates"],
      "how_to_discuss": "1-sentence advice on how to connect these in interview",
      "match_strength": 9
    }}
  ],
  "overall_alignment_score": 8.5,
  "top_alignment_areas": ["Area where company focus matches job needs"],
  "gaps_to_address": ["Areas where company info doesn't clearly match job requirements"],
  "interview_strategy": "2-3 sentence high-level strategy for leveraging this alignment"
}}

Focus on the TOP 5-7 most important requirements from the job description."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at mapping job requirements to company initiatives. Help candidates see the connections."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            print(f"✓ Mapped {len(result.get('requirement_mapping', []))} job requirements")
            return result

        except Exception as e:
            print(f"⚠️ Job alignment analysis failed: {e}")
            return {
                "requirement_mapping": [],
                "overall_alignment_score": 7.0,
                "top_alignment_areas": [],
                "gaps_to_address": [],
                "interview_strategy": "Connect your experience to the company's strategic initiatives."
            }

    async def calculate_interview_readiness(
        self,
        prep_data: Dict,
        sections_completed: List[str]
    ) -> Dict:
        """
        Calculate overall interview readiness score (like Sales Navigator's account score)

        Args:
            prep_data: Full interview prep data
            sections_completed: List of section IDs that user has reviewed

        Returns:
        {
            "readiness_score": 8.2,
            "progress_percentage": 67,
            "time_invested_minutes": 135,
            "critical_gaps": ["Gap 1", "Gap 2"],
            "next_actions": [
                {
                    "action": "Review company values",
                    "priority": "Critical",
                    "time_estimate_minutes": 15,
                    "why": "Likely interview question topic"
                }
            ]
        }
        """

        print("Calculating interview readiness score...")

        # Define sections and their weights
        section_weights = {
            "company_profile": 0.10,
            "role_analysis": 0.15,
            "values_culture": 0.20,
            "strategy_news": 0.20,
            "interview_prep_checklist": 0.15,
            "questions_to_ask": 0.10,
            "practice_questions": 0.10
        }

        # Calculate progress
        total_sections = len(section_weights)
        completed_count = len(sections_completed)
        progress_percentage = int((completed_count / total_sections) * 100)

        # Calculate weighted score
        weighted_score = 0.0
        for section, weight in section_weights.items():
            if section in sections_completed:
                weighted_score += weight * 10  # Full points
            else:
                weighted_score += weight * 3   # Partial points for having data

        # Identify critical gaps
        critical_sections = ["role_analysis", "values_culture", "strategy_news"]
        critical_gaps = [s for s in critical_sections if s not in sections_completed]

        # Generate next actions
        next_actions = []

        if "values_culture" not in sections_completed:
            next_actions.append({
                "action": "Review company values and prepare alignment examples",
                "priority": "Critical",
                "time_estimate_minutes": 20,
                "why": "Values alignment is a common interview topic"
            })

        if "strategy_news" not in sections_completed:
            next_actions.append({
                "action": "Study recent company initiatives and prepare talking points",
                "priority": "Critical",
                "time_estimate_minutes": 25,
                "why": "Shows you've done your homework on company direction"
            })

        if "practice_questions" not in sections_completed:
            next_actions.append({
                "action": "Practice answering common interview questions",
                "priority": "High",
                "time_estimate_minutes": 30,
                "why": "Practice reduces interview anxiety"
            })

        if "questions_to_ask" not in sections_completed:
            next_actions.append({
                "action": "Prepare 5-7 insightful questions to ask interviewer",
                "priority": "High",
                "time_estimate_minutes": 15,
                "why": "Good questions show engagement and curiosity"
            })

        # Estimate time invested (rough calculation)
        time_per_section = {
            "company_profile": 10,
            "role_analysis": 15,
            "values_culture": 20,
            "strategy_news": 25,
            "interview_prep_checklist": 20,
            "questions_to_ask": 15,
            "practice_questions": 30
        }

        time_invested = sum(time_per_section.get(s, 10) for s in sections_completed)

        result = {
            "readiness_score": round(weighted_score, 1),
            "progress_percentage": progress_percentage,
            "time_invested_minutes": time_invested,
            "critical_gaps": critical_gaps,
            "next_actions": next_actions[:4],  # Top 4 actions
            "status": self._get_readiness_status(weighted_score),
            "recommendation": self._get_recommendation(weighted_score, critical_gaps)
        }

        print(f"✓ Readiness score: {result['readiness_score']}/10 ({progress_percentage}% complete)")
        return result

    def _get_readiness_status(self, score: float) -> str:
        """Get readiness status label"""
        if score >= 8.5:
            return "Interview Ready"
        elif score >= 7.0:
            return "Nearly Ready"
        elif score >= 5.0:
            return "In Progress"
        else:
            return "Just Started"

    def _get_recommendation(self, score: float, critical_gaps: List[str]) -> str:
        """Get personalized recommendation"""
        if score >= 8.5:
            return "You're well-prepared! Do a final review of your STAR stories and you'll be ready to ace this interview."
        elif score >= 7.0:
            if critical_gaps:
                gap_names = ", ".join(critical_gaps)
                return f"You're almost ready. Focus on completing these critical sections: {gap_names}"
            return "You're nearly ready. Review your weak areas and practice your delivery."
        elif score >= 5.0:
            return "Keep going! Complete the critical sections first, then move to practice questions."
        else:
            return "Just getting started. Begin with Company Profile and Role Analysis to build your foundation."

    async def generate_values_alignment_scorecard(
        self,
        stated_values: List[Dict],
        candidate_background: str,
        job_description: str,
        company_name: str
    ) -> Dict:
        """
        Generate values alignment scorecard (Phase 2 feature - including for completeness)

        Returns:
        {
            "overall_culture_fit": 8.7,
            "value_matches": [
                {
                    "value": "Innovation",
                    "match_percentage": 95,
                    "your_evidence": "Led AI security initiative...",
                    "how_to_discuss": "Reference your innovation in...",
                    "likely_interview_question": "Tell me about a time you innovated..."
                }
            ],
            "star_story_prompts": [...],
            "interview_questions_by_value": {...}
        }
        """

        print(f"Generating values alignment scorecard for {company_name}...")

        prompt = f"""You are an interview coach. Analyze how well this candidate aligns with company values.

COMPANY: {company_name}

COMPANY VALUES:
{json.dumps(stated_values, indent=2)}

CANDIDATE BACKGROUND:
{candidate_background[:1500]}

JOB DESCRIPTION:
{job_description[:1000]}

Create a values alignment scorecard. Return ONLY a JSON object:

{{
  "overall_culture_fit": 8.7,
  "value_matches": [
    {{
      "value": "Value name",
      "match_percentage": 95,
      "your_evidence": "Specific example from your background that demonstrates this value",
      "how_to_discuss": "When asked about this value, say...",
      "likely_interview_question": "Sample behavioral question about this value",
      "star_story_prompt": "Situation from your background that showcases this value"
    }}
  ],
  "dos": [
    "Do reference specific examples that align with their values",
    "Do use their language when describing your approach"
  ],
  "donts": [
    "Don't claim to embody values without concrete examples",
    "Don't contradict their stated values with different priorities"
  ],
  "top_strengths": ["Your top 2-3 value alignments"],
  "areas_to_emphasize": ["Values where you should focus your examples"]
}}"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at assessing culture fit and helping candidates demonstrate value alignment through concrete examples."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=2500
            )

            result = json.loads(response.choices[0].message.content)
            print(f"✓ Generated alignment scorecard for {len(result.get('value_matches', []))} values")
            return result

        except Exception as e:
            print(f"⚠️ Values alignment scorecard failed: {e}")
            return {
                "overall_culture_fit": 7.5,
                "value_matches": [],
                "dos": [],
                "donts": [],
                "top_strengths": [],
                "areas_to_emphasize": []
            }
