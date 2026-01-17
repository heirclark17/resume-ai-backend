from pathlib import Path
from typing import Dict, List
import json
import re
from docx import Document
import pdfplumber
import os
from openai import OpenAI
from app.utils.file_encryption import FileEncryption
import io

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

        # Initialize encryption for secure file handling
        self.encryption = FileEncryption()

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
        # Decrypt file before parsing (files encrypted at rest for security)
        decrypted_bytes = self.encryption.decrypt_file(file_path)

        # Parse from decrypted bytes
        doc = Document(io.BytesIO(decrypted_bytes))

        # Extract all text with paragraph breaks
        full_text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

        print(f"[DOCX Parser] Extracted {len(full_text)} characters from DOCX")

        # Use AI parsing if available
        if self.use_ai_parsing:
            try:
                print(f"[DOCX Parser] Attempting AI parsing with OpenAI GPT-4.1-mini...")
                result = self._parse_with_ai(full_text)
                result['parsing_method'] = 'ai'
                result['parsing_warnings'] = []
                print(f"[DOCX Parser] AI parsing SUCCESS - Summary length: {len(result.get('summary', ''))}, Skills: {len(result.get('skills', []))}, Jobs: {len(result.get('experience', []))}")
                return result
            except Exception as e:
                print(f"[DOCX Parser] WARNING:  AI parsing FAILED, falling back to regex: {e}")
                import traceback
                traceback.print_exc()
                result = self._extract_sections(full_text)
                result['parsing_method'] = 'regex_fallback'
                result['parsing_warnings'] = [
                    f"AI parsing failed: {str(e)[:200]}",
                    "Using basic text extraction instead - results may be less accurate",
                    "Please verify all extracted information carefully"
                ]
                return result
        else:
            print(f"[DOCX Parser] AI parsing disabled (no OPENAI_API_KEY), using regex")
            result = self._extract_sections(full_text)
            result['parsing_method'] = 'regex'
            result['parsing_warnings'] = [
                "AI parsing is not enabled (missing OPENAI_API_KEY)",
                "Using basic text extraction - results may be less accurate"
            ]
            return result

    def parse_pdf(self, file_path: str) -> Dict:
        """Parse PDF resume using pdfplumber for better text extraction"""
        # Decrypt file before parsing (files encrypted at rest for security)
        decrypted_bytes = self.encryption.decrypt_file(file_path)

        full_text = ''

        try:
            # Parse from decrypted bytes
            with pdfplumber.open(io.BytesIO(decrypted_bytes)) as pdf:
                for page in pdf.pages:
                    # Extract text with layout preserved
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + '\n'
        except Exception as e:
            print(f"[PDF Parser] Error extracting PDF text: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

        print(f"[PDF Parser] Extracted {len(full_text)} characters from PDF")

        # Use AI parsing if available
        if self.use_ai_parsing:
            try:
                print(f"[PDF Parser] Attempting AI parsing with OpenAI GPT-4.1-mini...")
                result = self._parse_with_ai(full_text)
                result['parsing_method'] = 'ai'
                result['parsing_warnings'] = []
                print(f"[PDF Parser] AI parsing SUCCESS - Summary length: {len(result.get('summary', ''))}, Skills: {len(result.get('skills', []))}, Jobs: {len(result.get('experience', []))}")
                return result
            except Exception as e:
                print(f"[PDF Parser] WARNING:  AI parsing FAILED, falling back to regex: {e}")
                import traceback
                traceback.print_exc()
                result = self._extract_sections(full_text)
                result['parsing_method'] = 'regex_fallback'
                result['parsing_warnings'] = [
                    f"AI parsing failed: {str(e)[:200]}",
                    "Using basic text extraction instead - results may be less accurate",
                    "Please verify all extracted information carefully"
                ]
                return result
        else:
            print(f"[PDF Parser] AI parsing disabled (no OPENAI_API_KEY), using regex")
            result = self._extract_sections(full_text)
            result['parsing_method'] = 'regex'
            result['parsing_warnings'] = [
                "AI parsing is not enabled (missing OPENAI_API_KEY)",
                "Using basic text extraction - results may be less accurate"
            ]
            return result

    def _extract_sections(self, text: str) -> Dict:
        """Extract sections from resume text"""
        result = {
            'candidate_name': '',
            'candidate_email': '',
            'candidate_phone': '',
            'candidate_location': '',
            'candidate_linkedin': '',
            'summary': '',
            'skills': [],
            'experience': [],
            'education': '',
            'certifications': ''
        }

        # Try to extract contact info from first few lines
        lines = text.split('\n')[:10]  # Check first 10 lines for contact info
        for line in lines:
            line = line.strip()

            # Extract email
            if not result['candidate_email']:
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                if email_match:
                    result['candidate_email'] = email_match.group()

            # Extract phone
            if not result['candidate_phone']:
                phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', line)
                if phone_match:
                    result['candidate_phone'] = phone_match.group()

            # Extract LinkedIn
            if not result['candidate_linkedin']:
                if 'linkedin.com' in line.lower():
                    result['candidate_linkedin'] = line

        # Extract name from first line (usually the candidate's name)
        if lines and len(lines[0].strip()) > 0 and len(lines[0].strip()) < 50:
            potential_name = lines[0].strip()
            # Check if it looks like a name (not email, not phone, not URL)
            if '@' not in potential_name and 'http' not in potential_name.lower() and not re.search(r'\d{3}[-.\s]?\d{3}', potential_name):
                result['candidate_name'] = potential_name

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
1. **candidate_name**: Extract the candidate's full name (usually at the top of the resume)

2. **candidate_email**: Extract the email address

3. **candidate_phone**: Extract the phone number

4. **candidate_location**: Extract the city/state location (e.g., "Houston, TX")

5. **candidate_linkedin**: Extract LinkedIn URL or profile handle if present

6. **summary**: Extract the professional summary paragraph. This is typically the opening paragraph after the contact info that describes the candidate's background, experience, and expertise. Look for paragraphs with phrases like "years of experience", "proven ability", "background in", etc.

7. **skills**: Extract ALL skills from ANY section with keywords: "SKILLS", "CORE SKILLS", "TECHNICAL SKILLS", "TECHNOLOGIES", "COMPETENCIES", "EXPERTISE". Return as an array of individual skill strings (not full sentences).

8. **experience**: Extract ALL work experience entries in chronological order. For EACH job, extract:
   - title: The job title (e.g., "Cybersecurity Implementation Project Manager")
   - company: Company name (e.g., "T-Mobile")
   - location: City and state (e.g., "Houston, TX")
   - dates: Full date range (e.g., "2024 - May 2025")
   - bullets: ALL bullet points describing responsibilities and accomplishments

9. **education**: Extract degree, major, institution, and year as a single string

10. **certifications**: Extract ALL certifications and credentials as a single string (can include line breaks)

IMPORTANT:
- Extract the ACTUAL summary paragraph text, not job descriptions
- Include EVERY skill listed (programming languages, tools, frameworks, soft skills)
- Include EVERY work experience entry from most recent to oldest
- Include ALL bullet points for each job
- If a field is not found, use empty string or empty array
- Return ONLY the JSON object, no markdown formatting, no explanation

{{
  "candidate_name": "Full Name",
  "candidate_email": "email@example.com",
  "candidate_phone": "(555) 123-4567",
  "candidate_location": "City, State",
  "candidate_linkedin": "linkedin.com/in/username",
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
                model="gpt-4.1-mini",  # Latest 2026 model - outperforms gpt-4o-mini, optimized for structured extraction
                max_tokens=8000,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a resume parser that extracts structured information and returns only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.choices[0].message.content

            print(f"OpenAI GPT-4.1-mini Response (first 500 chars): {response_text[:500]}")

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
                # Format header with comma instead of en-dash for better compatibility
                title = job.get('title', '')
                company = job.get('company', '')
                if title and company:
                    header = f"{title}, {company}"
                else:
                    header = title or company or ''

                experience_transformed.append({
                    'header': header,
                    'location': job.get('location', ''),
                    'dates': job.get('dates', ''),
                    'bullets': job.get('bullets', [])
                })

            result = {
                'candidate_name': parsed_data.get('candidate_name', ''),
                'candidate_email': parsed_data.get('candidate_email', ''),
                'candidate_phone': parsed_data.get('candidate_phone', ''),
                'candidate_location': parsed_data.get('candidate_location', ''),
                'candidate_linkedin': parsed_data.get('candidate_linkedin', ''),
                'summary': parsed_data.get('summary', ''),
                'skills': parsed_data.get('skills', []) if isinstance(parsed_data.get('skills'), list) else [],
                'experience': experience_transformed,
                'education': parsed_data.get('education', ''),
                'certifications': parsed_data.get('certifications', '')
            }

            print(f"Parsed resume successfully: {len(result['experience'])} jobs, {len(result['skills'])} skills, candidate: {result.get('candidate_name', 'N/A')}")
            return result

        except Exception as e:
            print(f"Error parsing with AI: {e}")
            import traceback
            traceback.print_exc()
            raise
