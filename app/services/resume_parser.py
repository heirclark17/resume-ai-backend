from pathlib import Path
from typing import Dict, List
import json
import re
from docx import Document
import pdfplumber
import os
from openai import OpenAI

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

        # Initialize OpenAI API
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            self.client = OpenAI(api_key=self.openai_api_key)
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
        """Parse PDF resume using pdfplumber for better text extraction"""
        full_text = ''

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # Extract text with layout preserved
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + '\n'
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

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

        prompt = f"""You are a resume parser. Extract structured information from this resume and return ONLY a valid JSON object.

RESUME TEXT:
{resume_text}

INSTRUCTIONS:
1. **summary**: Extract the professional summary paragraph. This is typically the opening paragraph after the contact info that describes the candidate's background, experience, and expertise. Look for paragraphs with phrases like "years of experience", "proven ability", "background in", etc.

2. **skills**: Extract ALL skills from ANY section with keywords: "SKILLS", "CORE SKILLS", "TECHNICAL SKILLS", "TECHNOLOGIES", "COMPETENCIES", "EXPERTISE". Return as an array of individual skill strings (not full sentences).

3. **experience**: Extract ALL work experience entries in chronological order. For EACH job, extract:
   - title: The job title (e.g., "Cybersecurity Implementation Project Manager")
   - company: Company name (e.g., "T-Mobile")
   - location: City and state (e.g., "Houston, TX")
   - dates: Full date range (e.g., "2024 - May 2025")
   - bullets: ALL bullet points describing responsibilities and accomplishments

4. **education**: Extract degree, major, institution, and year as a single string

5. **certifications**: Extract ALL certifications and credentials as a single string (can include line breaks)

IMPORTANT:
- Extract the ACTUAL summary paragraph text, not job descriptions
- Include EVERY skill listed (programming languages, tools, frameworks, soft skills)
- Include EVERY work experience entry from most recent to oldest
- Include ALL bullet points for each job
- Return ONLY the JSON object, no markdown formatting, no explanation

{{
  "summary": "The professional summary paragraph text here",
  "skills": ["Skill 1", "Skill 2", "Skill 3"],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, State",
      "dates": "YYYY - YYYY",
      "bullets": ["First bullet point", "Second bullet point"]
    }}
  ],
  "education": "Degree, Major, Institution, Year",
  "certifications": "Certification 1\\nCertification 2"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=8000,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a resume parser that extracts structured information and returns only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.choices[0].message.content

            print(f"OpenAI GPT-4 Response (first 500 chars): {response_text[:500]}")

            # With response_format="json_object", OpenAI returns clean JSON
            try:
                parsed_data = json.loads(response_text)
            except json.JSONDecodeError as je:
                print(f"JSON decode error: {je}")
                print(f"Attempted to parse: {response_text[:1000]}")
                raise ValueError(f"Failed to parse JSON from OpenAI response: {str(je)}")

            # Validate required fields exist
            if not isinstance(parsed_data, dict):
                raise ValueError("Parsed data is not a dictionary")

            # Transform experience format to match expected structure
            experience_transformed = []
            for job in parsed_data.get('experience', []):
                experience_transformed.append({
                    'header': f"{job.get('title', '')} – {job.get('company', '')}",
                    'location': job.get('location', ''),
                    'dates': job.get('dates', ''),
                    'bullets': job.get('bullets', [])
                })

            result = {
                'summary': parsed_data.get('summary', ''),
                'skills': parsed_data.get('skills', []) if isinstance(parsed_data.get('skills'), list) else [],
                'experience': experience_transformed,
                'education': parsed_data.get('education', ''),
                'certifications': parsed_data.get('certifications', '')
            }

            print(f"Parsed resume successfully: {len(result['experience'])} jobs, {len(result['skills'])} skills")
            return result

        except Exception as e:
            print(f"Error parsing with AI: {e}")
            import traceback
            traceback.print_exc()
            raise
