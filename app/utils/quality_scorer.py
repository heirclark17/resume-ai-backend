from typing import Dict, List
import json


class QualityScorer:
    """Calculate quality score for tailored resumes"""

    @staticmethod
    def calculate_quality_score(
        base_resume_data: Dict,
        tailored_content: Dict,
        company_research: Dict = None
    ) -> float:
        """
        Calculate quality score (0-100) for tailored resume

        Args:
            base_resume_data: Original resume data
            tailored_content: Tailored resume content from Claude
            company_research: Optional company research data

        Returns:
            float: Quality score between 0-100
        """
        score = 0.0
        max_score = 100.0

        # 1. Content Completeness (30 points)
        completeness_score = QualityScorer._score_completeness(tailored_content)
        score += completeness_score * 0.3

        # 2. Customization Depth (25 points)
        customization_score = QualityScorer._score_customization(
            base_resume_data,
            tailored_content
        )
        score += customization_score * 0.25

        # 3. Skills Matching (20 points)
        skills_score = QualityScorer._score_skills(
            base_resume_data,
            tailored_content
        )
        score += skills_score * 0.20

        # 4. Experience Relevance (15 points)
        experience_score = QualityScorer._score_experience(tailored_content)
        score += experience_score * 0.15

        # 5. Company Alignment (10 points)
        alignment_score = QualityScorer._score_alignment(
            tailored_content,
            company_research
        )
        score += alignment_score * 0.10

        return min(max_score, max(0.0, score))

    @staticmethod
    def _score_completeness(tailored_content: Dict) -> float:
        """Score based on presence of required sections (0-100)"""
        score = 0.0
        required_sections = {
            'summary': 30,
            'competencies': 25,
            'experience': 25,
            'alignment_statement': 20
        }

        for section, weight in required_sections.items():
            content = tailored_content.get(section)
            if content:
                if isinstance(content, str):
                    # String content - check length
                    if len(content.strip()) > 50:
                        score += weight
                    elif len(content.strip()) > 10:
                        score += weight * 0.5
                elif isinstance(content, list):
                    # List content - check count
                    if len(content) >= 5:
                        score += weight
                    elif len(content) > 0:
                        score += weight * (len(content) / 5)

        return score

    @staticmethod
    def _score_customization(base_resume_data: Dict, tailored_content: Dict) -> float:
        """Score based on customization depth (0-100)"""
        score = 0.0

        # Check if summary was customized
        base_summary = base_resume_data.get('summary', '')
        tailored_summary = tailored_content.get('summary', '')

        if tailored_summary and tailored_summary != base_summary:
            # Summary was customized
            if len(tailored_summary) > len(base_summary) * 0.8:
                score += 40  # Good length
            else:
                score += 20  # Too short

        # Check if experience was reframed
        base_exp = base_resume_data.get('experience', [])
        tailored_exp = tailored_content.get('experience', [])

        if tailored_exp:
            score += 30  # Experience section exists

        # Check if competencies were added/modified
        base_skills = base_resume_data.get('skills', [])
        tailored_competencies = tailored_content.get('competencies', [])

        if len(tailored_competencies) >= 8:
            score += 30  # Good number of competencies
        elif len(tailored_competencies) > 0:
            score += 15  # Some competencies

        return score

    @staticmethod
    def _score_skills(base_resume_data: Dict, tailored_content: Dict) -> float:
        """Score based on skills/competencies (0-100)"""
        score = 0.0

        base_skills = base_resume_data.get('skills', [])
        tailored_competencies = tailored_content.get('competencies', [])

        if not tailored_competencies:
            return 0.0

        # Score based on number of competencies
        if len(tailored_competencies) >= 12:
            score += 50
        elif len(tailored_competencies) >= 8:
            score += 35
        elif len(tailored_competencies) >= 5:
            score += 20
        else:
            score += 10

        # Score based on variety (not just copying base skills)
        if base_skills:
            base_skills_lower = [s.lower() for s in base_skills]
            tailored_comp_lower = [c.lower() for c in tailored_competencies]

            unique_competencies = sum(
                1 for comp in tailored_comp_lower
                if comp not in base_skills_lower
            )

            if unique_competencies >= 5:
                score += 50
            elif unique_competencies >= 3:
                score += 30
            elif unique_competencies > 0:
                score += 15

        return score

    @staticmethod
    def _score_experience(tailored_content: Dict) -> float:
        """Score based on experience section quality (0-100)"""
        score = 0.0

        experience = tailored_content.get('experience', [])

        if not experience:
            return 0.0

        # Score based on number of jobs
        num_jobs = len(experience)
        if num_jobs >= 3:
            score += 40
        elif num_jobs >= 2:
            score += 30
        elif num_jobs >= 1:
            score += 20

        # Score based on bullet point quality
        total_bullets = 0
        for job in experience:
            if isinstance(job, dict):
                bullets = job.get('bullets', [])
                total_bullets += len(bullets)

        if total_bullets >= 15:
            score += 60
        elif total_bullets >= 10:
            score += 45
        elif total_bullets >= 5:
            score += 30
        elif total_bullets > 0:
            score += 15

        return score

    @staticmethod
    def _score_alignment(tailored_content: Dict, company_research: Dict = None) -> float:
        """Score based on company alignment (0-100)"""
        score = 0.0

        # Check alignment statement
        alignment_statement = tailored_content.get('alignment_statement', '')

        if alignment_statement:
            if len(alignment_statement) > 200:
                score += 60  # Detailed alignment statement
            elif len(alignment_statement) > 50:
                score += 40  # Basic alignment statement
            else:
                score += 20  # Short statement

        # If company research was provided, check for company-specific keywords
        if company_research and isinstance(company_research, dict):
            research_text = company_research.get('research', '').lower()

            # Check if summary mentions company-specific terms
            summary = tailored_content.get('summary', '').lower()

            # Simple keyword matching (could be more sophisticated)
            company_keywords_found = 0
            common_keywords = ['mission', 'values', 'initiative', 'culture', 'vision']

            for keyword in common_keywords:
                if keyword in research_text and keyword in summary:
                    company_keywords_found += 1

            if company_keywords_found >= 2:
                score += 40
            elif company_keywords_found > 0:
                score += 20

        return score
