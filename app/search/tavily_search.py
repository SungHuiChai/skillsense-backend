"""
Tavily search integration for finding web mentions and articles.
"""

from typing import Dict, Any, List, Optional
import httpx
import asyncio
import time
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TavilySearch:
    """Web search using Tavily API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Tavily search.

        Args:
            config: Configuration dictionary with tavily_api_key and search settings

        Raises:
            ValueError: If API key is missing
        """
        self.api_key = config.get('tavily_api_key')
        if not self.api_key:
            raise ValueError("Tavily API key is required")

        self.api_base = "https://api.tavily.com"
        self.search_depth = config.get('search_depth', 'advanced')  # 'basic' or 'advanced'
        self.max_results = config.get('max_results', 10)
        self.timeout = config.get('timeout', 30)
        self.rate_limit_delay = config.get('rate_limit_delay', 1.0)
        self.last_request_time = None

        logger.info(f"Tavily search initialized with depth={self.search_depth}, max_results={self.max_results}")

    async def _rate_limit(self):
        """Implement rate limiting to avoid overwhelming the API."""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the web for mentions of a person or topic.

        Args:
            query: Search query (e.g., "John Doe machine learning")
            **kwargs: Additional search parameters
                - include_domains: List of domains to prioritize
                - exclude_domains: List of domains to exclude
                - max_results: Override default max results

        Returns:
            List of search results with title, url, content, score

        Raises:
            ValueError: If API key is invalid or rate limit exceeded
            Exception: For other API errors
        """
        await self._rate_limit()

        logger.info(f"Searching Tavily for: {query}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": self.search_depth,
                    "max_results": kwargs.get('max_results', self.max_results),
                    "include_answer": False,  # We don't need AI-generated answers
                    "include_raw_content": True  # Get full content for extraction
                }

                if kwargs.get('include_domains'):
                    payload["include_domains"] = kwargs['include_domains']

                if kwargs.get('exclude_domains'):
                    payload["exclude_domains"] = kwargs['exclude_domains']

                response = await client.post(
                    f"{self.api_base}/search",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                results = self._process_results(data.get("results", []))
                logger.info(f"Found {len(results)} results for query: {query}")
                return results

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                error_msg = "Invalid Tavily API key"
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif e.response.status_code == 429:
                error_msg = "Tavily API rate limit exceeded"
                logger.error(error_msg)
                raise ValueError(error_msg)
            logger.error(f"HTTP error in Tavily search: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in Tavily search for query '{query}': {e}")
            raise

    def _process_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Process and normalize search results.

        Args:
            results: Raw Tavily search results

        Returns:
            List of processed results
        """
        processed = []

        for result in results:
            processed.append({
                "title": result.get("title"),
                "url": result.get("url"),
                "content": result.get("content"),
                "raw_content": result.get("raw_content"),
                "score": result.get("score", 0),
                "published_date": result.get("published_date"),
                "source": self._extract_source_name(result.get("url"))
            })

        return processed

    def _extract_source_name(self, url: str) -> str:
        """
        Extract clean source name from URL.

        Args:
            url: URL string

        Returns:
            Clean source name (e.g., "techcrunch", "medium")
        """
        if not url:
            return "Unknown"

        try:
            domain = urlparse(url).netloc
            # Remove www. and get main domain
            domain = domain.replace('www.', '')
            return domain.split('.')[0].capitalize()
        except Exception:
            return "Unknown"

    async def search_person(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for a specific person with contextual information.

        Args:
            name: Person's name
            context: Additional context (company, skills, location)

        Returns:
            List of relevant web mentions
        """
        queries = self._generate_person_queries(name, context)
        all_results = []

        logger.info(f"Searching for person: {name} with {len(queries)} queries")

        for query in queries:
            try:
                results = await self.search(query, max_results=5)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Query '{query}' failed: {e}")
                continue

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)

        logger.info(f"Found {len(unique_results)} unique results for person: {name}")
        return unique_results[:self.max_results]

    def _generate_person_queries(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Generate multiple search queries for comprehensive results.

        Args:
            name: Person's name
            context: Additional context

        Returns:
            List of search query strings
        """
        queries = [f'"{name}"']  # Base query with exact name

        if context:
            company = context.get('company')
            skills = context.get('skills', [])

            if company:
                queries.append(f'"{name}" {company}')

            if skills and len(skills) > 0:
                # Add query with top skill
                queries.append(f'"{name}" {skills[0]}')

            # Look for speaking engagements
            queries.append(f'"{name}" (speaking OR conference OR interview)')

            # Look for publications
            queries.append(f'"{name}" (article OR blog OR publication)')

        logger.debug(f"Generated {len(queries)} search queries for {name}")
        return queries[:3]  # Limit to avoid too many API calls

    def calculate_relevance_score(
        self,
        result: Dict[str, Any],
        person_name: str,
        keywords: List[str] = None
    ) -> float:
        """
        Calculate relevance score for a search result.

        Args:
            result: Search result dictionary
            person_name: Name of the person
            keywords: Additional keywords to check

        Returns:
            Relevance score (0-100)
        """
        score = 0.0
        keywords = keywords or []

        # Base score from Tavily
        tavily_score = result.get('score', 0) * 100
        score += tavily_score * 0.5

        # Check if person name is in title (high relevance)
        title = (result.get('title') or "").lower()
        if person_name.lower() in title:
            score += 30

        # Check if person name is in content
        content = (result.get('content') or "").lower()
        if person_name.lower() in content:
            score += 10

        # Check for keywords
        if keywords:
            keyword_matches = sum(1 for kw in keywords if kw.lower() in content)
            score += min(20, keyword_matches * 5)

        return min(100.0, round(score, 2))

    def calculate_credibility_score(self, result: Dict[str, Any]) -> float:
        """
        Calculate credibility score based on source.

        Args:
            result: Search result dictionary

        Returns:
            Credibility score (0-100)
        """
        # High credibility sources
        high_credibility = [
            'techcrunch', 'medium', 'github', 'stackoverflow', 'dev.to',
            'arxiv', 'ieee', 'acm', 'springer', 'forbes', 'wired',
            'thenextweb', 'venturebeat', 'arstechnica', 'zdnet'
        ]

        # Medium credibility sources
        medium_credibility = [
            'reddit', 'hackernoon', 'towardsdatascience', 'analytics',
            'linkedin', 'twitter', 'facebook', 'youtube'
        ]

        source = result.get('source', '').lower()

        if any(s in source for s in high_credibility):
            return 90.0
        elif any(s in source for s in medium_credibility):
            return 70.0
        else:
            return 50.0  # Default credibility
