"""
Link Validation Service
Validates URLs and checks if they are accessible
"""
import re
import requests
from typing import Tuple, Optional, Dict
from urllib.parse import urlparse
import httpx

from app.config import settings


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

    @staticmethod
    def extract_github_username(url: str) -> Optional[str]:
        """
        Extract GitHub username from URL

        Args:
            url: GitHub URL (e.g., 'https://github.com/username' or 'github.com/username')

        Returns:
            Optional[str]: Username if found, None otherwise
        """
        if not url:
            return None

        # Add https:// if not present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Parse URL
        try:
            parsed = urlparse(url)

            # Check if it's a GitHub URL
            if 'github.com' not in parsed.netloc.lower():
                return None

            # Extract path parts
            path_parts = [p for p in parsed.path.split('/') if p]

            if not path_parts:
                return None

            # First part should be the username
            username = path_parts[0]

            # Validate username format (GitHub usernames: alphanumeric and hyphens, max 39 chars)
            username_pattern = re.compile(r'^[a-zA-Z0-9][-a-zA-Z0-9]{0,38}$')

            if username_pattern.match(username):
                return username

            return None

        except Exception:
            return None

    @staticmethod
    async def validate_github_url(url: str) -> Dict[str, any]:
        """
        Validate GitHub URL format and check if account exists

        Args:
            url: GitHub URL to validate

        Returns:
            Dict with keys:
                - is_valid_format: bool
                - username: Optional[str]
                - account_exists: Optional[bool]
                - error_message: Optional[str]
                - profile_data: Optional[Dict] (basic profile info if exists)
        """
        result = {
            'is_valid_format': False,
            'username': None,
            'account_exists': None,
            'error_message': None,
            'profile_data': None
        }

        # Extract username
        username = LinkValidator.extract_github_username(url)

        if not username:
            result['error_message'] = 'Invalid GitHub URL format. Expected: https://github.com/username'
            return result

        result['is_valid_format'] = True
        result['username'] = username

        # Check if account exists using GitHub API
        if not settings.GITHUB_TOKEN:
            result['error_message'] = 'GitHub token not configured. Cannot verify account existence.'
            result['account_exists'] = None  # Unknown
            return result

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    'Authorization': f'token {settings.GITHUB_TOKEN}',
                    'Accept': 'application/vnd.github.v3+json'
                }

                response = await client.get(
                    f'https://api.github.com/users/{username}',
                    headers=headers,
                    timeout=5.0
                )

                if response.status_code == 200:
                    data = response.json()
                    result['account_exists'] = True
                    result['profile_data'] = {
                        'username': data.get('login'),
                        'name': data.get('name'),
                        'bio': data.get('bio'),
                        'public_repos': data.get('public_repos'),
                        'followers': data.get('followers')
                    }
                elif response.status_code == 404:
                    result['account_exists'] = False
                    result['error_message'] = f'GitHub account @{username} not found'
                elif response.status_code == 403:
                    result['account_exists'] = None
                    result['error_message'] = 'GitHub API rate limit exceeded'
                else:
                    result['account_exists'] = None
                    result['error_message'] = f'GitHub API error: {response.status_code}'

        except httpx.TimeoutException:
            result['account_exists'] = None
            result['error_message'] = 'GitHub API request timed out'
        except Exception as e:
            result['account_exists'] = None
            result['error_message'] = f'Error checking GitHub account: {str(e)}'

        return result

    @staticmethod
    def validate_github_url_sync(url: str) -> Dict[str, any]:
        """
        Synchronous version of GitHub URL validation (format only, no API check)

        Args:
            url: GitHub URL to validate

        Returns:
            Dict with validation results
        """
        result = {
            'is_valid_format': False,
            'username': None,
            'error_message': None
        }

        username = LinkValidator.extract_github_username(url)

        if not username:
            result['error_message'] = 'Invalid GitHub URL format. Expected: https://github.com/username'
            return result

        result['is_valid_format'] = True
        result['username'] = username

        return result
