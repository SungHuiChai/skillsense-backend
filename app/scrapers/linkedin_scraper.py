"""
LinkedIn scraper for collecting profile data using web search.
Note: Direct LinkedIn API access is restricted, so we use Tavily web search
to collect publicly available profile information.
"""

from typing import Dict, Any, Optional, List
import re
import httpx
from app.scrapers.base_scraper import BaseScraper
from app.search.tavily_search import TavilySearch
import logging

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scrape LinkedIn profiles using web search (Tavily)"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LinkedIn scraper.

        Args:
            config: Configuration dictionary with tavily_api_key and rate limiting settings
        """
        super().__init__(config)
        self.tavily_api_key = config.get('tavily_api_key')

        if self.tavily_api_key:
            try:
                self.tavily_search = TavilySearch({
                    'tavily_api_key': self.tavily_api_key,
                    'search_depth': 'advanced',
                    'max_results': 5
                })
                logger.info("LinkedIn scraper initialized with Tavily search")
            except Exception as e:
                logger.warning(f"LinkedIn scraper Tavily initialization failed: {e}")
                self.tavily_search = None
        else:
            logger.warning("LinkedIn scraper initialized without Tavily API key")
            self.tavily_search = None

    def validate_url(self, url: str) -> bool:
        """
        Validate LinkedIn URL.

        Args:
            url: LinkedIn profile URL

        Returns:
            True if valid LinkedIn URL, False otherwise
        """
        pattern = r'linkedin\.com/in/[a-zA-Z0-9-]+'
        return bool(re.search(pattern, url))

    def _extract_username(self, url: str) -> Optional[str]:
        """
        Extract username from LinkedIn URL.

        Args:
            url: LinkedIn profile URL

        Returns:
            Username string or None if invalid
        """
        match = re.search(r'linkedin\.com/in/([a-zA-Z0-9-]+)', url)
        return match.group(1) if match else None

    async def scrape(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn profile data using web search.

        Args:
            url: LinkedIn profile URL
            **kwargs: Additional parameters (full_name for better search)

        Returns:
            Dictionary with LinkedIn profile data

        Raises:
            ValueError: If URL is invalid or search fails
            Exception: For API errors
        """
        await self._rate_limit()

        username = self._extract_username(url)
        if not username:
            raise ValueError(f"Invalid LinkedIn URL: {url}")

        full_name = kwargs.get('full_name', '')
        logger.info(f"Collecting LinkedIn data for: {username} ({full_name})")

        if not self.tavily_search:
            logger.warning("Tavily search not available, returning minimal data")
            return {
                "profile_url": url,
                "username": username,
                "full_name": full_name,
                "headline": None,
                "summary": None,
                "experience": [],
                "skills": [],
                "education": [],
                "recommendations": [],
                "certifications": [],
                "data_source": "url_only",
                "collection_method": "tavily_unavailable"
            }

        try:
            # Search for LinkedIn profile content using Tavily
            search_query = f"{full_name} LinkedIn {url}" if full_name else f"LinkedIn {url}"

            results = await self.tavily_search.search(
                query=search_query,
                include_domains=['linkedin.com']
            )

            # Extract profile data from search results
            profile_data = self._process_search_results(results, url, full_name)

            logger.info(f"Successfully collected LinkedIn data for: {username}")
            return profile_data

        except Exception as e:
            logger.error(f"Error scraping LinkedIn profile {username}: {e}")
            # Return minimal data with error
            return {
                "profile_url": url,
                "username": username,
                "full_name": full_name,
                "headline": None,
                "summary": None,
                "experience": [],
                "skills": [],
                "education": [],
                "recommendations": [],
                "certifications": [],
                "data_source": "search_failed",
                "collection_method": "tavily_error",
                "error_message": str(e)
            }

    def _process_search_results(
        self,
        results: List[Dict[str, Any]],
        url: str,
        full_name: str
    ) -> Dict[str, Any]:
        """
        Process Tavily search results to extract profile data.

        Args:
            results: Tavily search results
            url: LinkedIn profile URL
            full_name: Person's full name

        Returns:
            Dictionary with extracted profile data
        """
        username = self._extract_username(url)

        # Initialize profile structure
        profile_data = {
            "profile_url": url,
            "username": username,
            "full_name": full_name,
            "headline": None,
            "summary": None,
            "experience": [],
            "skills": [],
            "education": [],
            "recommendations": [],
            "certifications": [],
            "data_source": "tavily_search",
            "collection_method": "web_search",
            "raw_search_results": results[:3]  # Keep top 3 for context
        }

        if not results:
            return profile_data

        # Extract information from search result content
        for result in results:
            content = result.get('content', '').lower()
            raw_content = result.get('raw_content', '')

            # Try to extract headline/title (often appears in search result titles)
            if not profile_data['headline'] and result.get('title'):
                # LinkedIn titles often include role/company
                title = result.get('title', '')
                if '|' in title:
                    parts = title.split('|')
                    profile_data['headline'] = parts[0].strip()
                elif '-' in title:
                    parts = title.split('-')
                    profile_data['headline'] = parts[0].strip()

            # Extract summary from content preview
            if not profile_data['summary'] and len(content) > 100:
                # Use first substantial paragraph as summary
                profile_data['summary'] = result.get('content', '')[:500]

            # Look for skill mentions (simple keyword extraction)
            skill_keywords = self._extract_skill_keywords(content + ' ' + raw_content)
            profile_data['skills'].extend(skill_keywords)

            # Look for experience indicators (job titles, companies)
            experience_mentions = self._extract_experience_mentions(content)
            profile_data['experience'].extend(experience_mentions)

        # Deduplicate skills
        profile_data['skills'] = list(set(profile_data['skills']))[:20]  # Limit to top 20

        logger.debug(f"Extracted {len(profile_data['skills'])} skills from LinkedIn search")

        return profile_data

    def _extract_skill_keywords(self, text: str) -> List[str]:
        """
        Extract likely skill keywords from text.

        Args:
            text: Text content from search results

        Returns:
            List of skill keywords
        """
        # Common technical skills to look for
        technical_skills = [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go', 'rust', 'php',
            'react', 'vue', 'angular', 'node', 'django', 'flask', 'spring', 'laravel',
            'machine learning', 'ai', 'data science', 'nlp', 'computer vision',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
            'sql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'git', 'ci/cd', 'agile', 'scrum', 'devops'
        ]

        found_skills = []
        text_lower = text.lower()

        for skill in technical_skills:
            if skill in text_lower:
                found_skills.append(skill.title())

        return found_skills

    def _extract_experience_mentions(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract experience/job mentions from text.

        Args:
            text: Text content from search results

        Returns:
            List of experience dictionaries
        """
        experience = []

        # Look for common job title patterns
        job_title_patterns = [
            r'(software engineer|developer|architect|manager|lead|director|analyst|scientist)',
            r'(senior|junior|principal|staff|head of)',
        ]

        # Look for company mentions (very basic)
        # In real implementation, you might use NER or more sophisticated parsing

        # For now, just indicate that experience data exists
        if any(re.search(pattern, text.lower()) for pattern in job_title_patterns):
            experience.append({
                "title": "Mentioned in profile",
                "company": "See LinkedIn profile",
                "description": "Experience details available on LinkedIn",
                "source": "search_result"
            })

        return experience

    def extract_skills(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract skills from LinkedIn data.

        Args:
            data: Scraped LinkedIn data

        Returns:
            List of skill dictionaries with name, category, evidence, confidence
        """
        skills = []

        # Extract from skills list
        for skill_name in data.get("skills", []):
            skills.append({
                "name": skill_name,
                "category": "linkedin_skill",
                "evidence": f"Listed on LinkedIn profile",
                "confidence": 70  # Medium confidence from web search
            })

        # Extract from experience
        for exp in data.get("experience", []):
            if exp.get("title"):
                skills.append({
                    "name": exp["title"],
                    "category": "job_role",
                    "evidence": f"Experience at {exp.get('company', 'company')}",
                    "confidence": 65
                })

        logger.info(f"Extracted {len(skills)} skills from LinkedIn data")
        return skills
