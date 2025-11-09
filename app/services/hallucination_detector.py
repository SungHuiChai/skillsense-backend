"""
Hallucination Detector Service
Identifies potentially false or exaggerated skills from AI analysis
"""
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class HallucinationDetectorService:
    """
    Service for detecting skill hallucinations and false positives.

    Hallucination indicators:
    - Skills mentioned only in AI analysis but not in actual data
    - Skills with no concrete evidence in repositories or activity
    - Overly generic or vague skill names
    - Skills inconsistent with the person's profile
    - Skills from only one weak source
    """

    # Known vague/generic skills that often indicate hallucinations
    VAGUE_SKILLS = {
        "coding", "programming", "software", "development", "technology",
        "computer science", "it", "web", "mobile", "desktop",
        "frontend", "backend", "fullstack", "data", "analytics",
        "management", "leadership", "communication", "teamwork",
        "problem solving", "critical thinking", "agile", "scrum"
    }

    # Skills that should have concrete evidence
    REQUIRES_EVIDENCE = {
        "machine learning", "deep learning", "artificial intelligence",
        "blockchain", "cryptocurrency", "quantum computing",
        "embedded systems", "robotics", "iot",
        "cybersecurity", "penetration testing", "ethical hacking"
    }

    def __init__(self):
        """Initialize hallucination detector"""
        pass

    def analyze_skill(
        self,
        skill: str,
        sources: Dict[str, bool],
        evidence: Optional[Dict[str, any]] = None,
        profile_context: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """
        Analyze a single skill for hallucination indicators.

        Args:
            skill: Skill name
            sources: Dict of sources where skill was found
            evidence: Evidence data (repos, commits, articles, etc.)
            profile_context: Overall profile context

        Returns:
            Analysis result with hallucination risk assessment
        """
        risk_score = 0
        risk_factors = []
        is_hallucination = False

        # Factor 1: Single source only (especially if AI-generated)
        source_count = sum(1 for found in sources.values() if found)
        if source_count == 1:
            risk_score += 30
            risk_factors.append({
                "factor": "single_source",
                "severity": "medium",
                "description": "Skill found in only one source"
            })

        # Factor 2: Not in CV but in AI analysis
        if not sources.get("cv", False):
            # If also not in GitHub but in web/AI analysis
            if not sources.get("github", False):
                risk_score += 40
                risk_factors.append({
                    "factor": "no_primary_source",
                    "severity": "high",
                    "description": "Skill not found in CV or GitHub (primary sources)"
                })
            else:
                risk_score += 15
                risk_factors.append({
                    "factor": "not_in_cv",
                    "severity": "low",
                    "description": "Skill found in secondary sources but not in CV"
                })

        # Factor 3: Vague/generic skill
        if self._is_vague_skill(skill):
            risk_score += 25
            risk_factors.append({
                "factor": "vague_skill",
                "severity": "medium",
                "description": f"'{skill}' is a generic/vague skill name"
            })

        # Factor 4: High-level skill with no evidence
        if self._requires_evidence(skill):
            has_evidence = self._check_evidence(evidence)
            if not has_evidence:
                risk_score += 35
                risk_factors.append({
                    "factor": "no_evidence",
                    "severity": "high",
                    "description": f"'{skill}' requires concrete evidence but none found"
                })

        # Factor 5: Inconsistent with profile
        if profile_context:
            is_inconsistent = self._check_profile_inconsistency(skill, profile_context)
            if is_inconsistent:
                risk_score += 20
                risk_factors.append({
                    "factor": "profile_inconsistency",
                    "severity": "medium",
                    "description": "Skill seems inconsistent with overall profile"
                })

        # Factor 6: No recent activity
        if evidence:
            last_activity = evidence.get("last_activity_date")
            if last_activity:
                days_old = self._get_days_since_activity(last_activity)
                if days_old > 365:  # More than 1 year
                    risk_score += 15
                    risk_factors.append({
                        "factor": "stale_skill",
                        "severity": "low",
                        "description": f"No activity in {days_old} days (may be outdated)"
                    })

        # Determine if it's likely a hallucination
        if risk_score >= 60:
            is_hallucination = True
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        elif risk_score >= 20:
            risk_level = "low"
        else:
            risk_level = "minimal"

        return {
            "skill": skill,
            "is_hallucination": is_hallucination,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendation": self._get_recommendation(risk_score, risk_level)
        }

    def analyze_skill_list(
        self,
        skills_with_sources: Dict[str, Dict[str, bool]],
        evidence_map: Optional[Dict[str, Dict[str, any]]] = None,
        profile_context: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """
        Analyze a list of skills for hallucinations.

        Args:
            skills_with_sources: Dict mapping skills to their sources
            evidence_map: Dict mapping skills to their evidence
            profile_context: Overall profile context

        Returns:
            Analysis results for all skills
        """
        results = []
        hallucination_count = 0
        high_risk_count = 0
        medium_risk_count = 0

        for skill, sources in skills_with_sources.items():
            evidence = evidence_map.get(skill) if evidence_map else None

            analysis = self.analyze_skill(
                skill=skill,
                sources=sources,
                evidence=evidence,
                profile_context=profile_context
            )

            results.append(analysis)

            if analysis["is_hallucination"]:
                hallucination_count += 1

            if analysis["risk_level"] == "high":
                high_risk_count += 1
            elif analysis["risk_level"] == "medium":
                medium_risk_count += 1

        # Sort by risk score (highest first)
        results.sort(key=lambda x: x["risk_score"], reverse=True)

        return {
            "total_skills": len(skills_with_sources),
            "hallucination_count": hallucination_count,
            "high_risk_count": high_risk_count,
            "medium_risk_count": medium_risk_count,
            "hallucination_rate": round(hallucination_count / len(skills_with_sources) * 100, 2) if skills_with_sources else 0,
            "skill_analyses": results,
            "flagged_skills": [r["skill"] for r in results if r["is_hallucination"]],
            "suspicious_skills": [r["skill"] for r in results if r["risk_level"] in ["high", "medium"]]
        }

    def _is_vague_skill(self, skill: str) -> bool:
        """Check if skill is vague/generic"""
        skill_lower = skill.lower().strip()
        return skill_lower in self.VAGUE_SKILLS

    def _requires_evidence(self, skill: str) -> bool:
        """Check if skill requires concrete evidence"""
        skill_lower = skill.lower().strip()
        return skill_lower in self.REQUIRES_EVIDENCE

    def _check_evidence(self, evidence: Optional[Dict[str, any]]) -> bool:
        """
        Check if there's concrete evidence for the skill.

        Evidence includes:
        - Repository with relevant code
        - Commits mentioning the technology
        - Articles written about it
        - Stack Overflow answers
        """
        if not evidence:
            return False

        # Check for various types of evidence
        has_repos = evidence.get("repository_count", 0) > 0
        has_commits = evidence.get("commit_count", 0) > 0
        has_articles = evidence.get("articles_written", 0) > 0
        has_stackoverflow = evidence.get("stackoverflow_score", 0) > 0

        return has_repos or has_commits or has_articles or has_stackoverflow

    def _check_profile_inconsistency(
        self,
        skill: str,
        profile_context: Dict[str, any]
    ) -> bool:
        """
        Check if skill is inconsistent with overall profile.

        For example:
        - Frontend skill in a backend-heavy profile
        - ML skill with no Python/R in profile
        - Mobile skill with no Swift/Kotlin
        """
        skill_lower = skill.lower()

        # Get profile's main skills
        main_skills = set()
        if "main_skills" in profile_context:
            main_skills = {s.lower() for s in profile_context["main_skills"]}

        # ML/DS skills require Python/R
        ml_keywords = ["machine learning", "deep learning", "tensorflow", "pytorch", "keras"]
        if any(keyword in skill_lower for keyword in ml_keywords):
            if not any(lang in main_skills for lang in ["python", "r", "julia"]):
                return True

        # Mobile skills require mobile languages
        mobile_keywords = ["ios", "android", "mobile", "swift", "kotlin"]
        if any(keyword in skill_lower for keyword in mobile_keywords):
            if not any(lang in main_skills for lang in ["swift", "kotlin", "java", "react native", "flutter"]):
                return True

        # Blockchain skills require relevant languages
        blockchain_keywords = ["blockchain", "solidity", "smart contract", "ethereum"]
        if any(keyword in skill_lower for keyword in blockchain_keywords):
            if not any(lang in main_skills for lang in ["solidity", "rust", "go", "javascript"]):
                return True

        return False

    def _get_days_since_activity(self, last_activity: any) -> int:
        """Calculate days since last activity"""
        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            except Exception:
                return 999  # Assume very old if can't parse

        if isinstance(last_activity, datetime):
            now = datetime.now(last_activity.tzinfo) if last_activity.tzinfo else datetime.now()
            return (now - last_activity).days

        return 999

    def _get_recommendation(self, risk_score: int, risk_level: str) -> str:
        """Get recommendation based on risk score"""
        if risk_score >= 60:
            return "EXCLUDE - Likely hallucination, exclude from profile"
        elif risk_score >= 40:
            return "FLAG - Requires manual review and verification"
        elif risk_score >= 20:
            return "VERIFY - Include but mark as unverified"
        else:
            return "INCLUDE - Low risk, safe to include"

    def filter_hallucinations(
        self,
        analysis_results: Dict[str, any],
        exclude_threshold: int = 60
    ) -> List[str]:
        """
        Filter out likely hallucinations from skill list.

        Args:
            analysis_results: Results from analyze_skill_list
            exclude_threshold: Risk score threshold for exclusion

        Returns:
            List of validated skills (hallucinations removed)
        """
        validated_skills = []

        for analysis in analysis_results["skill_analyses"]:
            if analysis["risk_score"] < exclude_threshold:
                validated_skills.append(analysis["skill"])

        return validated_skills

    def get_validation_report(
        self,
        analysis_results: Dict[str, any]
    ) -> str:
        """
        Generate a human-readable validation report.

        Args:
            analysis_results: Results from analyze_skill_list

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("SKILL VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Total Skills Analyzed: {analysis_results['total_skills']}")
        report.append(f"Likely Hallucinations: {analysis_results['hallucination_count']}")
        report.append(f"High Risk Skills: {analysis_results['high_risk_count']}")
        report.append(f"Medium Risk Skills: {analysis_results['medium_risk_count']}")
        report.append(f"Hallucination Rate: {analysis_results['hallucination_rate']}%")
        report.append("")

        if analysis_results["flagged_skills"]:
            report.append("FLAGGED AS HALLUCINATIONS:")
            for skill in analysis_results["flagged_skills"]:
                report.append(f"  - {skill}")
            report.append("")

        if analysis_results["suspicious_skills"]:
            report.append("SUSPICIOUS SKILLS (REQUIRE VERIFICATION):")
            for skill in analysis_results["suspicious_skills"]:
                if skill not in analysis_results["flagged_skills"]:
                    report.append(f"  - {skill}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)


# Singleton instance
_hallucination_detector = None

def get_hallucination_detector() -> HallucinationDetectorService:
    """Get or create the hallucination detector service singleton"""
    global _hallucination_detector
    if _hallucination_detector is None:
        _hallucination_detector = HallucinationDetectorService()
    return _hallucination_detector
