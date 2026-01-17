"""
Resume Analysis Service - AI-powered resume change analysis

Analyzes differences between original and tailored resumes,
identifies keywords, and calculates match scores using GPT-4.1-mini
"""

import os
from openai import AsyncOpenAI
import json
from typing import Dict, Any, List

class ResumeAnalysisService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4.1-mini"

    async def analyze_resume_changes(
        self,
        original_resume: Dict[str, Any],
        tailored_resume: Dict[str, Any],
        job_description: str,
        job_title: str
    ) -> Dict[str, Any]:
        """
        Analyze all changes between original and tailored resume
        Returns detailed explanations for each section change
        """

        # Define sections to compare
        sections = [
            ("Professional Summary", "summary", "summary"),
            ("Experience", "experience", "experience"),
            ("Skills", "skills", "skills"),
            ("Certifications", "certifications", "certifications"),
            ("Education", "education", "education"),
        ]

        analysis_results = []

        for section_name, orig_key, tailored_key in sections:
            original_content = self._extract_section_content(original_resume, orig_key)
            tailored_content = self._extract_section_content(tailored_resume, tailored_key)

            if original_content != tailored_content:
                section_analysis = await self._analyze_section(
                    section_name=section_name,
                    original_content=original_content,
                    tailored_content=tailored_content,
                    job_description=job_description,
                    job_title=job_title
                )
                if section_analysis:
                    analysis_results.append(section_analysis)

        return {"sections": analysis_results}

    def _extract_section_content(self, resume: Dict[str, Any], key: str) -> str:
        """Extract content from resume section"""
        if key not in resume:
            return ""

        content = resume[key]

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "\n".join([str(item) for item in content])
        elif isinstance(content, dict):
            return json.dumps(content, indent=2)
        else:
            return str(content)

    async def _analyze_section(
        self,
        section_name: str,
        original_content: str,
        tailored_content: str,
        job_description: str,
        job_title: str
    ) -> Dict[str, Any]:
        """Analyze changes in a specific section"""

        system_prompt = """You are an expert resume analyst and career coach.
Your job is to analyze changes between an original resume section and a tailored version,
explaining WHY changes were made, WHAT changed, and HOW it helps the candidate.

You must provide detailed, actionable insights that help candidates understand
the strategic value of each change."""

        user_prompt = f"""Analyze the changes made to the {section_name} section when tailoring for this job.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

ORIGINAL {section_name.upper()}:
{original_content}

TAILORED {section_name.upper()}:
{tailored_content}

Provide a detailed analysis in this JSON format:

{{
  "section_name": "{section_name}",
  "changes": [
    {{
      "change_type": "added|modified|removed",
      "impact_level": "high|medium|low",
      "original_text": "exact text from original (or null if added)",
      "new_text": "exact text from tailored (or null if removed)",
      "why_this_matters": "2-3 sentences explaining strategic importance",
      "what_changed": "Specific description of the change",
      "how_it_helps": "How this change improves job match",
      "job_requirements_matched": ["requirement 1", "requirement 2"],
      "keywords_added": ["keyword1", "keyword2"]
    }}
  ]
}}

CRITICAL REQUIREMENTS:
- Identify ALL meaningful changes (additions, modifications, removals)
- For each change, provide specific original_text and new_text
- Explain WHY each change matters strategically
- Map changes to specific job requirements
- Identify keywords that were added
- Use "high" impact for changes directly matching key requirements
- Use "medium" for supporting changes
- Use "low" for minor wording adjustments
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
            print(f"Error analyzing section {section_name}: {e}")
            return None

    async def analyze_keywords(
        self,
        original_resume: Dict[str, Any],
        tailored_resume: Dict[str, Any],
        job_description: str
    ) -> Dict[str, Any]:
        """
        Identify and categorize all new keywords added to tailored resume
        """

        original_text = json.dumps(original_resume)
        tailored_text = json.dumps(tailored_resume)

        system_prompt = """You are an ATS (Applicant Tracking System) and keyword optimization expert.
Your job is to identify new keywords added to a tailored resume and categorize them
by type, explaining their strategic value."""

        user_prompt = f"""Analyze the keywords added when tailoring this resume for the job.

JOB DESCRIPTION:
{job_description}

ORIGINAL RESUME:
{original_text}

TAILORED RESUME:
{tailored_text}

Identify ALL new keywords, phrases, and terminology added to the tailored version.
Categorize and analyze them in this JSON format:

{{
  "keyword_groups": [
    {{
      "category": "technical_skills|soft_skills|industry_terms|certifications|tools_technologies",
      "keywords": [
        {{
          "keyword": "exact keyword or phrase",
          "why_added": "Why this keyword is important for this job",
          "jd_frequency": 3,
          "ats_impact": "high|medium|low",
          "location_in_resume": "Professional Summary|Experience|Skills|etc",
          "context": "Brief context of how it's used"
        }}
      ]
    }}
  ],
  "total_keywords_added": 25,
  "ats_optimization_score": 85
}}

CRITICAL REQUIREMENTS:
- Only include keywords that are NEW in tailored version
- Group by category (technical_skills, soft_skills, industry_terms, certifications, tools_technologies)
- For each keyword, explain why it was added
- Indicate how many times it appears in job description (jd_frequency)
- Rate ATS impact (high/medium/low)
- Show where in resume it appears
- Calculate overall ATS optimization score (0-100)
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
            print(f"Error analyzing keywords: {e}")
            raise Exception(f"Failed to analyze keywords: {str(e)}")

    async def calculate_match_score(
        self,
        tailored_resume: Dict[str, Any],
        job_description: str,
        job_title: str
    ) -> Dict[str, Any]:
        """
        Calculate 0-100 match score with detailed breakdown
        """

        resume_text = json.dumps(tailored_resume, indent=2)

        system_prompt = """You are an expert recruiter and ATS specialist.
Your job is to calculate how well a tailored resume matches a job description,
providing a score between 0-100 and detailed analysis of strengths, gaps, and improvements."""

        user_prompt = f"""Calculate the match score for this tailored resume against the job description.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

TAILORED RESUME:
{resume_text}

Analyze the match and provide a comprehensive score in this JSON format:

{{
  "overall_score": 85,
  "grade": "Excellent|Very Good|Good|Fair|Needs Improvement",
  "category_scores": {{
    "skills_match": 90,
    "experience_relevance": 85,
    "keyword_optimization": 80,
    "role_alignment": 88
  }},
  "strengths": [
    "Specific strength 1 with evidence",
    "Specific strength 2 with evidence",
    "Specific strength 3 with evidence"
  ],
  "gaps": [
    "Specific gap or missing element",
    "Another gap or weakness"
  ],
  "improvements": [
    {{
      "suggestion": "Specific actionable improvement",
      "priority": "high|medium|low",
      "potential_score_gain": 5,
      "rationale": "Why this would help"
    }}
  ],
  "explanation": "2-3 paragraph natural language explanation of the score, highlighting key matches and areas for improvement"
}}

CRITICAL REQUIREMENTS:
- overall_score MUST be between 0-100 (integer)
- Grade: 90-100=Excellent, 80-89=Very Good, 70-79=Good, 60-69=Fair, <60=Needs Improvement
- All category_scores must be 0-100
- Provide 3-5 specific strengths with evidence
- Identify 0-3 gaps (empty array if no gaps)
- Provide 3-5 actionable improvements with priority and potential gain
- Explanation must be detailed and specific to this job/resume
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

            # Validate score range
            if result.get("overall_score", 0) < 0:
                result["overall_score"] = 0
            if result.get("overall_score", 0) > 100:
                result["overall_score"] = 100

            return result

        except Exception as e:
            print(f"Error calculating match score: {e}")
            raise Exception(f"Failed to calculate match score: {str(e)}")
