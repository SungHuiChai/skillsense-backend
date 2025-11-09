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

                # Collect READMEs from top repos (for GPT analysis)
                readme_samples = await self._collect_readme_samples(client, username, repos_data, limit=10)

                # Collect commit samples from top repos (for GPT analysis)
                commit_samples = await self._collect_commit_samples(client, username, repos_data, limit=50)

                # Calculate commit statistics
                commit_statistics = self._calculate_commit_statistics(commit_samples)

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
                    "readme_samples": readme_samples,  # NEW: README content for GPT
                    "commit_samples": commit_samples,  # NEW: Commit messages for GPT
                    "commit_statistics": commit_statistics,  # NEW: Commit patterns
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

    async def _collect_readme_samples(
        self,
        client: httpx.AsyncClient,
        username: str,
        repos: List[Dict],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Collect README content from top repositories for GPT analysis.

        Args:
            client: HTTP client
            username: GitHub username
            repos: List of repository data
            limit: Maximum number of READMEs to collect

        Returns:
            List of README samples with metadata
        """
        readme_samples = []

        # Sort repos by stars and recency
        sorted_repos = sorted(
            repos,
            key=lambda x: (x.get("stargazers_count", 0), x.get("updated_at", "")),
            reverse=True
        )[:limit]

        for repo in sorted_repos:
            repo_name = repo.get("name")
            if not repo_name:
                continue

            try:
                # Fetch README from GitHub API
                response = await client.get(
                    f"{self.api_base}/repos/{username}/{repo_name}/readme",
                    headers=self.headers
                )

                if response.status_code == 200:
                    readme_data = response.json()
                    # Content is base64 encoded
                    import base64
                    content = base64.b64decode(readme_data.get("content", "")).decode("utf-8")

                    # Limit content length (first 3000 chars for GPT)
                    content_preview = content[:3000] if len(content) > 3000 else content

                    readme_samples.append({
                        "repo_name": repo_name,
                        "repo_description": repo.get("description"),
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language"),
                        "topics": repo.get("topics", []),
                        "content": content_preview,
                        "content_length": len(content),
                        "url": readme_data.get("html_url")
                    })
                    logger.debug(f"Collected README from {repo_name}")

            except Exception as e:
                logger.debug(f"Could not fetch README for {repo_name}: {e}")
                continue

        logger.info(f"Collected {len(readme_samples)} README samples")
        return readme_samples

    async def _collect_commit_samples(
        self,
        client: httpx.AsyncClient,
        username: str,
        repos: List[Dict],
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Collect recent commit messages for GPT analysis.

        Args:
            client: HTTP client
            username: GitHub username
            repos: List of repository data
            limit: Maximum number of commits to collect

        Returns:
            List of commit samples with metadata
        """
        commit_samples = []
        commits_per_repo = max(5, limit // 10)  # Collect from top 10 repos

        # Sort by recent activity
        sorted_repos = sorted(
            repos,
            key=lambda x: x.get("updated_at", ""),
            reverse=True
        )[:10]

        for repo in sorted_repos:
            repo_name = repo.get("name")
            if not repo_name or repo.get("fork", False):  # Skip forks
                continue

            try:
                # Fetch recent commits
                response = await client.get(
                    f"{self.api_base}/repos/{username}/{repo_name}/commits",
                    headers=self.headers,
                    params={"per_page": commits_per_repo}
                )

                if response.status_code == 200:
                    commits = response.json()

                    for commit in commits:
                        commit_data = commit.get("commit", {})
                        author = commit_data.get("author", {})

                        commit_samples.append({
                            "repo_name": repo_name,
                            "repo_language": repo.get("language"),
                            "message": commit_data.get("message", ""),
                            "date": author.get("date"),
                            "author_name": author.get("name"),
                            "sha": commit.get("sha", "")[:7]  # Short SHA
                        })

                    logger.debug(f"Collected {len(commits)} commits from {repo_name}")

                if len(commit_samples) >= limit:
                    break

            except Exception as e:
                logger.debug(f"Could not fetch commits for {repo_name}: {e}")
                continue

        logger.info(f"Collected {len(commit_samples)} commit samples")
        return commit_samples[:limit]

    def _calculate_commit_statistics(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate commit pattern statistics for GPT analysis.

        Args:
            commits: List of commit samples

        Returns:
            Dictionary with commit statistics
        """
        if not commits:
            return {
                "total_commits": 0,
                "avg_message_length": 0,
                "has_conventional_commits": False,
                "languages_committed": [],
                "commit_frequency": "unknown"
            }

        from datetime import datetime
        from collections import Counter

        # Parse commit messages
        message_lengths = [len(c["message"]) for c in commits]

        # Check for conventional commits (feat:, fix:, docs:, etc.)
        conventional_patterns = ["feat:", "fix:", "docs:", "style:", "refactor:", "test:", "chore:"]
        conventional_count = sum(
            1 for c in commits
            if any(c["message"].lower().startswith(p) for p in conventional_patterns)
        )

        # Language distribution
        languages = Counter(c.get("repo_language") for c in commits if c.get("repo_language"))

        # Calculate commit frequency
        try:
            dates = [datetime.fromisoformat(c["date"].replace("Z", "+00:00")) for c in commits if c.get("date")]
            if len(dates) >= 2:
                date_range = (max(dates) - min(dates)).days
                commits_per_day = len(dates) / max(1, date_range)

                if commits_per_day >= 1:
                    frequency = "daily"
                elif commits_per_day >= 0.5:
                    frequency = "several_per_week"
                elif commits_per_day >= 0.2:
                    frequency = "weekly"
                else:
                    frequency = "occasional"
            else:
                frequency = "insufficient_data"
        except Exception:
            frequency = "unknown"

        return {
            "total_commits": len(commits),
            "avg_message_length": sum(message_lengths) / len(message_lengths) if message_lengths else 0,
            "has_conventional_commits": conventional_count > len(commits) * 0.3,  # 30% threshold
            "conventional_commit_percentage": (conventional_count / len(commits) * 100) if commits else 0,
            "languages_committed": dict(languages.most_common(5)),
            "commit_frequency": frequency,
            "repos_with_commits": len(set(c["repo_name"] for c in commits))
        }

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
