"""
GitHub scraper for collecting profile and repository data.
"""

from typing import Dict, Any, Optional, List
import re
import httpx
from app.scrapers.base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class GitHubScraper(BaseScraper):
    """Scrape GitHub profiles and repositories using GitHub API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GitHub scraper.

        Args:
            config: Configuration dictionary with github_token and rate limiting settings
        """
        super().__init__(config)
        self.api_token = config.get('github_token')
        self.api_base = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SkillSense-DataCollector/1.0"
        }
        if self.api_token:
            self.headers["Authorization"] = f"token {self.api_token}"
            logger.info("GitHub scraper initialized with authentication")
        else:
            logger.warning(
                "GitHub scraper initialized without token. "
                "Rate limits will be more restrictive (60 requests/hour)"
            )

    def validate_url(self, url: str) -> bool:
        """
        Validate GitHub URL.

        Args:
            url: GitHub profile URL

        Returns:
            True if valid GitHub URL, False otherwise
        """
        pattern = r'github\.com/([a-zA-Z0-9-]+)/?$'
        return bool(re.search(pattern, url))

    def _extract_username(self, url: str) -> Optional[str]:
        """
        Extract username from GitHub URL.

        Args:
            url: GitHub profile URL

        Returns:
            Username string or None if invalid
        """
        match = re.search(r'github\.com/([a-zA-Z0-9-]+)/?$', url)
        return match.group(1) if match else None

    async def scrape(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Scrape GitHub profile data.

        Args:
            url: GitHub profile URL
            **kwargs: Additional parameters

        Returns:
            Dictionary with GitHub profile data

        Raises:
            ValueError: If URL is invalid or user not found
            Exception: For API errors
        """
        await self._rate_limit()

        username = self._extract_username(url)
        if not username:
            raise ValueError(f"Invalid GitHub URL: {url}")

        logger.info(f"Scraping GitHub profile: {username}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Get user profile
                user_data = await self._get_user_profile(client, username)

                # Get repositories
                repos_data = await self._get_repositories(client, username)

                # Process repository data
                languages = self._extract_language_stats(repos_data)
                technologies = self._extract_technologies(repos_data)
                frameworks = self._extract_frameworks(repos_data)
                top_repos = self._get_top_repos(repos_data, limit=5)

                result = {
                    "username": user_data.get("login"),
                    "name": user_data.get("name"),
                    "bio": user_data.get("bio"),
                    "location": user_data.get("location"),
                    "company": user_data.get("company"),
                    "blog": user_data.get("blog"),
                    "email": user_data.get("email"),
                    "public_repos": user_data.get("public_repos"),
                    "public_gists": user_data.get("public_gists"),
                    "followers": user_data.get("followers"),
                    "following": user_data.get("following"),
                    "repositories": self._process_repositories(repos_data),
                    "languages": languages,
                    "top_repos": top_repos,
                    "contributions_last_year": None,  # Requires GraphQL API
                    "commit_activity": {},
                    "technologies": technologies,
                    "frameworks": frameworks,
                    "raw_data": {
                        "user": user_data,
                        "repos": repos_data[:10]  # Limit to save space
                    }
                }

                logger.info(
                    f"Successfully scraped GitHub profile: {username} "
                    f"({len(repos_data)} repos, {len(languages)} languages)"
                )

                return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = f"GitHub user not found: {username}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif e.response.status_code == 403:
                error_msg = "GitHub API rate limit exceeded"
                logger.error(error_msg)
                raise ValueError(error_msg)
            logger.error(f"HTTP error scraping GitHub profile {username}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error scraping GitHub profile {username}: {e}")
            raise

    async def _get_user_profile(self, client: httpx.AsyncClient, username: str) -> Dict[str, Any]:
        """
        Get user profile from GitHub API.

        Args:
            client: HTTP client
            username: GitHub username

        Returns:
            User profile data
        """
        response = await client.get(
            f"{self.api_base}/users/{username}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    async def _get_repositories(self, client: httpx.AsyncClient, username: str) -> List[Dict[str, Any]]:
        """
        Get user repositories from GitHub API.

        Args:
            client: HTTP client
            username: GitHub username

        Returns:
            List of repository data
        """
        response = await client.get(
            f"{self.api_base}/users/{username}/repos",
            headers=self.headers,
            params={"sort": "updated", "per_page": 100}
        )
        response.raise_for_status()
        return response.json()

    def _extract_language_stats(self, repos: List[Dict]) -> Dict[str, int]:
        """
        Extract language statistics from repositories.

        Args:
            repos: List of repository data

        Returns:
            Dictionary mapping language to count
        """
        languages = {}
        for repo in repos:
            if repo.get("language"):
                lang = repo["language"]
                languages[lang] = languages.get(lang, 0) + 1
        return languages

    def _process_repositories(self, repos: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extract relevant info from repositories.

        Args:
            repos: List of repository data

        Returns:
            List of processed repository info
        """
        processed = []
        for repo in repos[:50]:  # Limit number of repos
            processed.append({
                "name": repo.get("name"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "updated_at": repo.get("updated_at"),
                "topics": repo.get("topics", [])
            })
        return processed

    def _get_top_repos(self, repos: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top repositories by stars.

        Args:
            repos: List of repository data
            limit: Maximum number of repos to return

        Returns:
            List of top repository info
        """
        sorted_repos = sorted(
            repos,
            key=lambda x: x.get("stargazers_count", 0),
            reverse=True
        )
        return [
            {
                "name": repo.get("name"),
                "stars": repo.get("stargazers_count"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "url": repo.get("html_url")
            }
            for repo in sorted_repos[:limit]
        ]

    def _extract_technologies(self, repos: List[Dict]) -> List[str]:
        """
        Extract technologies from repositories.

        Args:
            repos: List of repository data

        Returns:
            Sorted list of unique technologies
        """
        technologies = set()
        for repo in repos:
            # Add primary language
            if repo.get("language"):
                technologies.add(repo["language"])

            # Add topics (GitHub topics often include technologies)
            for topic in repo.get("topics", []):
                technologies.add(topic)

        return sorted(list(technologies))

    def _extract_frameworks(self, repos: List[Dict]) -> List[str]:
        """
        Extract frameworks from repository names and topics.

        Args:
            repos: List of repository data

        Returns:
            Sorted list of detected frameworks
        """
        frameworks = set()
        framework_keywords = [
            'react', 'vue', 'angular', 'svelte', 'nextjs', 'nuxt',
            'django', 'flask', 'fastapi', 'express', 'nestjs', 'koa',
            'spring', 'springboot', 'rails', 'laravel', 'symfony',
            'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas',
            'numpy', 'matplotlib', 'seaborn', 'opencv', 'nltk', 'spacy',
            'docker', 'kubernetes', 'terraform', 'ansible', 'jenkins',
            'react-native', 'flutter', 'ionic', 'electron', 'redux',
            'graphql', 'rest', 'grpc', 'websocket', 'socketio'
        ]

        for repo in repos:
            repo_name = repo.get("name", "").lower()
            repo_desc = (repo.get("description") or "").lower()
            topics = [t.lower() for t in repo.get("topics", [])]

            for framework in framework_keywords:
                if (framework in repo_name or
                    framework in repo_desc or
                    framework in topics):
                    frameworks.add(framework)

        return sorted(list(frameworks))

    def extract_skills(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract skills from GitHub data.

        Args:
            data: Scraped GitHub data

        Returns:
            List of skill dictionaries with name, category, evidence, confidence
        """
        skills = []

        # Programming languages
        for lang, count in data.get("languages", {}).items():
            skills.append({
                "name": lang,
                "category": "programming_language",
                "evidence": f"Used in {count} repositories",
                "confidence": min(95, 70 + (count * 2))  # More repos = higher confidence
            })

        # Technologies and frameworks
        for tech in data.get("technologies", []):
            if tech not in data.get("languages", {}):  # Don't duplicate languages
                skills.append({
                    "name": tech,
                    "category": "technology",
                    "evidence": "Found in GitHub repositories",
                    "confidence": 75
                })

        for framework in data.get("frameworks", []):
            skills.append({
                "name": framework,
                "category": "framework",
                "evidence": "Used in projects",
                "confidence": 80
            })

        logger.info(f"Extracted {len(skills)} skills from GitHub data")
        return skills
