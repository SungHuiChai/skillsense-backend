"""
Base scraper abstract class for all data collection scrapers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize scraper with configuration.

        Args:
            config: Configuration dictionary with scraper-specific settings
        """
        self.config = config
        self.rate_limit_delay = config.get('rate_limit_delay', 1.0)
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        self.last_request_time = None

    @abstractmethod
    async def scrape(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Scrape data from the given URL.

        Args:
            url: URL to scrape
            **kwargs: Additional scraper-specific parameters

        Returns:
            Dict containing scraped data and metadata

        Raises:
            ValueError: If URL is invalid
            Exception: For other scraping errors
        """
        pass

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is appropriate for this scraper.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid for this scraper, False otherwise
        """
        pass

    @abstractmethod
    def extract_skills(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract skills from scraped data.

        Args:
            data: Scraped data dictionary

        Returns:
            List of skill dictionaries with name, category, evidence, confidence
        """
        pass

    async def _rate_limit(self):
        """Implement rate limiting to avoid overwhelming external APIs."""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
        self.last_request_time = time.time()

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"All {self.max_retries} retry attempts failed: {e}")
                    raise
                wait_time = 2 ** attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for scraped data.

        Args:
            data: Scraped data dictionary

        Returns:
            Confidence score (0-100)
        """
        if not data:
            return 0.0

        # Calculate completeness based on non-null values
        total_fields = len(data)
        populated_fields = sum(1 for v in data.values() if v)

        if total_fields == 0:
            return 0.0

        completeness = populated_fields / total_fields
        return round(completeness * 100, 2)

    def _get_metadata(self) -> Dict[str, Any]:
        """
        Get scraper metadata.

        Returns:
            Dictionary with scraper name, version, and collection time
        """
        return {
            "scraper_name": self.__class__.__name__,
            "collected_at": datetime.utcnow().isoformat(),
            "rate_limit_delay": self.rate_limit_delay,
            "timeout": self.timeout
        }
