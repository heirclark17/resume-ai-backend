"""
Interview Questions Generator Service

Generates behavioral and technical interview questions using:
- Perplexity AI for real company/tech stack research
- OpenAI GPT-4-mini for structured question generation

Produces:
- 10 behavioral questions aligned to job description with STAR story prompts
- 10 technical questions based on company tech stack vs. candidate skills
"""

from openai import OpenAI
from app.config import get_settings
from app.services.perplexity_client import PerplexityClient
import json
import os

settings = get_settings()


class InterviewQuestionsGenerator:
    """Generates behavioral and technical interview questions with STAR story support"""

    def __init__(self):
        openai_api_key = os.getenv('OPENAI_API_KEY') or settings.openai_api_key

        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in Railway environment variables."
            )

        try:
            self.client = OpenAI(api_key=openai_api_key)
            self.perplexity_client = PerplexityClient()
        except Exception as e:
            raise ValueError(
                f"Failed to initialize clients: {str(e)}. "
                "Check that your API keys are valid."
            )

    async def research_company_tech_stack(
        self,
        company_name: str,
        job_description: str,
        industry: str = None
    ) -> dict:
        """
        Research company's actual tech stack using Perplexity

        Returns:
            {
                "tech_stack": ["Python", "AWS", "Kubernetes", ...],
                "tools_and_platforms": ["Jira", "GitHub", "Splunk", ...],
                "frameworks": ["React", "FastAPI", "TensorFlow", ...],
                "cloud_infrastructure": ["AWS", "GCP", "Azure", ...],
                "security_tools": ["Splunk", "CrowdStrike", ...],
                "methodologies": ["Agile", "DevOps", "CI/CD", ...],
                "sources": [{"title": "...", "url": "..."}]
            }
        """
        query = f"""Research {company_name}'s technology stack and tools. Find:

1. **Programming Languages & Frameworks** used at {company_name}
2. **Cloud Infrastructure** (AWS, Azure, GCP services)
3. **Security Tools & Platforms** (SIEM, vulnerability scanners, etc.)
4. **DevOps & CI/CD Tools** (Jenkins, GitHub Actions, etc.)
5. **Collaboration & Project Tools** (Jira, Confluence, ServiceNow)
6. **Data & Analytics Platforms** (Splunk, Elasticsearch, etc.)
7. **Development Methodologies** (Agile, Scrum, SAFe)

Focus on technologies mentioned in job postings, engineering blogs, and tech talks.
Include specific tool names and versions if available.
Cite sources with URLs."""

        try:
            result = await self.perplexity_client.research_with_citations(query)

            # Parse the result to extract tech stack
            tech_data = self._parse_tech_stack_from_research(
                result.get('content', ''),
                result.get('citations', []),
                job_description
            )

            return tech_data

        except Exception as e:
            print(f"Tech stack research failed: {e}")
            # Return extracted from job description as fallback
            return self._extract_tech_from_job_description(job_description)

    def _parse_tech_stack_from_research(
        self,
        content: str,
        citations: list,
        job_description: str
    ) -> dict:
        """Parse Perplexity research into structured tech stack data"""

        # Use GPT to structure the research
        prompt = f"""Analyze this research about a company's technology stack and extract structured data.

RESEARCH CONTENT:
{content}

JOB DESCRIPTION (for additional context):
{job_description[:2000]}

Extract and return a JSON object with these fields:
{{
    "tech_stack": ["list of programming languages and core technologies"],
    "tools_and_platforms": ["list of tools like Jira, ServiceNow, Splunk"],
    "frameworks": ["list of frameworks like React, FastAPI, Spring"],
    "cloud_infrastructure": ["list of cloud services like AWS EC2, Azure AD"],
    "security_tools": ["list of security tools if mentioned"],
    "methodologies": ["list of methodologies like Agile, DevOps"],
    "certifications_valued": ["list of certifications company values"]
}}

Only include items explicitly mentioned. Return valid JSON only."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                max_tokens=1000,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You extract technology information into structured JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            tech_data = json.loads(response.choices[0].message.content)
            tech_data['sources'] = citations
            return tech_data

        except Exception as e:
            print(f"Tech stack parsing failed: {e}")
            return self._extract_tech_from_job_description(job_description)

    def _extract_tech_from_job_description(self, job_description: str) -> dict:
        """Fallback: Extract tech stack from job description"""

        prompt = f"""Extract technology requirements from this job description.

JOB DESCRIPTION:
{job_description[:3000]}

Return a JSON object:
{{
    "tech_stack": ["programming languages mentioned"],
    "tools_and_platforms": ["tools mentioned"],
    "frameworks": ["frameworks mentioned"],
    "cloud_infrastructure": ["cloud platforms mentioned"],
    "security_tools": ["security tools mentioned"],
    "methodologies": ["methodologies mentioned"],
    "certifications_valued": ["certifications mentioned"]
}}

Only include items explicitly mentioned in the job description."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                max_tokens=800,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You extract technology requirements from job descriptions."},
                    {"role": "user", "content": prompt}
                ]
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"JD tech extraction failed: {e}")
            return {
                "tech_stack": [],
                "tools_and_platforms": [],
                "frameworks": [],
                "cloud_infrastructure": [],
                "security_tools": [],
                "methodologies": [],
                "certifications_valued": [],
                "sources": []
            }

    async def generate_behavioral_questions(
        self,
        job_description: str,
        job_title: str,
        company_name: str,
        core_responsibilities: list,
        company_values: list = None,
        industry: str = None
    ) -> dict:
        """
        Generate 10 behavioral interview questions aligned to the job description

        Each question includes:
        - The behavioral question
        - Why it's being asked (what competency it tests)
        - STAR story prompt to help candidate prepare
        - Key themes to address in the answer
        - Common mistakes to avoid

        Returns:
            {
                "questions": [
                    {
                        "id": 1,
                        "question": "Tell me about a time...",
                        "category": "leadership|teamwork|problem_solving|communication|adaptability|conflict_resolution|initiative|decision_making|time_management|customer_focus",
                        "competency_tested": "What skill this evaluates",
                        "why_asked": "Why interviewers ask this",
                        "difficulty": "easy|medium|hard",
                        "star_prompt": {
                            "situation_hint": "Think about a time when...",
                            "task_hint": "Your responsibility was to...",
                            "action_hint": "Focus on specific steps you took...",
                            "result_hint": "Quantify the outcome..."
                        },
                        "key_themes": ["theme1", "theme2"],
                        "common_mistakes": ["mistake1", "mistake2"],
                        "job_alignment": "How this relates to the specific job"
                    }
                ],
                "preparation_tips": ["tip1", "tip2"],
                "company_context": "How company culture affects answers"
            }
        """

        values_context = ""
        if company_values:
            values_context = f"\n\nCOMPANY VALUES TO INCORPORATE:\n" + "\n".join([f"- {v}" for v in company_values[:5]])

        responsibilities_text = "\n".join([f"- {r}" for r in core_responsibilities[:8]])

        system_prompt = """You are an expert interview coach specializing in behavioral interviews.

Your task is to generate 10 behavioral interview questions that:
1. Are specifically aligned to the job description and responsibilities
2. Cover different competency areas (leadership, problem-solving, teamwork, etc.)
3. Include STAR story prompts to help candidates prepare
4. Are the types of questions actually asked at this company/industry

For each question, provide detailed guidance on how to answer it effectively.
Focus on questions that test skills directly mentioned in the job description.

Return valid JSON only, no markdown or extra text."""

        user_prompt = f"""Generate 10 behavioral interview questions for this role:

JOB TITLE: {job_title}
COMPANY: {company_name}
INDUSTRY: {industry or 'Technology'}

KEY RESPONSIBILITIES:
{responsibilities_text}

JOB DESCRIPTION EXCERPT:
{job_description[:2500]}
{values_context}

Generate a JSON object with this exact structure:
{{
    "questions": [
        {{
            "id": 1,
            "question": "Tell me about a time when you [specific behavioral scenario from job requirements]",
            "category": "one of: leadership, teamwork, problem_solving, communication, adaptability, conflict_resolution, initiative, decision_making, time_management, customer_focus",
            "competency_tested": "The specific skill or trait this question evaluates",
            "why_asked": "2-3 sentences explaining what interviewers learn from this question",
            "difficulty": "easy, medium, or hard",
            "star_prompt": {{
                "situation_hint": "Think about a time when [specific scenario guidance]...",
                "task_hint": "Your responsibility was to [specific task guidance]...",
                "action_hint": "Focus on [specific action guidance]. Include details about...",
                "result_hint": "Quantify with [specific metrics]. Show impact by..."
            }},
            "key_themes": ["3-4 themes to weave into the answer"],
            "common_mistakes": ["2-3 common mistakes candidates make with this question"],
            "job_alignment": "How this question specifically relates to {job_title} at {company_name}"
        }}
    ],
    "preparation_tips": ["5 general tips for behavioral interview success"],
    "company_context": "2-3 sentences about how {company_name}'s culture should influence answers"
}}

REQUIREMENTS:
- Questions must directly reference skills/responsibilities from the job description
- Include a mix of difficulty levels (3 easy, 4 medium, 3 hard)
- Cover at least 6 different competency categories
- STAR prompts must be specific and actionable, not generic
- Job alignment must reference actual job requirements"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                max_tokens=4000,
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Behavioral question generation failed: {e}")
            raise ValueError(f"Failed to generate behavioral questions: {e}")

    async def generate_technical_questions(
        self,
        job_description: str,
        job_title: str,
        company_name: str,
        company_tech_stack: dict,
        candidate_skills: list,
        candidate_experience: list,
        must_have_skills: list = None,
        nice_to_have_skills: list = None
    ) -> dict:
        """
        Generate 10 technical interview questions based on:
        - Company's actual tech stack
        - Candidate's skills from their resume
        - Job requirements

        Each question includes:
        - Technical question
        - Expected answer points
        - How to leverage candidate's existing skills
        - Skill gap bridge (if candidate doesn't have exact skill)

        Returns:
            {
                "tech_stack_analysis": {
                    "company_technologies": ["tech1", "tech2"],
                    "candidate_matching_skills": ["skill1", "skill2"],
                    "skill_gaps": ["gap1", "gap2"],
                    "transferable_skills": [
                        {"candidate_skill": "X", "applies_to": "Y", "how_to_discuss": "..."}
                    ]
                },
                "questions": [
                    {
                        "id": 1,
                        "question": "How would you...",
                        "category": "system_design|coding|debugging|architecture|security|devops|database|api|cloud|performance",
                        "technology_focus": ["Python", "AWS"],
                        "difficulty": "easy|medium|hard",
                        "expected_answer_points": ["point1", "point2"],
                        "candidate_skill_leverage": {
                            "relevant_experience": "Your experience with X applies here because...",
                            "talking_points": ["point1", "point2"],
                            "skill_bridge": "Even though you used Y, you can discuss Z because..."
                        },
                        "follow_up_questions": ["follow-up 1", "follow-up 2"],
                        "red_flags": ["what NOT to say"],
                        "job_alignment": "Why this matters for the role"
                    }
                ],
                "preparation_strategy": {
                    "high_priority_topics": ["topic1", "topic2"],
                    "recommended_study_areas": ["area1", "area2"],
                    "hands_on_practice": ["exercise1", "exercise2"]
                }
            }
        """

        # Format candidate skills and experience
        skills_text = ", ".join(candidate_skills[:20]) if candidate_skills else "Not provided"

        experience_text = ""
        if candidate_experience:
            for exp in candidate_experience[:3]:
                title = exp.get('title') or exp.get('header', 'Role')
                bullets = exp.get('bullets', [])[:3]
                experience_text += f"\n{title}:\n" + "\n".join([f"  - {b}" for b in bullets])

        # Format company tech stack
        tech_stack_text = ""
        for category, items in company_tech_stack.items():
            if items and category != 'sources':
                tech_stack_text += f"\n{category.replace('_', ' ').title()}: {', '.join(items[:10])}"

        must_have_text = ", ".join(must_have_skills[:10]) if must_have_skills else ""
        nice_to_have_text = ", ".join(nice_to_have_skills[:10]) if nice_to_have_skills else ""

        system_prompt = """You are an expert technical interviewer who creates questions that:
1. Test actual job-relevant skills
2. Account for candidate's existing experience
3. Help candidates bridge skill gaps with transferable experience
4. Are realistic questions asked at top tech companies

Your questions should be challenging but fair, and help candidates showcase their strengths.
Focus on practical, real-world scenarios over theoretical puzzles.

Return valid JSON only, no markdown or extra text."""

        user_prompt = f"""Generate 10 technical interview questions for this role:

JOB TITLE: {job_title}
COMPANY: {company_name}

COMPANY'S TECH STACK (from research):
{tech_stack_text}

MUST-HAVE SKILLS FROM JOB:
{must_have_text}

NICE-TO-HAVE SKILLS FROM JOB:
{nice_to_have_text}

CANDIDATE'S SKILLS (from their resume):
{skills_text}

CANDIDATE'S RELEVANT EXPERIENCE:
{experience_text}

JOB DESCRIPTION:
{job_description[:2000]}

Generate a JSON object with this structure:
{{
    "tech_stack_analysis": {{
        "company_technologies": ["key technologies the company uses"],
        "candidate_matching_skills": ["skills from candidate that match"],
        "skill_gaps": ["technologies candidate may need to learn"],
        "transferable_skills": [
            {{
                "candidate_skill": "Skill candidate has",
                "applies_to": "Company technology it relates to",
                "how_to_discuss": "How to frame this in an interview"
            }}
        ]
    }},
    "questions": [
        {{
            "id": 1,
            "question": "Technical question that tests real skills needed for the job",
            "category": "one of: system_design, coding, debugging, architecture, security, devops, database, api, cloud, performance",
            "technology_focus": ["1-3 specific technologies this question covers"],
            "difficulty": "easy, medium, or hard",
            "expected_answer_points": ["4-6 key points a good answer should cover"],
            "candidate_skill_leverage": {{
                "relevant_experience": "Based on your resume, your experience with X is directly applicable...",
                "talking_points": ["2-3 specific things from candidate's background to mention"],
                "skill_bridge": "If candidate doesn't have exact skill, how to bridge from what they know"
            }},
            "follow_up_questions": ["2 likely follow-up questions"],
            "red_flags": ["2 things that would concern interviewers"],
            "job_alignment": "Why this specific skill matters for {job_title}"
        }}
    ],
    "preparation_strategy": {{
        "high_priority_topics": ["5 topics to focus study on based on skill gaps"],
        "recommended_study_areas": ["3-5 specific concepts to review"],
        "hands_on_practice": ["3 practical exercises to do before the interview"]
    }}
}}

REQUIREMENTS:
- Questions must test skills from the job description or company tech stack
- Include a mix: 3 easy, 4 medium, 3 hard
- Cover at least 5 different technical categories
- candidate_skill_leverage must reference ACTUAL skills from the candidate's resume
- For skill gaps, provide specific guidance on how to bridge with existing experience
- Questions should be the type actually asked at {company_name} or similar companies"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                max_tokens=4500,
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Technical question generation failed: {e}")
            raise ValueError(f"Failed to generate technical questions: {e}")

    async def generate_full_interview_questions(
        self,
        job_description: str,
        job_title: str,
        company_name: str,
        core_responsibilities: list,
        must_have_skills: list,
        nice_to_have_skills: list,
        candidate_skills: list,
        candidate_experience: list,
        company_values: list = None,
        industry: str = None
    ) -> dict:
        """
        Generate complete interview question set (behavioral + technical)

        This is the main entry point that:
        1. Researches company tech stack via Perplexity
        2. Generates 10 behavioral questions with STAR prompts
        3. Generates 10 technical questions with skill alignment

        Returns combined result with both question sets
        """

        print(f"🔍 Researching {company_name}'s tech stack via Perplexity...")

        # Step 1: Research company tech stack
        company_tech_stack = await self.research_company_tech_stack(
            company_name=company_name,
            job_description=job_description,
            industry=industry
        )

        print(f"✓ Found tech stack: {len(company_tech_stack.get('tech_stack', []))} technologies")

        # Step 2: Generate behavioral questions
        print(f"📝 Generating 10 behavioral questions...")
        behavioral_result = await self.generate_behavioral_questions(
            job_description=job_description,
            job_title=job_title,
            company_name=company_name,
            core_responsibilities=core_responsibilities,
            company_values=company_values,
            industry=industry
        )

        print(f"✓ Generated {len(behavioral_result.get('questions', []))} behavioral questions")

        # Step 3: Generate technical questions
        print(f"🔧 Generating 10 technical questions...")
        technical_result = await self.generate_technical_questions(
            job_description=job_description,
            job_title=job_title,
            company_name=company_name,
            company_tech_stack=company_tech_stack,
            candidate_skills=candidate_skills,
            candidate_experience=candidate_experience,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills
        )

        print(f"✓ Generated {len(technical_result.get('questions', []))} technical questions")

        # Combine results
        return {
            "company_name": company_name,
            "job_title": job_title,
            "company_tech_stack": company_tech_stack,
            "behavioral": behavioral_result,
            "technical": technical_result,
            "summary": {
                "total_questions": len(behavioral_result.get('questions', [])) + len(technical_result.get('questions', [])),
                "behavioral_count": len(behavioral_result.get('questions', [])),
                "technical_count": len(technical_result.get('questions', [])),
                "skill_matches": len(technical_result.get('tech_stack_analysis', {}).get('candidate_matching_skills', [])),
                "skill_gaps": len(technical_result.get('tech_stack_analysis', {}).get('skill_gaps', []))
            }
        }
