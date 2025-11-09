"""
OpenAI GPT-4o Service for Skill Extraction and Analysis
Uses GPT-4o to analyze GitHub data and extract structured skills
"""
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIAnalyzer:
    """Analyze GitHub data using OpenAI GPT-4o"""

    def __init__(self):
        """Initialize OpenAI client"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def analyze_developer_activity(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze developer activity, contribution patterns, and work quality

        Args:
            github_data: GitHub profile and repository data

        Returns:
            Dict containing:
                - activity_level: Low/Medium/High/Very High
                - commit_quality_score: 0-100
                - contribution_consistency: Regular/Irregular/Sporadic
                - collaboration_score: 0-100
                - project_diversity: 0-100
                - insights: Detailed insights about the developer
                - professional_summary: AI-generated professional description
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._fallback_activity_analysis(github_data)

        try:
            context = self._prepare_activity_context(github_data)

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert technical recruiter analyzing a developer's GitHub activity.

Analyze the developer's contribution patterns, project quality, and overall engagement.

Return a JSON object with:
{
  "activity_level": "low|medium|high|very_high",
  "commit_quality_score": 0-100,
  "contribution_consistency": "regular|irregular|sporadic",
  "collaboration_score": 0-100,
  "project_diversity": 0-100,
  "strengths": ["strength1", "strength2", ...],
  "areas_for_growth": ["area1", "area2", ...],
  "insights": {
    "activity_insights": "Detailed analysis of contribution patterns",
    "commit_quality_insights": "Analysis of commit messages, code quality indicators",
    "collaboration_insights": "Team work and open source contribution patterns",
    "project_insights": "Diversity and complexity of projects"
  },
  "professional_summary": "2-3 sentence compelling summary highlighting unique value",
  "recommended_roles": ["role1", "role2", "role3"]
}

Base your analysis on:
- Number and frequency of commits
- Diversity of projects and technologies
- Repository complexity and stars/forks
- Commit message quality
- Contribution patterns
- Bio and profile description"""
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this developer's GitHub profile:\n\n{context}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully analyzed developer activity with GPT-4o")
            return result

        except Exception as e:
            logger.error(f"Error analyzing activity: {e}")
            return self._fallback_activity_analysis(github_data)

    def _prepare_activity_context(self, github_data: Dict[str, Any]) -> str:
        """Prepare context for activity analysis"""
        context_parts = []

        # Profile
        if github_data.get('name'):
            context_parts.append(f"Name: {github_data['name']}")
        if github_data.get('bio'):
            context_parts.append(f"Bio: {github_data['bio']}")

        # Activity metrics
        context_parts.append(f"\nActivity Metrics:")
        context_parts.append(f"- Public Repos: {github_data.get('public_repos', 0)}")
        context_parts.append(f"- Followers: {github_data.get('followers', 0)}")
        context_parts.append(f"- Following: {github_data.get('following', 0)}")

        # Languages and diversity
        if github_data.get('languages'):
            total_repos = sum(github_data['languages'].values())
            context_parts.append(f"\nLanguage Diversity ({total_repos} repos):")
            for lang, count in sorted(github_data['languages'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_repos * 100) if total_repos > 0 else 0
                context_parts.append(f"- {lang}: {count} repos ({percentage:.1f}%)")

        # Repository details
        if github_data.get('repositories'):
            context_parts.append(f"\nRepository Analysis ({len(github_data['repositories'])} total):")
            for repo in github_data['repositories'][:10]:
                context_parts.append(f"\n- {repo.get('name')}")
                if repo.get('description'):
                    context_parts.append(f"  Description: {repo['description']}")
                if repo.get('stargazers_count', 0) > 0:
                    context_parts.append(f"  Stars: {repo.get('stargazers_count')}")
                if repo.get('forks_count', 0) > 0:
                    context_parts.append(f"  Forks: {repo.get('forks_count')}")
                if repo.get('updated_at'):
                    context_parts.append(f"  Last Updated: {repo.get('updated_at')}")

        return "\n".join(context_parts)

    def _fallback_activity_analysis(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback activity analysis without OpenAI"""
        repos = github_data.get('public_repos', 0)
        followers = github_data.get('followers', 0)

        activity_level = "high" if repos >= 20 else "medium" if repos >= 10 else "low"

        return {
            "activity_level": activity_level,
            "commit_quality_score": 70,
            "contribution_consistency": "regular" if repos >= 15 else "irregular",
            "collaboration_score": min(followers * 10, 100),
            "project_diversity": min(len(github_data.get('languages', {})) * 20, 100),
            "strengths": ["Active contributor", "Diverse tech stack"],
            "areas_for_growth": ["Increase collaboration"],
            "insights": {
                "activity_insights": f"Developer has {repos} public repositories",
                "commit_quality_insights": "No analysis available",
                "collaboration_insights": f"{followers} followers on GitHub",
                "project_insights": f"Works with {len(github_data.get('languages', {}))} different languages"
            },
            "professional_summary": f"Active developer with {repos} public repositories",
            "recommended_roles": ["Software Developer", "Full Stack Engineer"]
        }

    async def extract_skills_from_github(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured skills from GitHub data using GPT-4o

        Args:
            github_data: GitHub profile and repository data

        Returns:
            Dict containing:
                - technical_skills: List of technical skills with proficiency
                - frameworks: List of frameworks/libraries
                - languages: Programming languages with proficiency
                - tools: Development tools
                - domains: Domain expertise areas
                - skill_summary: Natural language summary
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._fallback_extraction(github_data)

        try:
            # Prepare context for GPT-4o
            context = self._prepare_github_context(github_data)

            # Call GPT-4o
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert technical recruiter analyzing GitHub profiles.
Extract structured skills data from the GitHub profile and repository information.

Return a JSON object with:
{
  "technical_skills": [{"name": "skill", "proficiency": "beginner|intermediate|advanced|expert", "years_inferred": 1-10}],
  "frameworks": [{"name": "framework", "category": "web|mobile|data|ml|etc"}],
  "languages": [{"name": "language", "proficiency": "beginner|intermediate|advanced|expert", "projects_count": N}],
  "tools": ["tool1", "tool2"],
  "domains": ["domain1", "domain2"],
  "soft_skills": ["skill1", "skill2"],
  "skill_summary": "A 2-3 sentence professional summary of technical expertise"
}

Infer proficiency from:
- Number of repositories using the technology
- Complexity of projects
- Recency of usage
- Commit patterns"""
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this GitHub profile and extract skills:\n\n{context}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000
            )

            # Parse response
            result = json.loads(response.choices[0].message.content)

            logger.info(f"Successfully extracted skills using GPT-4o")
            return result

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return self._fallback_extraction(github_data)

    def _prepare_github_context(self, github_data: Dict[str, Any]) -> str:
        """
        Prepare GitHub data as context for GPT-4o

        Args:
            github_data: Raw GitHub data

        Returns:
            Formatted string context
        """
        context_parts = []

        # Basic profile info
        if github_data.get('name'):
            context_parts.append(f"Name: {github_data['name']}")
        if github_data.get('bio'):
            context_parts.append(f"Bio: {github_data['bio']}")
        if github_data.get('company'):
            context_parts.append(f"Company: {github_data['company']}")

        # Statistics
        context_parts.append(f"\nStatistics:")
        context_parts.append(f"- Public Repositories: {github_data.get('public_repos', 0)}")
        context_parts.append(f"- Followers: {github_data.get('followers', 0)}")

        # Languages used
        if github_data.get('languages'):
            context_parts.append(f"\nProgramming Languages Used:")
            for lang, count in github_data['languages'].items():
                context_parts.append(f"- {lang}: {count} repositories")

        # Technologies/Frameworks
        if github_data.get('technologies'):
            context_parts.append(f"\nTechnologies: {', '.join(github_data['technologies'])}")

        if github_data.get('frameworks'):
            context_parts.append(f"Frameworks: {', '.join(github_data['frameworks'])}")

        # Top repositories
        if github_data.get('top_repos'):
            context_parts.append(f"\nTop Repositories:")
            for repo in github_data['top_repos'][:5]:
                context_parts.append(f"- {repo.get('name')}: {repo.get('description', 'No description')}")
                if repo.get('language'):
                    context_parts.append(f"  Language: {repo['language']}")
                if repo.get('topics'):
                    context_parts.append(f"  Topics: {', '.join(repo['topics'])}")

        # Repository data
        if github_data.get('repositories'):
            context_parts.append(f"\nAll Repositories ({len(github_data['repositories'])} total):")
            for repo in github_data['repositories'][:10]:  # Limit to 10 for context length
                context_parts.append(f"- {repo.get('name')}")
                if repo.get('description'):
                    context_parts.append(f"  Description: {repo['description']}")
                if repo.get('language'):
                    context_parts.append(f"  Primary Language: {repo['language']}")

        return "\n".join(context_parts)

    def _fallback_extraction(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback skill extraction without OpenAI (rule-based)

        Args:
            github_data: GitHub data

        Returns:
            Basic skills extraction
        """
        logger.info("Using fallback skill extraction (rule-based)")

        languages = []
        if github_data.get('languages'):
            for lang, count in github_data['languages'].items():
                proficiency = "expert" if count >= 5 else "advanced" if count >= 3 else "intermediate"
                languages.append({
                    "name": lang,
                    "proficiency": proficiency,
                    "projects_count": count
                })

        technologies = github_data.get('technologies', [])
        frameworks = []
        if github_data.get('frameworks'):
            frameworks = [{"name": fw, "category": "unknown"} for fw in github_data['frameworks']]

        return {
            "technical_skills": [{"name": tech, "proficiency": "intermediate", "years_inferred": 2} for tech in technologies],
            "frameworks": frameworks,
            "languages": languages,
            "tools": ["Git", "GitHub"],
            "domains": [],
            "soft_skills": [],
            "skill_summary": f"Developer with experience in {', '.join(technologies[:3]) if technologies else 'various technologies'}"
        }

    async def generate_profile_summary(self, github_data: Dict[str, Any], cv_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a professional profile summary combining GitHub and CV data

        Args:
            github_data: GitHub profile data
            cv_data: Optional CV extracted data

        Returns:
            Professional summary text
        """
        if not self.client:
            return "Profile summary unavailable (OpenAI not configured)"

        try:
            context = self._prepare_github_context(github_data)

            if cv_data:
                context += f"\n\nCV Data:\n"
                if cv_data.get('work_history'):
                    context += f"Work Experience: {json.dumps(cv_data['work_history'][:3], indent=2)}\n"
                if cv_data.get('education'):
                    context += f"Education: {json.dumps(cv_data['education'], indent=2)}\n"

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional resume writer. Generate a compelling 3-4 sentence professional summary based on the candidate's GitHub profile and CV data. Focus on technical strengths, experience, and unique value proposition."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating profile summary: {e}")
            return "Experienced developer with strong technical skills"

    async def comprehensive_analysis(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive analysis combining skills extraction and activity analysis

        Args:
            github_data: GitHub profile and repository data

        Returns:
            Dict containing both skills and activity analysis
        """
        logger.info("Starting comprehensive GitHub analysis")

        # Run both analyses in parallel for efficiency
        skills_task = self.extract_skills_from_github(github_data)
        activity_task = self.analyze_developer_activity(github_data)

        skills_result = await skills_task
        activity_result = await activity_task

        return {
            "skills_analysis": skills_result,
            "activity_analysis": activity_result,
            "analyzed_at": datetime.now().isoformat()
        }
