"""
Data Extraction Service
Extracts structured data from CV text using regex and NLP
"""
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class DataExtractor:
    """Extract structured data from CV text"""

    # Email regex pattern
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Phone regex patterns (various formats)
    PHONE_PATTERNS = [
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',  # International
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Simple format
    ]

    # Social media URL patterns
    GITHUB_PATTERN = r'(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_-]+)'
    LINKEDIN_PATTERN = r'(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9_-]+)'
    TWITTER_PATTERN = r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)'
    PORTFOLIO_PATTERN = r'(?:https?://)?(?:www\.)?([A-Za-z0-9-]+\.[A-Za-z]{2,})(?:/[^\s]*)?'

    # Section headers
    WORK_SECTIONS = ['experience', 'work history', 'employment', 'work experience', 'professional experience']
    EDUCATION_SECTIONS = ['education', 'academic background', 'qualifications']
    SKILLS_SECTIONS = ['skills', 'technical skills', 'core competencies', 'technologies']
    CERT_SECTIONS = ['certifications', 'certificates', 'licenses']

    @staticmethod
    def extract_email(text: str) -> Tuple[Optional[str], float]:
        """
        Extract email address from text

        Args:
            text: CV text content

        Returns:
            Tuple[Optional[str], float]: (Email, confidence score)
        """
        matches = re.findall(DataExtractor.EMAIL_PATTERN, text, re.IGNORECASE)

        if not matches:
            return None, 0.0

        # Take the first email found (usually the primary one)
        email = matches[0].lower()

        # Calculate confidence based on email quality
        confidence = 85.0  # Base confidence for valid email

        # Boost confidence for professional domains
        professional_domains = ['gmail', 'outlook', 'yahoo', 'hotmail', 'icloud']
        domain = email.split('@')[1]
        if any(prof in domain for prof in professional_domains):
            confidence += 10.0

        # Reduce confidence if multiple emails found
        if len(matches) > 1:
            confidence -= 5.0

        return email, min(confidence, 99.0)

    @staticmethod
    def extract_phone(text: str) -> Tuple[Optional[str], float]:
        """
        Extract phone number from text

        Args:
            text: CV text content

        Returns:
            Tuple[Optional[str], float]: (Phone number, confidence score)
        """
        for pattern in DataExtractor.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                phone = matches[0]
                # Clean up the phone number
                phone = re.sub(r'[^\d+()-]', '', phone)

                # Calculate confidence based on format
                confidence = 75.0  # Base confidence

                if phone.startswith('+'):
                    confidence += 10.0  # International format is more reliable

                if len(phone) >= 10:
                    confidence += 10.0  # Full number

                return phone, min(confidence, 95.0)

        return None, 0.0

    @staticmethod
    def extract_social_links(text: str) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Extract social media links from text

        Args:
            text: CV text content

        Returns:
            Dict: Social media links with confidence scores
        """
        results = {}

        # Extract GitHub
        github_matches = re.findall(DataExtractor.GITHUB_PATTERN, text, re.IGNORECASE)
        if github_matches:
            username = github_matches[0]
            results['github'] = (f"https://github.com/{username}", 90.0)
        else:
            results['github'] = (None, 0.0)

        # Extract LinkedIn
        linkedin_matches = re.findall(DataExtractor.LINKEDIN_PATTERN, text, re.IGNORECASE)
        if linkedin_matches:
            username = linkedin_matches[0]
            results['linkedin'] = (f"https://linkedin.com/in/{username}", 90.0)
        else:
            results['linkedin'] = (None, 0.0)

        # Extract Twitter/X
        twitter_matches = re.findall(DataExtractor.TWITTER_PATTERN, text, re.IGNORECASE)
        if twitter_matches:
            username = twitter_matches[0]
            results['twitter'] = (f"https://twitter.com/{username}", 85.0)
        else:
            results['twitter'] = (None, 0.0)

        # Extract portfolio/personal website
        # Look for URLs that are not GitHub, LinkedIn, or Twitter
        all_urls = re.findall(DataExtractor.PORTFOLIO_PATTERN, text, re.IGNORECASE)
        portfolio_url = None
        for url in all_urls:
            if isinstance(url, tuple):
                url = url[0]
            if not any(site in url.lower() for site in ['github', 'linkedin', 'twitter', 'x.com', 'facebook']):
                portfolio_url = url if url.startswith('http') else f"https://{url}"
                break

        results['portfolio'] = (portfolio_url, 70.0 if portfolio_url else 0.0)

        return results

    @staticmethod
    def find_section(text: str, section_keywords: List[str]) -> Optional[str]:
        """
        Find and extract a section from CV text

        Args:
            text: CV text content
            section_keywords: List of possible section header names

        Returns:
            Optional[str]: Extracted section text
        """
        text_lower = text.lower()

        # Find the section start
        section_start = -1
        for keyword in section_keywords:
            pattern = rf'\n\s*{re.escape(keyword)}\s*[\n:]'
            match = re.search(pattern, text_lower)
            if match:
                section_start = match.start()
                break

        if section_start == -1:
            return None

        # Find the next section (next header in ALL CAPS or next known section)
        next_section_pattern = r'\n\s*[A-Z][A-Z\s]{3,}\s*[\n:]'
        remaining_text = text[section_start + 1:]
        next_match = re.search(next_section_pattern, remaining_text)

        if next_match:
            section_end = section_start + 1 + next_match.start()
            return text[section_start:section_end]
        else:
            # Take the rest of the document
            return text[section_start:]

    @staticmethod
    def extract_work_history(text: str) -> List[Dict[str, Any]]:
        """
        Extract work history from text

        Args:
            text: CV text content

        Returns:
            List[Dict]: List of work experiences
        """
        section = DataExtractor.find_section(text, DataExtractor.WORK_SECTIONS)
        if not section:
            return []

        experiences = []

        # Split by likely company entries (lines with dates)
        date_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|(?:19|20)\d{2}(?:\s*-\s*(?:Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|(?:19|20)\d{2}))?)'

        # Simple extraction - this would be improved with NLP
        lines = section.split('\n')
        current_exp = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line contains dates (likely start of experience)
            if re.search(date_pattern, line, re.IGNORECASE):
                if current_exp:
                    experiences.append(current_exp)
                current_exp = {
                    'company': 'Unknown',
                    'title': 'Unknown',
                    'dates': line,
                    'confidence': 70.0
                }
            elif current_exp:
                # Try to identify if it's a company or title
                if 'company' not in current_exp or current_exp['company'] == 'Unknown':
                    current_exp['company'] = line
                elif 'title' not in current_exp or current_exp['title'] == 'Unknown':
                    current_exp['title'] = line

        if current_exp:
            experiences.append(current_exp)

        return experiences[:5]  # Limit to 5 most recent

    @staticmethod
    def extract_education(text: str) -> List[Dict[str, Any]]:
        """
        Extract education from text

        Args:
            text: CV text content

        Returns:
            List[Dict]: List of education entries
        """
        section = DataExtractor.find_section(text, DataExtractor.EDUCATION_SECTIONS)
        if not section:
            return []

        education = []

        # Common degree patterns
        degree_patterns = [
            r'(Bachelor|B\.?S\.?|B\.?A\.?|Master|M\.?S\.?|M\.?A\.?|PhD|Ph\.?D\.?|MBA|MD)',
            r'(Associate|Diploma|Certificate)'
        ]

        lines = section.split('\n')
        current_edu = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for degree
            for pattern in degree_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    if current_edu:
                        education.append(current_edu)
                    current_edu = {
                        'degree': line,
                        'institution': '',
                        'year': '',
                        'confidence': 75.0
                    }
                    break

            # Check for year
            year_match = re.search(r'(19|20)\d{2}', line)
            if year_match and current_edu:
                current_edu['year'] = year_match.group(0)

            # If not a degree line, might be institution
            if current_edu and not re.search('|'.join(degree_patterns), line, re.IGNORECASE):
                if not current_edu['institution']:
                    current_edu['institution'] = line

        if current_edu:
            education.append(current_edu)

        return education[:3]  # Limit to 3 entries

    @staticmethod
    def extract_skills(text: str) -> List[Dict[str, Any]]:
        """
        Extract skills from text

        Args:
            text: CV text content

        Returns:
            List[Dict]: List of skills with confidence
        """
        section = DataExtractor.find_section(text, DataExtractor.SKILLS_SECTIONS)
        if not section:
            return []

        skills = []

        # Common skill keywords (this would be a much larger list in production)
        tech_skills = [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin',
            'react', 'angular', 'vue', 'node', 'django', 'flask', 'spring', 'express',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
            'machine learning', 'ai', 'deep learning', 'nlp', 'computer vision',
            'html', 'css', 'rest', 'api', 'microservices', 'agile', 'scrum'
        ]

        section_lower = section.lower()

        for skill in tech_skills:
            if skill in section_lower:
                skills.append({
                    'name': skill.title(),
                    'confidence': 85.0
                })

        # Also split by commas and extract
        lines = section.split('\n')
        for line in lines:
            if ',' in line:
                parts = line.split(',')
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 2 and part.lower() not in [s['name'].lower() for s in skills]:
                        skills.append({
                            'name': part,
                            'confidence': 75.0
                        })

        return skills[:20]  # Limit to 20 skills

    @staticmethod
    def calculate_overall_confidence(extracted_data: Dict[str, Any]) -> float:
        """
        Calculate overall extraction confidence

        Args:
            extracted_data: Dictionary of extracted data with confidence scores

        Returns:
            float: Overall confidence score (0-100)
        """
        confidences = []

        # Collect all confidence scores
        if extracted_data.get('email_confidence'):
            confidences.append(extracted_data['email_confidence'])

        if extracted_data.get('phone_confidence'):
            confidences.append(extracted_data['phone_confidence'])

        if extracted_data.get('github_url_confidence'):
            confidences.append(extracted_data['github_url_confidence'])

        if extracted_data.get('linkedin_url_confidence'):
            confidences.append(extracted_data['linkedin_url_confidence'])

        # Add work history and education confidence
        if extracted_data.get('work_history'):
            confidences.extend([w.get('confidence', 0) for w in extracted_data['work_history']])

        if extracted_data.get('education'):
            confidences.extend([e.get('confidence', 0) for e in extracted_data['education']])

        if not confidences:
            return 0.0

        # Calculate weighted average
        return round(sum(confidences) / len(confidences), 2)
