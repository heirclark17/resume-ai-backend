from pathlib import Path
from typing import Dict, List
import json
import re
from docx import Document
import PyPDF2
import os
from anthropic import Anthropic

class ResumeParser:
    """Parse DOCX and PDF resumes into structured data using Claude AI"""

    def __init__(self):
        self.sections = {
            'summary': ['summary', 'professional summary', 'profile', 'objective', 'about'],
            'skills': ['skills', 'technical skills', 'core competencies', 'expertise', 'technologies'],
            'experience': ['experience', 'work experience', 'professional experience', 'employment', 'work history'],
            'education': ['education', 'academic background', 'qualifications'],
            'certifications': ['certifications', 'certificates', 'licenses', 'credentials']
        }

        # Initialize Claude API
        self.claude_api_key = os.getenv('CLAUDE_API_KEY')
        if self.claude_api_key:
            self.client = Anthropic(api_key=self.claude_api_key)
            self.use_ai_parsing = True
        else:
            self.use_ai_parsing = False

    def parse_file(self, file_path: str) -> Dict:
        """
        Parse resume file (DOCX or PDF)

        Returns:
            {
                'summary': str,
                'skills': List[str],
                'experience': List[dict],
                'education': str,
                'certifications': str
            }
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.docx':
            return self.parse_docx(file_path)
        elif file_ext == '.pdf':
            return self.parse_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

    def parse_docx(self, file_path: str) -> Dict:
        """Parse DOCX resume"""
        doc = Document(file_path)

        # Extract all text with paragraph breaks
        full_text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

        # Use AI parsing if available
        if self.use_ai_parsing:
            try:
                return self._parse_with_ai(full_text)
            except Exception as e:
                print(f"AI parsing failed, falling back to regex: {e}")
                return self._extract_sections(full_text)
        else:
            return self._extract_sections(full_text)

    def parse_pdf(self, file_path: str) -> Dict:
        """Parse PDF resume"""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)

            # Extract text from all pages
            full_text = ''
            for page in reader.pages:
                full_text += page.extract_text() + '\n'

        # Use AI parsing if available
        if self.use_ai_parsing:
            try:
                return self._parse_with_ai(full_text)
            except Exception as e:
                print(f"AI parsing failed, falling back to regex: {e}")
                return self._extract_sections(full_text)
        else:
            return self._extract_sections(full_text)

    def _extract_sections(self, text: str) -> Dict:
        """Extract sections from resume text"""
        result = {
            'summary': '',
            'skills': [],
            'experience': [],
            'education': '',
            'certifications': ''
        }

        # Split into lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        current_section = None
        section_content = []

        for line in lines:
            # Check if line is a section header
            line_lower = line.lower()
            detected_section = None

            for section_key, keywords in self.sections.items():
                if any(keyword in line_lower for keyword in keywords):
                    # Make sure it's a header (short line, often ends with colon)
                    if len(line) < 50 or ':' in line:
                        detected_section = section_key
                        break

            if detected_section:
                # Save previous section
                if current_section and section_content:
                    result[current_section] = self._process_section(current_section, section_content)

                # Start new section
                current_section = detected_section
                section_content = []
            else:
                # Add to current section
                if current_section:
                    section_content.append(line)

        # Save last section
        if current_section and section_content:
            result[current_section] = self._process_section(current_section, section_content)

        return result

    def _process_section(self, section_name: str, content: List[str]) -> any:
        """Process section content based on type"""

        if section_name == 'skills':
            # Extract skills (usually comma-separated or bulleted)
            skills = []
            for line in content:
                # Remove bullets
                line = re.sub(r'^[•\-\*]\s*', '', line)
                # Split by commas, semicolons, or pipes
                parts = re.split(r'[,;|]', line)
                skills.extend([s.strip() for s in parts if s.strip() and len(s.strip()) > 2])

            # Remove duplicates while preserving order
            seen = set()
            unique_skills = []
            for skill in skills:
                if skill.lower() not in seen:
                    seen.add(skill.lower())
                    unique_skills.append(skill)

            return unique_skills

        elif section_name == 'experience':
            # Parse job entries
            jobs = []
            current_job = None

            for line in content:
                # Check if line looks like a job title or company
                if self._is_job_header(line):
                    if current_job:
                        jobs.append(current_job)
                    current_job = {'header': line, 'bullets': []}
                elif current_job:
                    # Remove bullet characters
                    bullet = re.sub(r'^[•\-\*]\s*', '', line)
                    if bullet and len(bullet) > 10:  # Ignore very short lines
                        current_job['bullets'].append(bullet)

            if current_job:
                jobs.append(current_job)

            return jobs

        else:
            # For summary, education, certifications: return as text
            return '\n'.join(content)

    def _is_job_header(self, line: str) -> bool:
        """Detect if line is a job title/company header"""
        # Job headers usually have dates (2020-2024, Jan 2020, etc.)
        date_patterns = [
            r'\d{4}\s*[-–]\s*\d{4}',
            r'\d{4}\s*[-–]\s*Present',
            r'\d{4}\s*[-–]\s*Current',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
        ]
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in date_patterns)

    def _parse_with_ai(self, resume_text: str) -> Dict:
        """Parse resume using Claude AI for better accuracy"""

        prompt = f"""Extract structured information from this resume and return it as valid JSON.

Resume Text:
{resume_text}

Extract the following sections:
1. **summary**: The professional summary or objective statement (even if not explicitly labeled as "summary")
2. **skills**: List of technical skills and competencies (as array of strings)
3. **experience**: Work experience entries as array of objects with:
   - title: Job title
   - company: Company name
   - location: Location (city, state)
   - dates: Date range
   - bullets: Array of bullet points describing responsibilities and accomplishments
4. **education**: Education details as string
5. **certifications**: Certifications and credentials as string

Requirements:
- For summary: Extract the opening paragraph that describes professional background (may be under a title like "CYBERSECURITY PROGRAM & PROJECT MANAGER" or similar)
- For experience: Extract ALL work experience entries, including job title, company, location, date range, and all bullet points
- For skills: Combine skills from sections like "CORE SKILLS", "TECHNOLOGIES", "TECHNICAL SKILLS" etc.
- Return ONLY valid JSON, no other text

Return JSON in this exact format:
{{
  "summary": "string",
  "skills": ["skill1", "skill2", ...],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, State",
      "dates": "YYYY - YYYY",
      "bullets": ["bullet 1", "bullet 2", ...]
    }}
  ],
  "education": "string",
  "certifications": "string"
}}"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text

            # Extract JSON from response (Claude might wrap it in markdown)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group(0))
            else:
                parsed_data = json.loads(response_text)

            # Transform experience format to match expected structure
            experience_transformed = []
            for job in parsed_data.get('experience', []):
                experience_transformed.append({
                    'header': f"{job.get('title', '')} – {job.get('company', '')}",
                    'location': job.get('location', ''),
                    'dates': job.get('dates', ''),
                    'bullets': job.get('bullets', [])
                })

            return {
                'summary': parsed_data.get('summary', ''),
                'skills': parsed_data.get('skills', []),
                'experience': experience_transformed,
                'education': parsed_data.get('education', ''),
                'certifications': parsed_data.get('certifications', '')
            }

        except Exception as e:
            print(f"Error parsing with AI: {e}")
            raise
