"""
Certification Recommendation Service

Generates personalized certification recommendations for career advancement
using GPT-4.1-mini based on target role, industry, and current skills.
"""

import os
from openai import AsyncOpenAI
import json
from typing import Dict, Any, List

class CertificationService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4.1-mini"

    async def recommend_certifications(
        self,
        job_title: str,
        company_name: str,
        industry: str,
        job_description: str,
        current_skills: List[str],
        experience_level: str
    ) -> Dict[str, Any]:
        """
        Generate personalized certification recommendations

        Args:
            job_title: Target role title
            company_name: Target company name
            industry: Industry sector
            job_description: Full JD text
            current_skills: List of candidate's current skills
            experience_level: entry|mid|senior

        Returns:
            Dictionary with certification recommendations organized by level
        """

        system_prompt = """You are a career development expert and certification advisor
with deep knowledge of professional certifications across industries including:
- Cybersecurity (CISSP, CISM, Security+, CEH, etc.)
- Project Management (PMP, CAPM, CSM, SAFe, etc.)
- Cloud (AWS, Azure, GCP certifications)
- IT (CompTIA, Microsoft, Cisco, etc.)
- Data & Analytics (Tableau, PowerBI, etc.)

Your job is to recommend relevant, valuable certifications that will:
1. Advance the candidate's career toward their target role
2. Fill skill gaps identified in the job description
3. Provide strong ROI (return on investment)
4. Follow a logical progression path"""

        user_prompt = f"""Generate personalized certification recommendations for this career situation.

TARGET ROLE: {job_title}
COMPANY: {company_name}
INDUSTRY: {industry}
EXPERIENCE LEVEL: {experience_level}

JOB DESCRIPTION:
{job_description}

CURRENT SKILLS:
{', '.join(current_skills)}

Provide comprehensive certification recommendations in this JSON format:

{{
  "certifications_by_level": {{
    "entry": [
      {{
        "name": "Certification Name",
        "provider": "Issuing Organization",
        "priority": "high|medium|low",
        "why_recommended": "2-3 sentences explaining why this cert is valuable for this role",
        "skills_gained": ["skill1", "skill2", "skill3"],
        "cost": "$500-$1000",
        "time_to_complete": "2-3 months",
        "difficulty": "beginner|intermediate|advanced",
        "roi_rating": "high|medium|low",
        "prerequisites": "None" or "List prerequisites",
        "study_resources": [
          "Official training course link or name",
          "Recommended book or online course",
          "Practice exam resource"
        ],
        "exam_details": {{
          "format": "Multiple choice, 100 questions",
          "duration": "3 hours",
          "passing_score": "70%",
          "validity": "3 years"
        }}
      }}
    ],
    "mid": [
      // Same structure as entry level
    ],
    "advanced": [
      // Same structure as entry level
    ]
  }},
  "recommended_path": [
    {{
      "step": 1,
      "certification": "Certification Name",
      "timeline": "Months 1-3",
      "rationale": "Why to do this first"
    }}
  ],
  "personalized_advice": "2-3 paragraphs of personalized career advice based on target role, current skills, and recommended certifications"
}}

CRITICAL REQUIREMENTS:
- Provide 3-5 certifications for each level (entry, mid, advanced)
- Prioritize certifications that match job description requirements
- Include specific cost ranges and time estimates
- Recommend actual, real certifications (not made-up ones)
- Study resources should be real and helpful
- Recommended path should be sequential and logical
- Entry: Foundation certs for someone starting in the field
- Mid: Intermediate certs for practitioners (2-5 years experience)
- Advanced: Expert-level certs for leaders (5+ years experience)
- Return valid JSON only"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Error generating certification recommendations: {e}")
            raise Exception(f"Failed to generate recommendations: {str(e)}")
