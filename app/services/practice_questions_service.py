"""
Service for generating job-specific practice questions and AI-generated STAR stories
"""
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PracticeQuestionsService:
    """Generate job-specific practice questions and STAR stories"""

    def generate_job_specific_questions(
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
            response = client.chat.completions.create(
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

    def generate_star_story(
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

        prompt = f"""You are an expert interview coach. Generate a compelling STAR story to answer this interview question.

INTERVIEW QUESTION:
{question}

CANDIDATE'S BACKGROUND:
{candidate_background}

JOB APPLYING FOR:
{job_title}

JOB DESCRIPTION:
{job_description}

Generate a STAR story that:
1. SITUATION: Sets the context (specific, relatable scenario from candidate's background)
2. TASK: Defines the challenge or goal (aligned with job requirements)
3. ACTION: Details specific steps taken (demonstrates required skills)
4. RESULT: Quantifies the outcome (measurable impact with numbers/percentages)

REQUIREMENTS:
- Use first-person perspective ("I...")
- Make it specific and detailed, not generic
- Include measurable outcomes (percentages, numbers, timeframes)
- Align with the job's core responsibilities
- Keep each section 2-3 sentences max
- Sound natural and conversational

Return ONLY a valid JSON object with keys: situation, task, action, result. No markdown, no additional text.

Example format:
{{
  "situation": "When I joined the cybersecurity team at my previous company, we were facing a 45% increase in phishing attacks targeting employees, and our current training program had only 60% completion rates.",
  "task": "I was tasked with redesigning our security awareness program to increase engagement and reduce successful phishing attempts by at least 30% within six months.",
  "action": "I implemented a gamified training platform with monthly simulated phishing campaigns, created role-specific micro-learning modules, and established a security champions program across all departments. I also built a real-time dashboard to track metrics and identify high-risk teams.",
  "result": "Within 4 months, we reduced successful phishing click rates from 18% to 4%, achieved 95% training completion, and our security champions program expanded to 50 employees. The CISO presented our program as a model to the board, and we received budget approval to expand it company-wide."
}}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert interview coach who creates compelling STAR stories. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
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
            "situation": "I noticed our team was struggling with [specific challenge] which was impacting [key metric].",
            "task": "I was responsible for [specific goal or objective] to improve [outcome].",
            "action": "I took the following steps: [specific action 1], [specific action 2], and [specific action 3].",
            "result": "As a result, we achieved [quantifiable outcome with numbers/percentages] within [timeframe]."
        }
