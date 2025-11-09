"""
ChatGPT Web Search Service
Uses GPT-4o with web search capability for multi-source skill extraction
"""
import os
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class ChatGPTWebSearchService:
    """
    Service for using ChatGPT with web search to discover and extract skills
    from various online sources like Stack Overflow, personal blogs, and web mentions.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize ChatGPT service with API key"""
        self.api_key = api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"

    def search_skill_mentions(
        self,
        full_name: str,
        github_username: Optional[str] = None,
        known_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search the web for mentions of a person's technical skills.

        Args:
            full_name: Person's full name
            github_username: GitHub username for more specific search
            known_skills: Already identified skills to validate

        Returns:
            Dict with web mentions, articles, and skill validations
        """
        logger.info(f"Searching web for skill mentions: {full_name}")

        # Build search context
        search_context = f"Full name: {full_name}"
        if github_username:
            search_context += f", GitHub: {github_username}"

        # Build prompt for GPT with web search
        prompt = f"""You are a technical skill researcher. Search the web for information about this person:

{search_context}

Your task is to find:
1. Web articles or blog posts where they are mentioned as having technical skills
2. Conference talks, presentations, or technical content they've created
3. Open source contributions mentioned on websites (beyond GitHub)
4. Technical interviews, podcasts, or media mentions
5. Any online portfolios, personal websites, or professional profiles

Focus on finding CONCRETE EVIDENCE of technical skills. Look for:
- Articles they've written about specific technologies
- Projects they've built and documented
- Technologies explicitly mentioned in their bio or profile
- Skills endorsed or mentioned by others

{"Known skills to validate: " + ", ".join(known_skills) if known_skills else ""}

Please search the web and provide your findings in JSON format:
{{
    "web_mentions": [
        {{
            "url": "source URL",
            "title": "article/page title",
            "mention_type": "article|talk|interview|portfolio|other",
            "skills_mentioned": ["skill1", "skill2"],
            "excerpt": "relevant excerpt from the content",
            "credibility": "high|medium|low"
        }}
    ],
    "skill_validations": {{
        "skill_name": {{
            "found_evidence": true/false,
            "sources": ["url1", "url2"],
            "confidence": "high|medium|low",
            "context": "how this skill was mentioned"
        }}
    }},
    "additional_skills": ["skills not in known list but found online"],
    "professional_summary": "brief summary of their online technical presence"
}}

IMPORTANT: Only include skills with clear evidence. Mark confidence as:
- high: Multiple sources or authoritative mention (they wrote about it, presented on it)
- medium: Single credible source
- low: Indirect mention or unclear context"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical researcher with web search capabilities. Search the web thoroughly and provide accurate, evidence-based findings in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Found {len(result.get('web_mentions', []))} web mentions")
            return result

        except Exception as e:
            logger.error(f"Error searching web for skill mentions: {e}")
            return {
                "web_mentions": [],
                "skill_validations": {},
                "additional_skills": [],
                "professional_summary": "",
                "error": str(e)
            }

    def discover_stackoverflow_profile(
        self,
        full_name: str,
        email: Optional[str] = None,
        github_username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for a person's Stack Overflow profile and activity.

        Args:
            full_name: Person's full name
            email: Email address
            github_username: GitHub username

        Returns:
            Dict with Stack Overflow profile data, reputation, and top tags
        """
        logger.info(f"Discovering Stack Overflow profile: {full_name}")

        search_context = f"Full name: {full_name}"
        if email:
            search_context += f", Email: {email}"
        if github_username:
            search_context += f", GitHub: {github_username}"

        prompt = f"""You are a technical profile researcher. Search for Stack Overflow profiles for this person:

{search_context}

Your task is to:
1. Find their Stack Overflow profile URL if it exists
2. Get their reputation score
3. Identify their top tags/technologies
4. Find notable answers or questions
5. Determine their activity level

Please search the web and Stack Overflow, then provide findings in JSON format:
{{
    "profile_found": true/false,
    "profile_url": "URL if found",
    "username": "Stack Overflow username",
    "reputation": number or null,
    "top_tags": [
        {{
            "tag": "technology name",
            "count": number of posts,
            "score": reputation in this tag
        }}
    ],
    "notable_contributions": [
        {{
            "title": "question or answer title",
            "url": "link",
            "score": upvotes,
            "type": "question|answer"
        }}
    ],
    "activity_level": "high|medium|low|inactive",
    "account_age_years": number or null,
    "total_answers": number,
    "total_questions": number,
    "skills_from_tags": ["skill1", "skill2"]
}}

If no profile is found, set profile_found to false and provide empty arrays."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a profile researcher with web search capabilities. Search Stack Overflow and provide accurate data in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Stack Overflow profile found: {result.get('profile_found', False)}")
            return result

        except Exception as e:
            logger.error(f"Error discovering Stack Overflow profile: {e}")
            return {
                "profile_found": False,
                "profile_url": None,
                "username": None,
                "reputation": None,
                "top_tags": [],
                "notable_contributions": [],
                "activity_level": "unknown",
                "skills_from_tags": [],
                "error": str(e)
            }

    def discover_personal_blog(
        self,
        full_name: str,
        github_username: Optional[str] = None,
        known_blog_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for a person's personal blog or technical writing.

        Args:
            full_name: Person's full name
            github_username: GitHub username
            known_blog_url: Blog URL from GitHub profile if available

        Returns:
            Dict with blog URL, articles, and skills extracted from content
        """
        logger.info(f"Discovering personal blog: {full_name}")

        search_context = f"Full name: {full_name}"
        if github_username:
            search_context += f", GitHub: {github_username}"
        if known_blog_url:
            search_context += f", Known blog URL: {known_blog_url}"

        prompt = f"""You are a technical content researcher. Search for personal blogs or technical writing by this person:

{search_context}

Your task is to:
1. Find their personal blog, Medium profile, Dev.to, or similar platforms
2. Identify recent technical articles they've written
3. Extract technologies and skills they write about
4. Assess the depth and recency of their technical content

Please search the web and provide findings in JSON format:
{{
    "blog_found": true/false,
    "blog_url": "primary blog URL",
    "additional_platforms": [
        {{
            "platform": "Medium|Dev.to|Hashnode|Substack|Personal|Other",
            "url": "profile or blog URL",
            "article_count": number or null
        }}
    ],
    "recent_articles": [
        {{
            "title": "article title",
            "url": "article URL",
            "date": "publication date if available",
            "technologies": ["tech1", "tech2"],
            "summary": "brief summary of content"
        }}
    ],
    "writing_topics": ["topic1", "topic2"],
    "skills_from_content": [
        {{
            "skill": "skill name",
            "frequency": "how often mentioned",
            "depth": "beginner|intermediate|advanced|expert",
            "evidence": "why we think they have this skill"
        }}
    ],
    "content_quality": "high|medium|low",
    "posting_frequency": "active|occasional|inactive",
    "total_articles_estimate": number or null
}}

If no blog is found, set blog_found to false and provide empty arrays."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content researcher with web search capabilities. Search for technical blogs and writing, provide accurate data in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Personal blog found: {result.get('blog_found', False)}")
            return result

        except Exception as e:
            logger.error(f"Error discovering personal blog: {e}")
            return {
                "blog_found": False,
                "blog_url": None,
                "additional_platforms": [],
                "recent_articles": [],
                "writing_topics": [],
                "skills_from_content": [],
                "content_quality": "unknown",
                "posting_frequency": "unknown",
                "error": str(e)
            }

    def extract_comprehensive_web_profile(
        self,
        full_name: str,
        email: Optional[str] = None,
        github_username: Optional[str] = None,
        github_blog_url: Optional[str] = None,
        known_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive web search combining all discovery methods.

        This is the main entry point that orchestrates all web searches.

        Returns:
            Combined results from all search methods
        """
        logger.info(f"Starting comprehensive web profile extraction: {full_name}")

        results = {
            "person": {
                "full_name": full_name,
                "email": email,
                "github_username": github_username
            },
            "web_mentions": {},
            "stackoverflow": {},
            "personal_blog": {},
            "consolidated_skills": [],
            "overall_confidence": {}
        }

        # 1. Search for general web mentions
        try:
            web_mentions = self.search_skill_mentions(
                full_name=full_name,
                github_username=github_username,
                known_skills=known_skills
            )
            results["web_mentions"] = web_mentions
        except Exception as e:
            logger.error(f"Error in web mentions search: {e}")
            results["web_mentions"]["error"] = str(e)

        # 2. Discover Stack Overflow profile
        try:
            stackoverflow = self.discover_stackoverflow_profile(
                full_name=full_name,
                email=email,
                github_username=github_username
            )
            results["stackoverflow"] = stackoverflow
        except Exception as e:
            logger.error(f"Error in Stack Overflow discovery: {e}")
            results["stackoverflow"]["error"] = str(e)

        # 3. Discover personal blog
        try:
            blog = self.discover_personal_blog(
                full_name=full_name,
                github_username=github_username,
                known_blog_url=github_blog_url
            )
            results["personal_blog"] = blog
        except Exception as e:
            logger.error(f"Error in blog discovery: {e}")
            results["personal_blog"]["error"] = str(e)

        # 4. Consolidate all discovered skills
        all_skills = set()

        # From web mentions
        if "additional_skills" in web_mentions:
            all_skills.update(web_mentions["additional_skills"])

        # From Stack Overflow
        if stackoverflow.get("skills_from_tags"):
            all_skills.update(stackoverflow["skills_from_tags"])

        # From blog
        if blog.get("skills_from_content"):
            all_skills.update([s["skill"] for s in blog["skills_from_content"]])

        results["consolidated_skills"] = list(all_skills)

        logger.info(f"Comprehensive extraction complete. Found {len(all_skills)} skills from web sources")

        return results


# Singleton instance
_web_search_service = None

def get_web_search_service() -> ChatGPTWebSearchService:
    """Get or create the ChatGPT web search service singleton"""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = ChatGPTWebSearchService()
    return _web_search_service
