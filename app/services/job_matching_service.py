"""
Job Matching Service using OpenAI GPT-4o

Analyzes candidates against job descriptions and provides detailed matching analysis:
- Match scores (0-100)
- Key strengths relevant to the role
- Potential concerns or gaps
- Overall assessment
- Hiring recommendations
"""
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class JobMatchingService:
    """AI-powered job matching service using GPT-4o"""

    def __init__(self):
        """Initialize OpenAI client"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def match_candidates_to_job(
        self,
        job_description: str,
        candidates: List[Dict[str, Any]],
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Match candidates to a job description using AI analysis

        Args:
            job_description: The job description text
            candidates: List of candidate profiles from CandidateAggregationService
            top_n: Optional limit on number of candidates to return

        Returns:
            Dict containing:
                - job_description: Original job description
                - total_candidates_analyzed: Number of candidates analyzed
                - matches: List of candidates with match analysis
                - analyzed_at: Timestamp
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._fallback_matching(job_description, candidates, top_n)

        if not candidates:
            logger.warning("No candidates provided for matching")
            return {
                "job_description": job_description,
                "total_candidates_analyzed": 0,
                "matches": [],
                "analyzed_at": datetime.now().isoformat(),
                "error": "No candidates available for matching"
            }

        logger.info(f"Matching {len(candidates)} candidates to job description")

        try:
            # Analyze each candidate
            matches = []
            for candidate in candidates:
                analysis = await self._analyze_candidate_match(job_description, candidate)
                if analysis:
                    matches.append({
                        "candidate": self._format_candidate_summary(candidate),
                        "analysis": analysis
                    })

            # Sort by match score (highest first)
            matches.sort(key=lambda x: x["analysis"]["match_score"], reverse=True)

            # Limit results if requested
            if top_n:
                matches = matches[:top_n]

            return {
                "job_description": job_description,
                "total_candidates_analyzed": len(candidates),
                "total_matches_returned": len(matches),
                "matches": matches,
                "analyzed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error matching candidates: {e}")
            return self._fallback_matching(job_description, candidates, top_n)

    async def _analyze_candidate_match(
        self,
        job_description: str,
        candidate: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a single candidate against the job description

        Args:
            job_description: Job description text
            candidate: Candidate profile data

        Returns:
            Dict with match analysis or None if analysis fails
        """
        try:
            # Prepare candidate context
            candidate_context = self._prepare_candidate_context(candidate)

            # Call GPT-4o for analysis
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert technical recruiter and hiring manager analyzing candidate fit for a specific role.

Analyze the candidate's profile against the job description and provide a detailed assessment.

Return a JSON object with:
{
  "match_score": 0-100 (integer score indicating overall fit),
  "recommendation": "Highly Recommended" | "Recommended" | "Maybe" | "Not Recommended",
  "key_strengths": ["strength1", "strength2", "strength3"],
  "relevant_experience": ["experience1", "experience2"],
  "potential_concerns": ["concern1", "concern2"],
  "skill_gaps": ["missing_skill1", "missing_skill2"],
  "cultural_fit_indicators": ["indicator1", "indicator2"],
  "overall_assessment": "2-3 sentences summarizing why this candidate is/isn't a good fit",
  "interview_focus_areas": ["area1", "area2", "area3"],
  "compensation_expectations": "Estimated range or 'Not specified'",
  "availability_concerns": "Any red flags about availability or commitment"
}

Be honest and balanced in your assessment. Highlight both strengths and weaknesses.
Consider technical skills, experience level, cultural fit, and growth potential."""
                    },
                    {
                        "role": "user",
                        "content": f"""Job Description:
{job_description}

---

Candidate Profile:
{candidate_context}

Please analyze this candidate's fit for the role."""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2500
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully analyzed candidate match (Score: {result.get('match_score')})")
            return result

        except Exception as e:
            logger.error(f"Error analyzing candidate match: {e}")
            return self._fallback_candidate_analysis(candidate)

    def _prepare_candidate_context(self, candidate: Dict[str, Any]) -> str:
        """
        Prepare candidate data as formatted context for GPT-4o

        Args:
            candidate: Candidate profile dict

        Returns:
            Formatted string context
        """
        context_parts = []

        # Personal Information
        personal_info = candidate.get("personal_info", {})
        if personal_info.get("name"):
            context_parts.append(f"Name: {personal_info['name']}")
        if personal_info.get("location"):
            context_parts.append(f"Location: {personal_info['location']}")
        if personal_info.get("email"):
            context_parts.append(f"Email: {personal_info['email']}")

        # Professional Summary (AI-generated)
        if candidate.get("professional_summary"):
            context_parts.append(f"\nProfessional Summary:\n{candidate['professional_summary']}")

        # Skills Summary (AI-generated)
        if candidate.get("skills_summary"):
            context_parts.append(f"\nSkills Summary:\n{candidate['skills_summary']}")

        # Detailed Skills
        skills = candidate.get("skills", {})
        if skills:
            context_parts.append("\nTechnical Skills:")

            if skills.get("technical_skills"):
                context_parts.append("\nCore Technical Skills:")
                for skill in skills["technical_skills"][:10]:  # Limit to top 10
                    if isinstance(skill, dict):
                        name = skill.get("name", "")
                        proficiency = skill.get("proficiency", "")
                        context_parts.append(f"  - {name} ({proficiency})")
                    else:
                        context_parts.append(f"  - {skill}")

            if skills.get("languages"):
                context_parts.append("\nProgramming Languages:")
                for lang in skills["languages"][:10]:
                    if isinstance(lang, dict):
                        name = lang.get("name", "")
                        proficiency = lang.get("proficiency", "")
                        projects = lang.get("projects_count", 0)
                        context_parts.append(f"  - {name} ({proficiency}, {projects} projects)")
                    else:
                        context_parts.append(f"  - {lang}")

            if skills.get("frameworks"):
                context_parts.append("\nFrameworks:")
                for fw in skills["frameworks"][:10]:
                    if isinstance(fw, dict):
                        context_parts.append(f"  - {fw.get('name', '')}")
                    else:
                        context_parts.append(f"  - {fw}")

            if skills.get("tools"):
                tools_str = ", ".join(skills["tools"][:15])
                context_parts.append(f"\nTools: {tools_str}")

            if skills.get("domains"):
                domains_str = ", ".join(skills["domains"][:10])
                context_parts.append(f"\nDomain Expertise: {domains_str}")

        # Work History
        work_history = candidate.get("work_history", [])
        if work_history:
            context_parts.append("\nWork Experience:")
            for i, job in enumerate(work_history[:5]):  # Limit to 5 most recent
                company = job.get("company", "Unknown Company")
                title = job.get("title", "Unknown Position")
                dates = f"{job.get('start_date', '')} - {job.get('end_date', 'Present')}"
                context_parts.append(f"\n{i+1}. {title} at {company} ({dates})")
                if job.get("description"):
                    # Truncate long descriptions
                    desc = job["description"][:200] + "..." if len(job["description"]) > 200 else job["description"]
                    context_parts.append(f"   {desc}")

        # Education
        education = candidate.get("education", [])
        if education:
            context_parts.append("\nEducation:")
            for edu in education[:3]:
                institution = edu.get("institution", "Unknown")
                degree = edu.get("degree", "Unknown")
                field = edu.get("field_of_study", "")
                context_parts.append(f"  - {degree} {field} from {institution}".strip())

        # GitHub Metrics
        github = candidate.get("github_metrics", {})
        if github:
            context_parts.append("\nGitHub Activity:")
            if github.get("username"):
                context_parts.append(f"  Username: {github['username']}")
            if github.get("activity_level"):
                context_parts.append(f"  Activity Level: {github['activity_level']}")
            if github.get("commit_quality_score"):
                context_parts.append(f"  Code Quality Score: {github['commit_quality_score']}/100")
            if github.get("collaboration_score"):
                context_parts.append(f"  Collaboration Score: {github['collaboration_score']}/100")
            if github.get("public_repos"):
                context_parts.append(f"  Public Repositories: {github['public_repos']}")
            if github.get("followers"):
                context_parts.append(f"  Followers: {github['followers']}")

        # Stack Overflow
        stackoverflow = candidate.get("stackoverflow_expertise")
        if stackoverflow:
            context_parts.append("\nStack Overflow:")
            context_parts.append(f"  Reputation: {stackoverflow.get('reputation', 0)}")
            if stackoverflow.get('badges'):
                badges = stackoverflow['badges']
                context_parts.append(f"  Badges: {badges.get('gold', 0)} gold, {badges.get('silver', 0)} silver, {badges.get('bronze', 0)} bronze")
            if stackoverflow.get('expertise_areas'):
                areas = ", ".join(stackoverflow['expertise_areas'][:5])
                context_parts.append(f"  Expertise: {areas}")

        # Web Presence
        web_presence = candidate.get("web_presence", {})
        if web_presence:
            total_mentions = web_presence.get("total_web_mentions", 0)
            articles = len(web_presence.get("articles", []))
            talks = len(web_presence.get("talks", []))

            if total_mentions > 0 or articles > 0 or talks > 0:
                context_parts.append("\nOnline Presence:")
                if articles > 0:
                    context_parts.append(f"  - Published {articles} articles/blog posts")
                if talks > 0:
                    context_parts.append(f"  - Given {talks} conference talks/presentations")
                if total_mentions > 0:
                    context_parts.append(f"  - {total_mentions} total web mentions")

        # Strengths and Growth Areas
        if candidate.get("strengths"):
            context_parts.append(f"\nKey Strengths: {', '.join(candidate['strengths'][:5])}")

        if candidate.get("areas_for_growth"):
            context_parts.append(f"\nAreas for Growth: {', '.join(candidate['areas_for_growth'][:3])}")

        # Recommended Roles
        if candidate.get("recommended_roles"):
            context_parts.append(f"\nRecommended Roles: {', '.join(candidate['recommended_roles'][:5])}")

        return "\n".join(context_parts)

    def _format_candidate_summary(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format candidate data for return in match results

        Args:
            candidate: Full candidate profile

        Returns:
            Simplified candidate summary
        """
        personal_info = candidate.get("personal_info", {})

        return {
            "submission_id": candidate.get("submission_id"),
            "name": personal_info.get("name"),
            "email": personal_info.get("email"),
            "location": personal_info.get("location"),
            "github_url": personal_info.get("github_url"),
            "linkedin_url": personal_info.get("linkedin_url"),
            "professional_summary": candidate.get("professional_summary"),
        }

    def _fallback_matching(
        self,
        job_description: str,
        candidates: List[Dict[str, Any]],
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fallback matching without OpenAI (simple scoring)

        Args:
            job_description: Job description
            candidates: List of candidates
            top_n: Optional limit

        Returns:
            Basic match results
        """
        logger.info("Using fallback matching (rule-based)")

        matches = []
        for candidate in candidates:
            analysis = self._fallback_candidate_analysis(candidate)
            matches.append({
                "candidate": self._format_candidate_summary(candidate),
                "analysis": analysis
            })

        # Sort by match score
        matches.sort(key=lambda x: x["analysis"]["match_score"], reverse=True)

        if top_n:
            matches = matches[:top_n]

        return {
            "job_description": job_description,
            "total_candidates_analyzed": len(candidates),
            "total_matches_returned": len(matches),
            "matches": matches,
            "analyzed_at": datetime.now().isoformat(),
            "note": "Fallback matching used (OpenAI not available)"
        }

    def _fallback_candidate_analysis(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback candidate analysis without AI

        Args:
            candidate: Candidate profile

        Returns:
            Basic match analysis
        """
        # Simple scoring based on available data
        score = 50  # Base score

        # Add points for GitHub activity
        github = candidate.get("github_metrics", {})
        if github.get("activity_level") == "very_high":
            score += 15
        elif github.get("activity_level") == "high":
            score += 10

        # Add points for quality scores
        if github.get("commit_quality_score", 0) > 80:
            score += 10

        # Add points for web presence
        web = candidate.get("web_presence", {})
        if web.get("total_web_mentions", 0) > 5:
            score += 10

        # Add points for Stack Overflow
        stackoverflow = candidate.get("stackoverflow_expertise")
        if stackoverflow and stackoverflow.get("reputation", 0) > 1000:
            score += 10

        # Cap at 100
        score = min(score, 100)

        recommendation = "Highly Recommended" if score >= 80 else "Recommended" if score >= 60 else "Maybe"

        return {
            "match_score": score,
            "recommendation": recommendation,
            "key_strengths": ["Active contributor", "Strong technical background"],
            "relevant_experience": ["Software development experience"],
            "potential_concerns": ["Manual analysis - AI not available"],
            "skill_gaps": ["Unable to assess without AI analysis"],
            "cultural_fit_indicators": ["Community engagement"],
            "overall_assessment": f"Candidate shows promise with a match score of {score}/100. Full AI analysis unavailable.",
            "interview_focus_areas": ["Technical skills", "Project experience"],
            "compensation_expectations": "Not specified",
            "availability_concerns": "None identified"
        }
