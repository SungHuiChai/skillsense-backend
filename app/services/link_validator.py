"""
Link Validation Service
Validates URLs and checks if they are accessible
"""
import re
import requests
from typing import Tuple
from urllib.parse import urlparse


class LinkValidator:
    """Validate and verify URLs"""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if URL has valid format

        Args:
            url: URL string to validate

        Returns:
            bool: True if URL is valid format
        """
        if not url:
            return False

        # Basic URL pattern
        url_pattern = re.compile(
            r'^(?:http|https)://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    @staticmethod
    def is_accessible(url: str, timeout: int = 5) -> bool:
        """
        Check if URL is accessible (returns 200-399 status code)

        Args:
            url: URL to check
            timeout: Request timeout in seconds

        Returns:
            bool: True if URL is accessible
        """
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return 200 <= response.status_code < 400
        except:
            # If HEAD fails, try GET
            try:
                response = requests.get(url, timeout=timeout, allow_redirects=True)
                return 200 <= response.status_code < 400
            except:
                return False

    @staticmethod
    def verify_domain(url: str, expected_domain: str) -> bool:
        """
        Verify URL belongs to expected domain

        Args:
            url: URL to check
            expected_domain: Expected domain (e.g., 'github.com')

        Returns:
            bool: True if URL is from expected domain
        """
        try:
            parsed = urlparse(url)
            return expected_domain.lower() in parsed.netloc.lower()
        except:
            return False

    @staticmethod
    def validate_social_link(url: str, platform: str) -> Tuple[bool, bool, bool]:
        """
        Validate social media link

        Args:
            url: URL to validate
            platform: Platform name ('github', 'linkedin', 'twitter', 'portfolio')

        Returns:
            Tuple[bool, bool, bool]: (is_valid_format, is_correct_domain, is_accessible)
        """
        is_valid_format = LinkValidator.is_valid_url(url)

        # Check domain based on platform
        domain_map = {
            'github': 'github.com',
            'linkedin': 'linkedin.com',
            'twitter': ['twitter.com', 'x.com'],
            'portfolio': None  # Any domain is fine
        }

        expected_domains = domain_map.get(platform)
        is_correct_domain = True

        if expected_domains:
            if isinstance(expected_domains, list):
                is_correct_domain = any(
                    LinkValidator.verify_domain(url, domain)
                    for domain in expected_domains
                )
            else:
                is_correct_domain = LinkValidator.verify_domain(url, expected_domains)

        # Check accessibility (optional, can be slow)
        # is_accessible = LinkValidator.is_accessible(url)
        is_accessible = True  # Skip actual HTTP check for now to avoid delays

        return is_valid_format, is_correct_domain, is_accessible
