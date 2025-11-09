"""
GPT-4o Scoring Service
Replaces mathematical confidence scoring with AI-driven analysis

Uses enhanced data from:
- GitHub README samples
- Commit messages and patterns
- LinkedIn profile data
- Web mentions

Provides:
- Skill confidence scores (0-100%)
- Skill proficiency levels (beginner/intermediate/advanced/expert)
- Years of experience estimates
- Overall profile quality scores
"""

import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class GPTScoringService:
    """AI-driven skill confidence scoring using GPT-4o"""

    def __init__(self):
        """Initialize OpenAI client"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("GPT Scoring Service initialized")

    async def score_skill_confidence(
        self,
        skill_name: str,
        github_data: Optional[Dict[str, Any]] = None,
        linkedin_data: Optional[Dict[str, Any]] = None,
        web_mentions: Optional[List[Dict[str, Any]]] = None,
        cv_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Score a single skill using GPT-4o analysis of all available data.

        Args:
            skill_name: Name of the skill to score
            github_data: GitHub profile and repository data (with README/commit samples)
            linkedin_data: LinkedIn profile data
            web_mentions: List of web mentions/articles
            cv_data: CV/resume data

        Returns:
            Dict containing:
                - confidence_score: 0-100 (how confident we are this is a real skill)
                - proficiency_level: beginner|intermediate|advanced|expert
                - years_experience: Estimated years (1-20+)
                - evidence_quality: low|medium|high|excellent
                - reasoning: Explanation of the score
                - data_sources_used: List of sources that contributed
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._fallback_skill_score(skill_name)

        try:
            # Prepare context for GPT
            context = self._prepare_skill_context(
                skill_name, github_data, linkedin_data, web_mentions, cv_data
            )

            # Call GPT-4o for skill-specific analysis
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert technical recruiter evaluating candidate skills.

Analyze ALL available evidence about this specific skill and provide:

1. **Confidence Score (0-100)**: How confident are you this person ACTUALLY has this skill?
   - Consider: evidence quality, recency, depth of usage, consistency across sources
   - 90-100: Overwhelming evidence, clear expertise
   - 75-89: Strong evidence, proven capability
   - 60-74: Moderate evidence, likely competent
   - 40-59: Limited evidence, uncertain
   - 0-39: Weak/no evidence, likely false positive

2. **Proficiency Level**: beginner|intermediate|advanced|expert
   - Beginner: Just learning, limited projects
   - Intermediate: Comfortable with basics, some experience
   - Advanced: Deep knowledge, complex projects, consistent use
   - Expert: Mastery, contributions to community, teaching others

3. **Years Experience (1-20+)**: Estimate based on:
   - Project complexity and evolution over time
   - Commit history patterns
   - LinkedIn experience entries
   - Web articles/talks timeline

4. **Evidence Quality**: low|medium|high|excellent
   - Excellent: Multiple sources, deep technical content, recent activity
   - High: Clear project evidence, good documentation
   - Medium: Some indicators, limited depth
   - Low: Minimal evidence, single mention

Return ONLY a JSON object:
{
  "confidence_score": 85,
  "proficiency_level": "advanced",
  "years_experience": 5,
  "evidence_quality": "high",
  "reasoning": "Clear explanation of why these scores were given, referencing specific evidence",
  "data_sources_used": ["github_readme", "commits", "linkedin", "cv"],
  "key_evidence": ["Specific examples that influenced the score"],
  "red_flags": ["Any concerns or inconsistencies"]
}

Be CRITICAL and HONEST. Don't inflate scores. If evidence is weak, say so."""
                    },
                    {
                        "role": "user",
                        "content": f"Skill to evaluate: {skill_name}\n\nEvidence:\n\n{context}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Low temperature for consistent scoring
                max_tokens=1500
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"GPT scored skill '{skill_name}': {result['confidence_score']}%")

            return {
                "skill": skill_name,
                **result,
                "scored_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error scoring skill '{skill_name}': {e}")
            return self._fallback_skill_score(skill_name)

    async def score_multiple_skills(
        self,
        skills: List[str],
        github_data: Optional[Dict[str, Any]] = None,
        linkedin_data: Optional[Dict[str, Any]] = None,
        web_mentions: Optional[List[Dict[str, Any]]] = None,
        cv_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Score multiple skills efficiently using batch GPT analysis.

        Args:
            skills: List of skill names to score
            github_data: GitHub data
            linkedin_data: LinkedIn data
            web_mentions: Web mentions
            cv_data: CV data

        Returns:
            List of skill scores
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return [self._fallback_skill_score(skill) for skill in skills]

        try:
            # Prepare comprehensive context once for all skills
            context = self._prepare_comprehensive_context(
                github_data, linkedin_data, web_mentions, cv_data
            )

            # Batch analyze all skills
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert technical recruiter evaluating candidate skills.

Analyze the provided profile data and score EACH skill in the list.

For EACH skill, provide:
- confidence_score (0-100): How confident you are they have this skill
- proficiency_level: beginner|intermediate|advanced|expert
- years_experience: Estimated years (1-20+)
- evidence_quality: low|medium|high|excellent
- reasoning: Brief explanation

Return a JSON object with a "skills" array:
{
  "skills": [
    {
      "skill": "Python",
      "confidence_score": 90,
      "proficiency_level": "advanced",
      "years_experience": 6,
      "evidence_quality": "excellent",
      "reasoning": "Strong evidence across multiple projects...",
      "data_sources_used": ["github_readme", "commits"],
      "key_evidence": ["Built ML pipeline in Python", "300+ Python commits"]
    },
    ...
  ],
  "overall_assessment": "Brief overall technical assessment"
}

Be CRITICAL. Only high scores for clear evidence."""
                    },
                    {
                        "role": "user",
                        "content": f"Skills to evaluate: {', '.join(skills)}\n\nCandidate Profile:\n\n{context}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=4000
            )

            result = json.loads(response.choices[0].message.content)
            skills_scores = result.get("skills", [])

            # Add timestamp
            for score in skills_scores:
                score["scored_at"] = datetime.now().isoformat()

            logger.info(f"GPT scored {len(skills_scores)} skills")
            return skills_scores

        except Exception as e:
            logger.error(f"Error scoring multiple skills: {e}")
            return [self._fallback_skill_score(skill) for skill in skills]

    async def calculate_profile_quality(
        self,
        github_data: Optional[Dict[str, Any]] = None,
        linkedin_data: Optional[Dict[str, Any]] = None,
        web_mentions: Optional[List[Dict[str, Any]]] = None,
        cv_data: Optional[Dict[str, Any]] = None,
        skills_scores: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Calculate overall profile quality score using GPT analysis.

        Args:
            github_data: GitHub data with enhanced content
            linkedin_data: LinkedIn profile data
            web_mentions: Web mentions/articles
            cv_data: CV data
            skills_scores: Already-scored skills (optional)

        Returns:
            Dict containing:
                - overall_quality_score: 0-100
                - profile_completeness: 0-100
                - data_richness: poor|fair|good|excellent
                - technical_depth: low|medium|high|exceptional
                - professional_presence: low|medium|high|exceptional
                - strengths: List of key strengths
                - areas_for_improvement: List of gaps
                - summary: Overall assessment
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._fallback_profile_quality()

        try:
            context = self._prepare_comprehensive_context(
                github_data, linkedin_data, web_mentions, cv_data
            )

            # Add skills summary if available
            if skills_scores:
                skills_summary = self._summarize_skills_scores(skills_scores)
                context += f"\n\nSkills Assessment Summary:\n{skills_summary}"

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a senior technical recruiter evaluating a candidate's overall profile quality.

Analyze the COMPLETENESS, DEPTH, and CREDIBILITY of the candidate's professional profile.

Consider:
1. **Data Completeness**: How much quality data is available across sources?
2. **Technical Depth**: Evidence of real technical expertise vs surface-level claims
3. **Professional Presence**: Online visibility, community contributions, thought leadership
4. **Consistency**: Do different sources tell the same story?
5. **Recency**: Is the profile active and up-to-date?
6. **Verifiability**: Can claims be verified through code, articles, projects?

Return a JSON object:
{
  "overall_quality_score": 85,
  "profile_completeness": 90,
  "data_richness": "excellent",
  "technical_depth": "high",
  "professional_presence": "high",
  "activity_level": "very_active|active|moderate|low",
  "strengths": [
    "Strong GitHub presence with well-documented projects",
    "Active contributor to open source"
  ],
  "areas_for_improvement": [
    "Limited web presence and articles",
    "LinkedIn profile could be more detailed"
  ],
  "red_flags": [
    "Any concerning inconsistencies or gaps"
  ],
  "summary": "2-3 sentence overall assessment",
  "hirability_score": 85,
  "recommended_for": ["senior engineer", "tech lead"],
  "data_sources_quality": {
    "github": "excellent|good|fair|poor|missing",
    "linkedin": "excellent|good|fair|poor|missing",
    "web_mentions": "excellent|good|fair|poor|missing",
    "cv": "excellent|good|fair|poor|missing"
  }
}

Be HONEST and CRITICAL."""
                    },
                    {
                        "role": "user",
                        "content": f"Evaluate this candidate's profile:\n\n{context}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            result["evaluated_at"] = datetime.now().isoformat()

            logger.info(f"Profile quality score: {result.get('overall_quality_score', 0)}")
            return result

        except Exception as e:
            logger.error(f"Error calculating profile quality: {e}")
            return self._fallback_profile_quality()

    def _prepare_skill_context(
        self,
        skill_name: str,
        github_data: Optional[Dict[str, Any]],
        linkedin_data: Optional[Dict[str, Any]],
        web_mentions: Optional[List[Dict[str, Any]]],
        cv_data: Optional[Dict[str, Any]]
    ) -> str:
        """Prepare focused context for a specific skill"""
        context_parts = []
        context_parts.append(f"SKILL TO EVALUATE: {skill_name}\n")

        # CV mentions
        if cv_data:
            context_parts.append("=== CV/RESUME DATA ===")
            if cv_data.get('skills'):
                if skill_name.lower() in [s.lower() for s in cv_data['skills']]:
                    context_parts.append(f"✓ '{skill_name}' explicitly listed in CV")
            if cv_data.get('work_history'):
                context_parts.append(f"\nWork History: {len(cv_data['work_history'])} positions")
                for job in cv_data['work_history'][:3]:
                    context_parts.append(f"- {job.get('title')} at {job.get('company')}")

        # GitHub evidence
        if github_data:
            context_parts.append("\n=== GITHUB EVIDENCE ===")

            # Check if skill appears in languages
            if github_data.get('languages'):
                skill_lower = skill_name.lower()
                for lang, count in github_data['languages'].items():
                    if skill_lower in lang.lower() or lang.lower() in skill_lower:
                        context_parts.append(f"✓ Used in {count} repositories (primary language)")

            # Check README samples
            if github_data.get('readme_samples'):
                skill_mentions = []
                for readme in github_data['readme_samples']:
                    content = readme.get('content', '').lower()
                    if skill_name.lower() in content:
                        skill_mentions.append(f"- {readme['repo_name']}: {readme.get('repo_description', '')[:100]}")

                if skill_mentions:
                    context_parts.append(f"\n✓ Mentioned in {len(skill_mentions)} project READMEs:")
                    context_parts.extend(skill_mentions[:3])

            # Check commit messages
            if github_data.get('commit_samples'):
                skill_commits = [
                    c for c in github_data['commit_samples']
                    if skill_name.lower() in c.get('message', '').lower()
                ]
                if skill_commits:
                    context_parts.append(f"\n✓ Found in {len(skill_commits)} commit messages")
                    for commit in skill_commits[:3]:
                        context_parts.append(f"  - {commit['message'][:80]}...")

            # Commit statistics
            if github_data.get('commit_statistics'):
                stats = github_data['commit_statistics']
                context_parts.append(f"\nCommit Activity: {stats.get('commit_frequency', 'unknown')}")

        # LinkedIn evidence
        if linkedin_data:
            context_parts.append("\n=== LINKEDIN EVIDENCE ===")

            # Check skills list
            if linkedin_data.get('skills'):
                if skill_name.lower() in [s.lower() for s in linkedin_data['skills']]:
                    context_parts.append(f"✓ Listed in LinkedIn skills")

            # Check experience descriptions
            if linkedin_data.get('experience'):
                for exp in linkedin_data['experience']:
                    desc = exp.get('description', '').lower()
                    if skill_name.lower() in desc:
                        context_parts.append(f"✓ Mentioned in {exp.get('title')} role")

            # Check headline/summary
            if linkedin_data.get('headline'):
                if skill_name.lower() in linkedin_data['headline'].lower():
                    context_parts.append(f"✓ Featured in professional headline")

        # Web mentions
        if web_mentions:
            skill_articles = [
                m for m in web_mentions
                if skill_name.lower() in m.get('title', '').lower() or
                   skill_name.lower() in m.get('content', '').lower()
            ]
            if skill_articles:
                context_parts.append(f"\n=== WEB MENTIONS ({len(skill_articles)} found) ===")
                for article in skill_articles[:2]:
                    context_parts.append(f"- {article.get('title')}")
                    context_parts.append(f"  {article.get('snippet', '')[:150]}...")

        return "\n".join(context_parts)

    def _prepare_comprehensive_context(
        self,
        github_data: Optional[Dict[str, Any]],
        linkedin_data: Optional[Dict[str, Any]],
        web_mentions: Optional[List[Dict[str, Any]]],
        cv_data: Optional[Dict[str, Any]]
    ) -> str:
        """Prepare comprehensive context for profile-wide analysis"""
        context_parts = []

        # GitHub section
        if github_data:
            context_parts.append("=== GITHUB PROFILE ===")
            context_parts.append(f"Username: {github_data.get('username')}")
            context_parts.append(f"Public Repos: {github_data.get('public_repos', 0)}")
            context_parts.append(f"Followers: {github_data.get('followers', 0)}")

            if github_data.get('bio'):
                context_parts.append(f"Bio: {github_data['bio']}")

            if github_data.get('languages'):
                context_parts.append(f"\nLanguages: {dict(list(github_data['languages'].items())[:5])}")

            # README samples
            if github_data.get('readme_samples'):
                context_parts.append(f"\n--- README Samples ({len(github_data['readme_samples'])} projects) ---")
                for readme in github_data['readme_samples'][:3]:
                    context_parts.append(f"\n{readme['repo_name']} ({readme.get('stars', 0)} ⭐)")
                    context_parts.append(f"{readme['content'][:300]}...")

            # Commit samples
            if github_data.get('commit_samples'):
                context_parts.append(f"\n--- Recent Commits (sample of {len(github_data['commit_samples'])}) ---")
                for commit in github_data['commit_samples'][:10]:
                    context_parts.append(f"- {commit['message'][:100]}")

            # Commit stats
            if github_data.get('commit_statistics'):
                stats = github_data['commit_statistics']
                context_parts.append(f"\n--- Commit Patterns ---")
                context_parts.append(f"Frequency: {stats.get('commit_frequency')}")
                context_parts.append(f"Uses conventional commits: {stats.get('has_conventional_commits')}")

        # LinkedIn section
        if linkedin_data:
            context_parts.append("\n\n=== LINKEDIN PROFILE ===")
            context_parts.append(f"Name: {linkedin_data.get('full_name')}")
            if linkedin_data.get('headline'):
                context_parts.append(f"Headline: {linkedin_data['headline']}")
            if linkedin_data.get('summary'):
                context_parts.append(f"Summary: {linkedin_data['summary'][:300]}...")

            if linkedin_data.get('experience'):
                context_parts.append(f"\nExperience: {len(linkedin_data['experience'])} positions")
                for exp in linkedin_data['experience'][:3]:
                    context_parts.append(f"- {exp.get('title')} at {exp.get('company')}")

            if linkedin_data.get('skills'):
                context_parts.append(f"\nSkills: {', '.join(linkedin_data['skills'][:10])}")

        # Web mentions section
        if web_mentions:
            context_parts.append(f"\n\n=== WEB MENTIONS ({len(web_mentions)} found) ===")
            for mention in web_mentions[:3]:
                context_parts.append(f"\n- {mention.get('title')}")
                context_parts.append(f"  Source: {mention.get('source_name')}")
                context_parts.append(f"  {mention.get('snippet', '')[:200]}...")

        # CV section
        if cv_data:
            context_parts.append("\n\n=== CV/RESUME ===")
            if cv_data.get('skills'):
                context_parts.append(f"Listed Skills: {', '.join(cv_data['skills'][:15])}")
            if cv_data.get('work_history'):
                context_parts.append(f"\nWork History: {len(cv_data['work_history'])} positions")

        return "\n".join(context_parts)

    def _summarize_skills_scores(self, skills_scores: List[Dict[str, Any]]) -> str:
        """Create a summary of skills scores for profile quality analysis"""
        if not skills_scores:
            return "No skills scored yet"

        avg_confidence = sum(s.get('confidence_score', 0) for s in skills_scores) / len(skills_scores)

        by_proficiency = {}
        for s in skills_scores:
            level = s.get('proficiency_level', 'unknown')
            by_proficiency[level] = by_proficiency.get(level, 0) + 1

        high_confidence = [s for s in skills_scores if s.get('confidence_score', 0) >= 80]

        summary = [
            f"Total Skills Assessed: {len(skills_scores)}",
            f"Average Confidence: {avg_confidence:.1f}%",
            f"High Confidence Skills (80+%): {len(high_confidence)}",
            f"Proficiency Distribution: {by_proficiency}"
        ]

        return "\n".join(summary)

    def _fallback_skill_score(self, skill_name: str) -> Dict[str, Any]:
        """Fallback scoring when GPT is unavailable"""
        return {
            "skill": skill_name,
            "confidence_score": 50,
            "proficiency_level": "intermediate",
            "years_experience": 2,
            "evidence_quality": "medium",
            "reasoning": "GPT analysis unavailable - using fallback score",
            "data_sources_used": [],
            "key_evidence": [],
            "red_flags": ["Analysis unavailable"],
            "scored_at": datetime.now().isoformat()
        }

    def _fallback_profile_quality(self) -> Dict[str, Any]:
        """Fallback profile quality when GPT is unavailable"""
        return {
            "overall_quality_score": 50,
            "profile_completeness": 50,
            "data_richness": "fair",
            "technical_depth": "medium",
            "professional_presence": "medium",
            "activity_level": "moderate",
            "strengths": ["Profile data available"],
            "areas_for_improvement": ["Analysis unavailable"],
            "red_flags": [],
            "summary": "Profile quality analysis unavailable",
            "hirability_score": 50,
            "recommended_for": ["software engineer"],
            "data_sources_quality": {},
            "evaluated_at": datetime.now().isoformat()
        }


# Singleton instance
_gpt_scoring_service = None

def get_gpt_scoring_service() -> GPTScoringService:
    """Get or create the GPT scoring service singleton"""
    global _gpt_scoring_service
    if _gpt_scoring_service is None:
        _gpt_scoring_service = GPTScoringService()
    return _gpt_scoring_service
