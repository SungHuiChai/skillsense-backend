"""
Skill Validation Service
Cross-source validation with confidence scoring and hallucination detection
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.services.skill_normalization import get_normalization_service
from app.services.confidence_calculator import get_confidence_calculator
from app.services.hallucination_detector import get_hallucination_detector
from app.models.extracted_data import ExtractedData
from app.models.collected_data import GitHubData, GitHubAnalysis, StackOverflowData, SkillWebMention

logger = logging.getLogger(__name__)


class SkillValidationService:
    """
    Validates skills across multiple sources and calculates confidence scores.

    This service implements the full validation pipeline:
    1. Normalize skills from all sources
    2. Merge and deduplicate
    3. Calculate confidence scores based on source combinations
    4. Detect hallucinations
    5. Generate validated skill profile
    """

    def __init__(self):
        """Initialize validation service with dependencies"""
        self.normalizer = get_normalization_service()
        self.confidence_calc = get_confidence_calculator()
        self.hallucination_detector = get_hallucination_detector()

    def validate_submission_skills(
        self,
        submission_id: UUID,
        db: Session
    ) -> Dict[str, Any]:
        """
        Validate all skills for a submission across all sources.

        Args:
            submission_id: CV submission ID
            db: Database session

        Returns:
            Complete validation results with confidence scores
        """
        logger.info(f"Starting skill validation for submission {submission_id}")

        # 1. Collect skills from all sources
        source_skills = self._collect_skills_from_sources(submission_id, db)

        # 2. Normalize all skills
        normalized_skills = self._normalize_all_skills(source_skills)

        # 3. Build skill-source mapping
        skill_sources = self._build_skill_source_mapping(normalized_skills, source_skills)

        # 4. Gather evidence for each skill
        evidence_map = self._gather_skill_evidence(submission_id, db, skill_sources)

        # 5. Calculate confidence scores
        confidence_results = self._calculate_all_confidence_scores(
            skill_sources, evidence_map
        )

        # 6. Detect hallucinations
        hallucination_results = self.hallucination_detector.analyze_skill_list(
            skill_sources, evidence_map
        )

        # 7. Filter out hallucinations
        validated_skills = self.hallucination_detector.filter_hallucinations(
            hallucination_results, exclude_threshold=60
        )

        # 8. Build final validated skill list with metadata
        final_skills = self._build_final_skill_list(
            validated_skills, confidence_results, skill_sources
        )

        # 9. Calculate profile-level metrics
        profile_confidence = self.confidence_calc.calculate_profile_confidence(
            confidence_results
        )

        results = {
            "submission_id": str(submission_id),
            "validation_timestamp": datetime.now().isoformat(),
            "sources_analyzed": {
                "cv": source_skills["cv"]["found"],
                "github": source_skills["github"]["found"],
                "stackoverflow": source_skills["stackoverflow"]["found"],
                "web_mentions": source_skills["web_mentions"]["found"],
                "blog": source_skills["blog"]["found"]
            },
            "total_skills_raw": len(skill_sources),
            "total_skills_validated": len(validated_skills),
            "skills_filtered_as_hallucinations": hallucination_results["hallucination_count"],
            "profile_confidence": profile_confidence,
            "validated_skills": final_skills,
            "hallucination_report": {
                "flagged_skills": hallucination_results["flagged_skills"],
                "suspicious_skills": hallucination_results["suspicious_skills"],
                "hallucination_rate": hallucination_results["hallucination_rate"]
            }
        }

        logger.info(
            f"Validation complete. {len(validated_skills)}/{len(skill_sources)} skills validated, "
            f"{hallucination_results['hallucination_count']} filtered"
        )

        return results

    def _collect_skills_from_sources(
        self,
        submission_id: UUID,
        db: Session
    ) -> Dict[str, Dict[str, Any]]:
        """Collect skills from all available sources"""
        logger.info("Collecting skills from all sources")

        sources = {
            "cv": {"found": False, "skills": []},
            "github": {"found": False, "skills": []},
            "stackoverflow": {"found": False, "skills": []},
            "web_mentions": {"found": False, "skills": []},
            "blog": {"found": False, "skills": []}
        }

        # CV skills
        extracted_data = db.query(ExtractedData).filter(
            ExtractedData.submission_id == str(submission_id)
        ).first()

        if extracted_data and extracted_data.skills:
            skills_data = extracted_data.skills
            if isinstance(skills_data, list):
                # Extract skill names from list of skill dicts
                cv_skills = [s.get("name") if isinstance(s, dict) else s for s in skills_data]
            elif isinstance(skills_data, dict):
                cv_skills = skills_data.get("technical_skills", [])
            else:
                cv_skills = []

            sources["cv"]["skills"] = cv_skills
            sources["cv"]["found"] = len(cv_skills) > 0

        # GitHub skills
        github_analysis = db.query(GitHubAnalysis).filter(
            GitHubAnalysis.submission_id == str(submission_id)
        ).first()

        if github_analysis:
            github_skills = []
            # Extract from technical_skills
            if github_analysis.technical_skills:
                github_skills.extend([s["name"] for s in github_analysis.technical_skills if isinstance(s, dict)])
            # Extract from frameworks
            if github_analysis.frameworks:
                github_skills.extend([f["name"] if isinstance(f, dict) else f for f in github_analysis.frameworks])
            # Extract from languages
            if github_analysis.languages:
                github_skills.extend([l["name"] if isinstance(l, dict) else l for l in github_analysis.languages])

            sources["github"]["skills"] = github_skills
            sources["github"]["found"] = len(github_skills) > 0

        # Stack Overflow skills
        stackoverflow_data = db.query(StackOverflowData).filter(
            StackOverflowData.submission_id == str(submission_id)
        ).first()

        if stackoverflow_data and stackoverflow_data.skills_from_tags:
            sources["stackoverflow"]["skills"] = stackoverflow_data.skills_from_tags
            sources["stackoverflow"]["found"] = True

        # Web mentions and blog skills
        web_mentions = db.query(SkillWebMention).filter(
            SkillWebMention.submission_id == str(submission_id)
        ).all()

        if web_mentions:
            web_skills = []
            blog_skills = []

            for mention in web_mentions:
                skill = mention.canonical_skill or mention.skill_name
                if mention.source_type == "blog":
                    blog_skills.append(skill)
                else:
                    web_skills.append(skill)

            sources["web_mentions"]["skills"] = list(set(web_skills))
            sources["web_mentions"]["found"] = len(web_skills) > 0

            sources["blog"]["skills"] = list(set(blog_skills))
            sources["blog"]["found"] = len(blog_skills) > 0

        logger.info(f"Collected skills: CV={len(sources['cv']['skills'])}, "
                   f"GitHub={len(sources['github']['skills'])}, "
                   f"SO={len(sources['stackoverflow']['skills'])}, "
                   f"Web={len(sources['web_mentions']['skills'])}, "
                   f"Blog={len(sources['blog']['skills'])}")

        return sources

    def _normalize_all_skills(
        self,
        source_skills: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Normalize skills from each source"""
        normalized = {}

        for source_name, source_data in source_skills.items():
            if source_data["found"]:
                normalized[source_name] = self.normalizer.normalize_skills(
                    source_data["skills"]
                )
            else:
                normalized[source_name] = []

        return normalized

    def _build_skill_source_mapping(
        self,
        normalized_skills: Dict[str, List[str]],
        source_skills: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, bool]]:
        """Build mapping of which sources contain each skill"""
        all_skills = set()
        for skills in normalized_skills.values():
            all_skills.update(skills)

        skill_sources = {}
        for skill in all_skills:
            skill_sources[skill] = {
                "cv": skill in normalized_skills["cv"],
                "github": skill in normalized_skills["github"],
                "stackoverflow": skill in normalized_skills["stackoverflow"],
                "web_mentions": skill in normalized_skills["web_mentions"],
                "blog": skill in normalized_skills["blog"]
            }

        return skill_sources

    def _gather_skill_evidence(
        self,
        submission_id: UUID,
        db: Session,
        skill_sources: Dict[str, Dict[str, bool]]
    ) -> Dict[str, Dict[str, Any]]:
        """Gather evidence for each skill"""
        evidence_map = {}

        # Get GitHub data
        github_data = db.query(GitHubData).filter(
            GitHubData.submission_id == str(submission_id)
        ).first()

        # Get Stack Overflow data
        so_data = db.query(StackOverflowData).filter(
            StackOverflowData.submission_id == str(submission_id)
        ).first()

        # Get web mentions
        web_mentions = db.query(SkillWebMention).filter(
            SkillWebMention.submission_id == str(submission_id)
        ).all()

        for skill in skill_sources.keys():
            evidence = {
                "repository_count": 0,
                "commit_count": 0,
                "articles_written": 0,
                "endorsements": 0,
                "stackoverflow_score": 0,
                "last_activity_date": None
            }

            # GitHub evidence
            if github_data:
                # Count repos using this skill
                if github_data.repositories:
                    for repo in github_data.repositories:
                        repo_lang = repo.get("language") or ""
                        if repo_lang and self.normalizer.normalize_skill(repo_lang.lower()) == skill:
                            evidence["repository_count"] += 1

                # Use collected_at as last activity
                if github_data.collected_at:
                    evidence["last_activity_date"] = github_data.collected_at

            # Stack Overflow evidence
            if so_data and so_data.top_tags:
                for tag_data in so_data.top_tags:
                    if isinstance(tag_data, dict):
                        tag = tag_data.get("tag", "")
                        if self.normalizer.normalize_skill(tag) == skill:
                            evidence["stackoverflow_score"] = tag_data.get("score", 0)

            # Web mention evidence
            skill_mentions = [m for m in web_mentions
                            if (m.canonical_skill == skill or
                                self.normalizer.normalize_skill(m.skill_name) == skill)]

            for mention in skill_mentions:
                if mention.source_type in ["article", "blog"]:
                    evidence["articles_written"] += 1

                # Update last activity if more recent
                if mention.collected_at:
                    if not evidence["last_activity_date"] or \
                       mention.collected_at > evidence["last_activity_date"]:
                        evidence["last_activity_date"] = mention.collected_at

            evidence_map[skill] = evidence

        return evidence_map

    def _calculate_all_confidence_scores(
        self,
        skill_sources: Dict[str, Dict[str, bool]],
        evidence_map: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calculate confidence scores for all skills"""
        results = []

        for skill, sources in skill_sources.items():
            evidence = evidence_map.get(skill, {})
            confidence = self.confidence_calc.calculate_skill_confidence(
                skill=skill,
                sources=sources,
                evidence=evidence
            )
            results.append(confidence)

        return results

    def _build_final_skill_list(
        self,
        validated_skills: List[str],
        confidence_results: List[Dict[str, Any]],
        skill_sources: Dict[str, Dict[str, bool]]
    ) -> List[Dict[str, Any]]:
        """Build final validated skill list with all metadata"""
        final_skills = []

        # Create lookup dict for confidence results
        confidence_lookup = {r["skill"]: r for r in confidence_results}

        for skill in validated_skills:
            confidence_data = confidence_lookup.get(skill, {})
            sources = skill_sources.get(skill, {})

            skill_data = {
                "skill": skill,
                "category": self.normalizer.extract_skill_category(skill),
                "confidence_score": confidence_data.get("confidence_score", 0),
                "confidence_level": confidence_data.get("confidence_level", "unknown"),
                "sources": [s for s, found in sources.items() if found],
                "source_count": sum(1 for found in sources.values() if found),
                "base_score": confidence_data.get("base_score", 0),
                "bonuses": confidence_data.get("bonuses", {}),
                "total_bonus": confidence_data.get("total_bonus", 0)
            }

            final_skills.append(skill_data)

        # Sort by confidence score (highest first)
        final_skills.sort(key=lambda x: x["confidence_score"], reverse=True)

        return final_skills

    def get_skill_details(
        self,
        submission_id: UUID,
        skill_name: str,
        db: Session
    ) -> Dict[str, Any]:
        """Get detailed information about a specific skill"""
        normalized_skill = self.normalizer.normalize_skill(skill_name)

        # Collect evidence from all sources
        evidence = {
            "skill": normalized_skill,
            "synonyms": self.normalizer.find_skill_synonyms(normalized_skill),
            "category": self.normalizer.extract_skill_category(normalized_skill),
            "sources": []
        }

        # Check CV
        extracted_data = db.query(ExtractedData).filter(
            ExtractedData.submission_id == str(submission_id)
        ).first()

        if extracted_data and extracted_data.extracted_skills:
            skills_data = extracted_data.extracted_skills
            if isinstance(skills_data, dict):
                cv_skills = skills_data.get("technical_skills", [])
            else:
                cv_skills = skills_data

            normalized_cv = self.normalizer.normalize_skills(cv_skills)
            if normalized_skill in normalized_cv:
                evidence["sources"].append({
                    "source": "cv",
                    "found": True
                })

        # Check GitHub
        github_analysis = db.query(GitHubAnalysis).filter(
            GitHubAnalysis.submission_id == str(submission_id)
        ).first()

        if github_analysis:
            # Check in technical_skills, frameworks, languages
            github_skills = []
            if github_analysis.technical_skills:
                github_skills.extend([s["name"] for s in github_analysis.technical_skills if isinstance(s, dict)])
            if github_analysis.frameworks:
                github_skills.extend([f["name"] if isinstance(f, dict) else f for f in github_analysis.frameworks])

            normalized_github = self.normalizer.normalize_skills(github_skills)
            if normalized_skill in normalized_github:
                evidence["sources"].append({
                    "source": "github",
                    "found": True,
                    "details": "Found in GitHub analysis"
                })

        # Check Stack Overflow
        so_data = db.query(StackOverflowData).filter(
            StackOverflowData.submission_id == str(submission_id)
        ).first()

        if so_data and so_data.skills_from_tags:
            normalized_so = self.normalizer.normalize_skills(so_data.skills_from_tags)
            if normalized_skill in normalized_so:
                # Find the tag data
                tag_data = None
                for tag in so_data.top_tags or []:
                    if isinstance(tag, dict):
                        if self.normalizer.normalize_skill(tag.get("tag", "")) == normalized_skill:
                            tag_data = tag
                            break

                evidence["sources"].append({
                    "source": "stackoverflow",
                    "found": True,
                    "reputation": so_data.reputation,
                    "tag_data": tag_data
                })

        # Check web mentions
        web_mentions = db.query(SkillWebMention).filter(
            SkillWebMention.submission_id == str(submission_id),
            SkillWebMention.canonical_skill == normalized_skill
        ).all()

        if web_mentions:
            mention_details = []
            for mention in web_mentions:
                mention_details.append({
                    "url": mention.url,
                    "title": mention.title,
                    "source_type": mention.source_type,
                    "credibility": mention.credibility,
                    "credibility_score": float(mention.credibility_score) if mention.credibility_score else None
                })

            evidence["sources"].append({
                "source": "web_mentions",
                "found": True,
                "mention_count": len(web_mentions),
                "mentions": mention_details
            })

        return evidence


# Singleton instance
_validation_service = None

def get_validation_service() -> SkillValidationService:
    """Get or create the skill validation service singleton"""
    global _validation_service
    if _validation_service is None:
        _validation_service = SkillValidationService()
    return _validation_service
