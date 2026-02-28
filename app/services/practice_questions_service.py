"""
Service for generating job-specific practice questions and AI-generated STAR stories
"""
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import os
import json

from app.services.gateway import get_gateway

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PracticeQuestionsService:
    """Generate job-specific practice questions and STAR stories"""

    async def generate_job_specific_questions(
        self,
        job_description: str,
        job_title: str,
        core_responsibilities: List[str],
        must_have_skills: List[str],
        company_name: str,
        num_questions: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate practice questions strictly based on job description responsibilities

        Args:
            job_description: Full job description text
            job_title: Job title
            core_responsibilities: List of core responsibilities from job posting
            must_have_skills: Required skills from job posting
            company_name: Name of the company
            num_questions: Number of questions to generate

        Returns:
            List of question objects with category and difficulty
        """

        prompt = f"""You are an expert interview coach. Generate {num_questions} targeted practice interview questions for a candidate applying to {company_name} for the position of {job_title}.

JOB DESCRIPTION:
{job_description}

CORE RESPONSIBILITIES:
{chr(10).join(f"- {resp}" for resp in core_responsibilities)}

MUST-HAVE SKILLS:
{chr(10).join(f"- {skill}" for skill in must_have_skills)}

REQUIREMENTS:
1. Create questions that DIRECTLY test the candidate's ability to perform the listed responsibilities
2. Focus on specific scenarios and challenges mentioned in the job description
3. Include a mix of:
   - Behavioral questions (40%) - Past experience demonstrating required skills
   - Situational questions (30%) - Hypothetical scenarios related to responsibilities
   - Technical questions (20%) - Specific skills and tools mentioned
   - Role-specific questions (10%) - Unique to this position

4. Make questions specific to THIS role, not generic interview questions
5. Include questions that assess cultural fit based on the company and role

6. For each question, provide:
   - question: The question text
   - category: behavioral, situational, technical, or role_specific
   - difficulty: easy, medium, or hard
   - why_asked: Brief explanation of what this question assesses
   - key_skills_tested: List of 2-3 skills this question evaluates

Return ONLY a valid JSON array of question objects. No markdown, no additional text.

Example format:
[
  {{
    "question": "Tell me about a time when you had to manage conflicting priorities across multiple stakeholders. How did you decide what to prioritize?",
    "category": "behavioral",
    "difficulty": "medium",
    "why_asked": "Tests stakeholder management and prioritization skills - core to this role",
    "key_skills_tested": ["Stakeholder Management", "Prioritization", "Decision Making"]
  }}
]
"""

        try:
            response = await get_gateway().execute(
                "openai",
                client.chat.completions.create,
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert interview coach who generates highly specific, role-tailored interview questions. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            content = content.strip()

            questions = json.loads(content)

            print(f"✓ Generated {len(questions)} job-specific practice questions")
            return questions

        except json.JSONDecodeError as e:
            print(f"✗ JSON parse error: {e}")
            print(f"Response content: {content[:500]}")
            # Fallback to basic questions if JSON parsing fails
            return self._get_fallback_questions(job_title, core_responsibilities)

        except Exception as e:
            print(f"✗ Error generating practice questions: {e}")
            return self._get_fallback_questions(job_title, core_responsibilities)

    async def generate_star_story(
        self,
        question: str,
        candidate_background: str,
        job_description: str,
        job_title: str
    ) -> Dict[str, str]:
        """
        Generate an AI-powered STAR story for answering a specific question

        Args:
            question: The practice interview question
            candidate_background: Candidate's resume summary or experience
            job_description: Job description text
            job_title: Job title

        Returns:
            Dictionary with Situation, Task, Action, Result
        """

        prompt = f"""You are an elite interview coach who has helped hundreds of candidates land roles at top companies. Generate an EXTREMELY DETAILED and compelling STAR story to answer this interview question. This story should be detailed enough to fill a 3-5 minute verbal answer in an actual interview.

INTERVIEW QUESTION:
{question}

CANDIDATE'S BACKGROUND:
{candidate_background}

JOB APPLYING FOR:
{job_title}

JOB DESCRIPTION:
{job_description}

Generate a STAR story with the following depth and detail:

1. SITUATION (15% of story - 4-6 sentences):
   - Set the specific scene: company type, team size, your role at the time
   - Describe the business context and why it mattered (revenue impact, customer impact, compliance risk, etc.)
   - Include specific numbers: team size, budget, timeline, scale of the problem
   - Paint a vivid picture so the interviewer can visualize the challenge
   - Mention any constraints or complicating factors (tight deadline, limited resources, competing priorities)

2. TASK (10% of story - 3-4 sentences):
   - Define YOUR specific responsibility (not the team's, YOURS)
   - Explain what success looked like with concrete criteria
   - Mention the stakes: what would happen if this failed?
   - Connect the task directly to skills relevant to the job you're applying for

3. ACTION (60% of story - THIS IS THE MOST IMPORTANT SECTION - 10-15 sentences minimum):
   - Break down EVERY specific step YOU personally took, in chronological order
   - Name specific tools, frameworks, methodologies, and technologies you used
   - Describe how you influenced or led others (stakeholder meetings, presentations, 1:1 coaching)
   - Include at least one moment of problem-solving when something went wrong or an obstacle arose
   - Detail your decision-making process: what options did you consider? Why did you choose this approach?
   - Mention cross-functional collaboration: who did you work with and how?
   - Include specific examples of communication: "I presented to the VP of Engineering...", "I created a weekly dashboard for the executive team..."
   - Show leadership behaviors even if you weren't a formal leader
   - Include technical depth where appropriate (specific configurations, architectures, processes)
   - Describe how you tracked progress and adjusted your approach

4. RESULT (15% of story - 4-6 sentences):
   - Lead with the PRIMARY quantifiable outcome (percentage improvement, dollar savings, time reduction)
   - Include at least 3 different metrics or outcomes
   - Mention both immediate results AND longer-term impact
   - Include recognition received (awards, promotions, being asked to repeat the initiative)
   - Connect the results back to business value (revenue, customer satisfaction, risk reduction)
   - End with what you learned or how this experience prepared you for THIS role

CRITICAL REQUIREMENTS:
- Use first-person perspective ("I...") throughout
- Be EXTREMELY specific - no generic or vague language
- Every claim must have a number, percentage, timeframe, or concrete example
- The ACTION section must be the longest and most detailed section by far
- Sound natural and conversational, as if telling a compelling story in person
- Align the story with the skills and responsibilities in the job description
- The total story should be detailed enough for a 3-5 minute verbal answer

Return ONLY a valid JSON object with keys: situation, task, action, result. No markdown, no additional text.
"""

        try:
            response = await get_gateway().execute(
                "openai",
                client.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are an elite interview coach who creates exceptionally detailed STAR stories. Your stories are so well-crafted that candidates who use them consistently receive offers. You always return valid JSON only, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )

            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            content = content.strip()

            star_story = json.loads(content)

            print(f"✓ Generated STAR story for question: {question[:50]}...")
            return star_story

        except json.JSONDecodeError as e:
            print(f"✗ JSON parse error generating STAR story: {e}")
            return self._get_fallback_star_story()

        except Exception as e:
            print(f"✗ Error generating STAR story: {e}")
            return self._get_fallback_star_story()

    def _get_fallback_questions(self, job_title: str, responsibilities: List[str]) -> List[Dict[str, Any]]:
        """Fallback questions if AI generation fails"""
        return [
            {
                "question": f"Tell me about a time when you successfully {responsibilities[0] if responsibilities else 'led a project'}.  What was your approach and what was the outcome?",
                "category": "behavioral",
                "difficulty": "medium",
                "why_asked": f"Assesses experience with core responsibility: {responsibilities[0] if responsibilities else 'project leadership'}",
                "key_skills_tested": ["Leadership", "Communication", "Results Orientation"]
            },
            {
                "question": f"Describe a situation where you had to overcome a significant challenge in your role. How did you handle it?",
                "category": "behavioral",
                "difficulty": "medium",
                "why_asked": "Tests problem-solving and resilience",
                "key_skills_tested": ["Problem Solving", "Resilience", "Critical Thinking"]
            },
            {
                "question": f"How would you approach {responsibilities[1] if len(responsibilities) > 1 else 'prioritizing multiple competing demands'} in this role?",
                "category": "situational",
                "difficulty": "medium",
                "why_asked": f"Evaluates strategic thinking for: {responsibilities[1] if len(responsibilities) > 1 else 'prioritization'}",
                "key_skills_tested": ["Strategic Thinking", "Prioritization", "Time Management"]
            }
        ]

    def _get_fallback_star_story(self) -> Dict[str, str]:
        """Fallback STAR story if AI generation fails"""
        return {
            "situation": "Unable to generate a detailed STAR story at this time. Please click 'Regenerate' to try again, or use the 'Edit' button to write your own story using the STAR framework.",
            "task": "Think about: What was YOUR specific responsibility? What did success look like? What were the stakes?",
            "action": "This should be the longest section (60% of your story). Detail every step you took, tools you used, people you collaborated with, and obstacles you overcame.",
            "result": "End with 3+ quantifiable outcomes: percentage improvements, dollar savings, time reductions, and any recognition received."
        }
