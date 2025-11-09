"""
Confidence Calculator Service
Implements the confidence scoring algorithm for cross-source skill validation
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ConfidenceCalculatorService:
    """
    Service for calculating confidence scores for skills based on multiple sources.

    Scoring Algorithm:
    - CV only: 60%
    - CV + GitHub: 75%
    - CV + GitHub + Web: 90%
    - All sources (CV + GitHub + Web + Stack Overflow) + mentions: 95%

    Bonuses:
    - Endorsements: +5%
    - Web articles written: +5%
    - Recent activity (< 6 months): +5-10%
    """

    # Base confidence scores
    BASE_SCORES = {
        "cv_only": 60,
        "cv_github": 75,
        "cv_github_web": 90,
        "all_sources": 95
    }

    # Bonus scores
    BONUS_ENDORSEMENTS = 5
    BONUS_ARTICLES = 5
    BONUS_RECENT_ACTIVITY_MIN = 5
    BONUS_RECENT_ACTIVITY_MAX = 10

    def __init__(self):
        """Initialize confidence calculator"""
        pass

    def calculate_skill_confidence(
        self,
        skill: str,
        sources: Dict[str, bool],
        evidence: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """
        Calculate confidence score for a single skill.

        Args:
            skill: Skill name
            sources: Dict indicating which sources confirmed the skill
                {
                    "cv": bool,
                    "github": bool,
                    "web_mentions": bool,
                    "stackoverflow": bool,
                    "blog": bool
                }
            evidence: Additional evidence data
                {
                    "endorsements": int,
                    "articles_written": int,
                    "last_activity_date": datetime,
                    "stackoverflow_score": int,
                    "github_commits": int,
                    "web_mentions_count": int
                }

        Returns:
            Dict with confidence score and breakdown
        """
        if not sources:
            return {
                "skill": skill,
                "confidence_score": 0,
                "confidence_level": "none",
                "base_score": 0,
                "bonuses": {},
                "total_bonus": 0,
                "sources_found": []
            }

        # Determine base score
        base_score = self._calculate_base_score(sources)

        # Calculate bonuses
        bonuses = {}
        total_bonus = 0

        if evidence:
            # Endorsement bonus
            if evidence.get("endorsements", 0) > 0:
                bonuses["endorsements"] = self.BONUS_ENDORSEMENTS
                total_bonus += self.BONUS_ENDORSEMENTS

            # Articles bonus
            if evidence.get("articles_written", 0) > 0:
                bonuses["articles"] = self.BONUS_ARTICLES
                total_bonus += self.BONUS_ARTICLES

            # Recent activity bonus
            activity_bonus = self._calculate_activity_bonus(evidence)
            if activity_bonus > 0:
                bonuses["recent_activity"] = activity_bonus
                total_bonus += activity_bonus

        # Final confidence score (capped at 100)
        final_score = min(base_score + total_bonus, 100)

        # Determine confidence level
        confidence_level = self._get_confidence_level(final_score)

        # List of sources found
        sources_found = [source for source, found in sources.items() if found]

        return {
            "skill": skill,
            "confidence_score": final_score,
            "confidence_level": confidence_level,
            "base_score": base_score,
            "bonuses": bonuses,
            "total_bonus": total_bonus,
            "sources_found": sources_found,
            "source_count": len(sources_found)
        }

    def _calculate_base_score(self, sources: Dict[str, bool]) -> int:
        """
        Calculate base confidence score based on source combinations.

        Priority order (highest score wins):
        1. All sources (CV + GitHub + Web + Stack Overflow): 95%
        2. CV + GitHub + Web: 90%
        3. CV + GitHub: 75%
        4. CV only: 60%
        """
        has_cv = sources.get("cv", False)
        has_github = sources.get("github", False)
        has_web = sources.get("web_mentions", False) or sources.get("blog", False)
        has_stackoverflow = sources.get("stackoverflow", False)

        # All sources present
        if has_cv and has_github and has_web and has_stackoverflow:
            return self.BASE_SCORES["all_sources"]

        # CV + GitHub + Web (but not Stack Overflow)
        if has_cv and has_github and has_web:
            return self.BASE_SCORES["cv_github_web"]

        # CV + GitHub (but not web)
        if has_cv and has_github:
            return self.BASE_SCORES["cv_github"]

        # CV only
        if has_cv:
            return self.BASE_SCORES["cv_only"]

        # If no CV but other sources exist, give partial credit
        # GitHub alone: 50%
        # Web alone: 40%
        # Stack Overflow alone: 45%
        if has_github and not has_cv:
            return 50
        if has_web and not has_cv:
            return 40
        if has_stackoverflow and not has_cv:
            return 45

        # Multiple sources but no CV
        if (has_github or has_web or has_stackoverflow):
            return 55

        return 0

    def _calculate_activity_bonus(self, evidence: Dict[str, any]) -> int:
        """
        Calculate bonus for recent activity.

        Recent activity (< 6 months): +5 to +10 bonus
        - Very recent (< 3 months): +10
        - Recent (3-6 months): +5
        - Old (> 6 months): +0
        """
        last_activity = evidence.get("last_activity_date")

        if not last_activity:
            return 0

        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            except Exception:
                return 0

        now = datetime.now(last_activity.tzinfo) if last_activity.tzinfo else datetime.now()
        days_since_activity = (now - last_activity).days

        # Very recent: < 90 days (3 months)
        if days_since_activity < 90:
            return self.BONUS_RECENT_ACTIVITY_MAX

        # Recent: 90-180 days (3-6 months)
        if days_since_activity < 180:
            return self.BONUS_RECENT_ACTIVITY_MIN

        # Old: > 180 days
        return 0

    def _get_confidence_level(self, score: int) -> str:
        """
        Convert numeric score to confidence level label.

        Levels:
        - expert: 90-100%
        - high: 75-89%
        - medium: 60-74%
        - low: 40-59%
        - very_low: < 40%
        """
        if score >= 90:
            return "expert"
        elif score >= 75:
            return "high"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "low"
        else:
            return "very_low"

    def calculate_profile_confidence(
        self,
        skills_data: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Calculate overall profile confidence based on all skills.

        Args:
            skills_data: List of skill confidence data

        Returns:
            Profile-level confidence metrics
        """
        if not skills_data:
            return {
                "overall_confidence": 0,
                "total_skills": 0,
                "expert_skills": 0,
                "high_confidence_skills": 0,
                "medium_confidence_skills": 0,
                "low_confidence_skills": 0,
                "average_score": 0,
                "distribution": {}
            }

        total_skills = len(skills_data)
        scores = [s["confidence_score"] for s in skills_data]
        average_score = sum(scores) / total_skills if total_skills > 0 else 0

        # Count by confidence level
        expert_count = len([s for s in skills_data if s["confidence_level"] == "expert"])
        high_count = len([s for s in skills_data if s["confidence_level"] == "high"])
        medium_count = len([s for s in skills_data if s["confidence_level"] == "medium"])
        low_count = len([s for s in skills_data if s["confidence_level"] == "low"])
        very_low_count = len([s for s in skills_data if s["confidence_level"] == "very_low"])

        return {
            "overall_confidence": round(average_score, 2),
            "total_skills": total_skills,
            "expert_skills": expert_count,
            "high_confidence_skills": high_count,
            "medium_confidence_skills": medium_count,
            "low_confidence_skills": low_count,
            "very_low_confidence_skills": very_low_count,
            "average_score": round(average_score, 2),
            "distribution": {
                "expert": expert_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "very_low": very_low_count
            }
        }

    def merge_skill_sources(
        self,
        cv_skills: List[str],
        github_skills: List[str],
        web_skills: List[str],
        stackoverflow_skills: List[str],
        blog_skills: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, bool]]:
        """
        Merge skills from multiple sources and track which sources confirmed each skill.

        Args:
            cv_skills: Skills from CV
            github_skills: Skills from GitHub
            web_skills: Skills from web mentions
            stackoverflow_skills: Skills from Stack Overflow
            blog_skills: Skills from personal blog

        Returns:
            Dict mapping skill names to source presence
        """
        all_skills = set()
        all_skills.update(cv_skills or [])
        all_skills.update(github_skills or [])
        all_skills.update(web_skills or [])
        all_skills.update(stackoverflow_skills or [])
        if blog_skills:
            all_skills.update(blog_skills)

        skill_sources = {}

        for skill in all_skills:
            skill_sources[skill] = {
                "cv": skill in (cv_skills or []),
                "github": skill in (github_skills or []),
                "web_mentions": skill in (web_skills or []),
                "stackoverflow": skill in (stackoverflow_skills or []),
                "blog": skill in (blog_skills or []) if blog_skills else False
            }

        return skill_sources

    def detect_skill_conflicts(
        self,
        skill_sources: Dict[str, Dict[str, bool]],
        min_sources: int = 2
    ) -> List[Dict[str, any]]:
        """
        Detect skills that may be hallucinations or false positives.

        A skill is flagged if:
        - It appears in only 1 source when multiple sources are available
        - It's not in CV but appears in other sources (potential hallucination)

        Args:
            skill_sources: Dict mapping skills to their sources
            min_sources: Minimum sources required to avoid conflict flag

        Returns:
            List of potentially conflicting skills
        """
        conflicts = []

        for skill, sources in skill_sources.items():
            source_count = sum(1 for present in sources.values() if present)

            # Flag if only 1 source
            if source_count == 1:
                only_source = [s for s, present in sources.items() if present][0]

                # Extra suspicious if not in CV
                if not sources.get("cv", False):
                    conflicts.append({
                        "skill": skill,
                        "reason": "single_source_no_cv",
                        "source": only_source,
                        "risk": "high"
                    })
                else:
                    conflicts.append({
                        "skill": skill,
                        "reason": "single_source_only",
                        "source": only_source,
                        "risk": "medium"
                    })

            # Flag if not in CV but in multiple other sources
            elif not sources.get("cv", False) and source_count >= min_sources:
                found_in = [s for s, present in sources.items() if present]
                conflicts.append({
                    "skill": skill,
                    "reason": "missing_from_cv",
                    "sources": found_in,
                    "risk": "low",
                    "note": "Skill found in multiple sources but not in CV - may be genuine but undocumented skill"
                })

        return conflicts


# Singleton instance
_confidence_calculator = None

def get_confidence_calculator() -> ConfidenceCalculatorService:
    """Get or create the confidence calculator service singleton"""
    global _confidence_calculator
    if _confidence_calculator is None:
        _confidence_calculator = ConfidenceCalculatorService()
    return _confidence_calculator
