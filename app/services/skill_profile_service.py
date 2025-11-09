"""
Skill Profile Service
Builds comprehensive skill profiles with categorization and relationships
"""
from typing import Dict, List, Optional, Any
from collections import defaultdict
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.services.skill_validation_service import get_validation_service
from app.services.skill_normalization import get_normalization_service

logger = logging.getLogger(__name__)


class SkillProfileService:
    """
    Builds comprehensive skill profiles from validated skills.

    Creates structured skill profiles with:
    - Skill categorization by domain
    - Skill relationships and clusters
    - Proficiency levels
    - Professional summaries
    """

    def __init__(self):
        """Initialize skill profile service"""
        self.validation_service = get_validation_service()
        self.normalizer = get_normalization_service()

    def build_skill_profile(
        self,
        submission_id: UUID,
        db: Session
    ) -> Dict[str, Any]:
        """
        Build a comprehensive skill profile for a submission.

        Args:
            submission_id: CV submission ID
            db: Database session

        Returns:
            Complete skill profile with categorization and analysis
        """
        logger.info(f"Building skill profile for submission {submission_id}")

        # Get validated skills
        validation_results = self.validation_service.validate_submission_skills(
            submission_id, db
        )

        # Build profile components
        profile = {
            "submission_id": str(submission_id),
            "profile_metadata": {
                "total_skills": validation_results["total_skills_validated"],
                "overall_confidence": validation_results["profile_confidence"]["overall_confidence"],
                "confidence_distribution": validation_results["profile_confidence"]["distribution"]
            },
            "skills_by_category": self._categorize_skills(
                validation_results["validated_skills"]
            ),
            "skills_by_confidence": self._group_by_confidence(
                validation_results["validated_skills"]
            ),
            "skill_relationships": self._identify_skill_relationships(
                validation_results["validated_skills"]
            ),
            "top_skills": self._identify_top_skills(
                validation_results["validated_skills"]
            ),
            "professional_summary": self._generate_professional_summary(
                validation_results
            ),
            "skill_gaps": self._identify_skill_gaps(
                validation_results["validated_skills"]
            ),
            "recommended_learning": self._recommend_learning_paths(
                validation_results["validated_skills"]
            )
        }

        logger.info(f"Skill profile built with {profile['profile_metadata']['total_skills']} skills "
                   f"across {len(profile['skills_by_category'])} categories")

        return profile

    def _categorize_skills(
        self,
        validated_skills: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize skills by domain"""
        categories = defaultdict(list)

        for skill_data in validated_skills:
            skill = skill_data["skill"]
            category = skill_data.get("category", "other")

            categories[category].append({
                "skill": skill,
                "confidence_score": skill_data["confidence_score"],
                "confidence_level": skill_data["confidence_level"],
                "sources": skill_data["sources"]
            })

        # Sort skills within each category by confidence
        for category in categories:
            categories[category].sort(
                key=lambda x: x["confidence_score"],
                reverse=True
            )

        # Convert to regular dict and add metadata
        result = {}
        for category, skills in categories.items():
            result[category] = {
                "category_name": self._get_category_display_name(category),
                "skill_count": len(skills),
                "average_confidence": sum(s["confidence_score"] for s in skills) / len(skills),
                "skills": skills
            }

        return result

    def _group_by_confidence(
        self,
        validated_skills: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Group skills by confidence level"""
        groups = {
            "expert": [],
            "high": [],
            "medium": [],
            "low": []
        }

        for skill_data in validated_skills:
            level = skill_data["confidence_level"]
            if level in groups:
                groups[level].append(skill_data["skill"])

        return groups

    def _identify_skill_relationships(
        self,
        validated_skills: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify relationships between skills.

        For example:
        - React + TypeScript (commonly used together)
        - Python + Django (framework relationship)
        - AWS + Docker + Kubernetes (DevOps stack)
        """
        relationships = []

        # Define common skill combinations
        known_combinations = [
            {
                "name": "React Frontend Stack",
                "skills": ["react", "javascript", "typescript"],
                "relationship": "complementary"
            },
            {
                "name": "Django Backend Stack",
                "skills": ["python", "django", "postgresql"],
                "relationship": "complementary"
            },
            {
                "name": "DevOps Stack",
                "skills": ["docker", "kubernetes", "aws"],
                "relationship": "complementary"
            },
            {
                "name": "Data Science Stack",
                "skills": ["python", "pandas", "numpy", "jupyter"],
                "relationship": "complementary"
            },
            {
                "name": "Machine Learning Stack",
                "skills": ["python", "tensorflow", "pytorch", "scikit-learn"],
                "relationship": "complementary"
            },
            {
                "name": "Full Stack JavaScript",
                "skills": ["javascript", "react", "node.js", "express"],
                "relationship": "complementary"
            }
        ]

        # Get user's skills
        user_skills = set(s["skill"] for s in validated_skills)

        # Find matching combinations
        for combo in known_combinations:
            combo_skills = set(combo["skills"])
            matched_skills = combo_skills & user_skills

            if len(matched_skills) >= 2:  # At least 2 skills from the combo
                relationships.append({
                    "stack_name": combo["name"],
                    "skills_present": list(matched_skills),
                    "skills_missing": list(combo_skills - matched_skills),
                    "completion_rate": len(matched_skills) / len(combo_skills) * 100,
                    "relationship_type": combo["relationship"]
                })

        # Sort by completion rate
        relationships.sort(key=lambda x: x["completion_rate"], reverse=True)

        return relationships

    def _identify_top_skills(
        self,
        validated_skills: List[Dict[str, Any]],
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """Identify top N skills by confidence and source coverage"""
        # Already sorted by confidence in validation
        return validated_skills[:top_n]

    def _generate_professional_summary(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a professional summary of the skill profile"""
        validated_skills = validation_results["validated_skills"]
        profile_confidence = validation_results["profile_confidence"]

        # Count skills by category
        category_counts = defaultdict(int)
        for skill in validated_skills:
            category = skill.get("category", "other")
            category_counts[category] += 1

        # Find dominant categories
        sorted_categories = sorted(
            category_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Identify primary domain
        if sorted_categories:
            primary_domain = sorted_categories[0][0]
            primary_skill_count = sorted_categories[0][1]
        else:
            primary_domain = "unknown"
            primary_skill_count = 0

        # Build summary
        summary = {
            "total_skills": len(validated_skills),
            "primary_domain": self._get_category_display_name(primary_domain),
            "primary_domain_skill_count": primary_skill_count,
            "confidence_breakdown": {
                "expert": profile_confidence["expert_skills"],
                "high": profile_confidence["high_confidence_skills"],
                "medium": profile_confidence["medium_confidence_skills"],
                "low": profile_confidence["low_confidence_skills"]
            },
            "overall_confidence_score": profile_confidence["overall_confidence"],
            "top_categories": [
                {
                    "category": self._get_category_display_name(cat),
                    "skill_count": count
                }
                for cat, count in sorted_categories[:5]
            ],
            "profile_strength": self._assess_profile_strength(profile_confidence),
            "description": self._generate_description_text(
                validated_skills, profile_confidence, sorted_categories
            )
        }

        return summary

    def _identify_skill_gaps(
        self,
        validated_skills: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify potential skill gaps based on common stacks"""
        gaps = []

        # Check common stacks
        user_skills = set(s["skill"] for s in validated_skills)

        # Frontend developer gaps
        if "react" in user_skills or "vue" in user_skills or "angular" in user_skills:
            recommended_frontend = {"typescript", "jest", "webpack", "git"}
            missing = recommended_frontend - user_skills
            if missing:
                gaps.append({
                    "gap_area": "Frontend Development",
                    "missing_skills": list(missing),
                    "priority": "high",
                    "reason": "Common tools for modern frontend development"
                })

        # Backend developer gaps
        if "django" in user_skills or "flask" in user_skills or "fastapi" in user_skills:
            recommended_backend = {"postgresql", "redis", "docker", "git"}
            missing = recommended_backend - user_skills
            if missing:
                gaps.append({
                    "gap_area": "Backend Development",
                    "missing_skills": list(missing),
                    "priority": "high",
                    "reason": "Essential backend infrastructure skills"
                })

        # DevOps gaps
        if "docker" in user_skills or "kubernetes" in user_skills:
            recommended_devops = {"terraform", "jenkins", "aws"}
            missing = recommended_devops - user_skills
            if missing:
                gaps.append({
                    "gap_area": "DevOps",
                    "missing_skills": list(missing),
                    "priority": "medium",
                    "reason": "Complete DevOps toolkit"
                })

        # Data Science gaps
        if "pandas" in user_skills or "numpy" in user_skills:
            recommended_ds = {"jupyter", "scikit-learn", "matplotlib"}
            missing = recommended_ds - user_skills
            if missing:
                gaps.append({
                    "gap_area": "Data Science",
                    "missing_skills": list(missing),
                    "priority": "medium",
                    "reason": "Standard data science tools"
                })

        return gaps

    def _recommend_learning_paths(
        self,
        validated_skills: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Recommend learning paths based on current skills"""
        recommendations = []

        user_skills = set(s["skill"] for s in validated_skills)
        skill_levels = {s["skill"]: s["confidence_level"] for s in validated_skills}

        # Recommend based on existing skills
        learning_paths = [
            {
                "path_name": "Advanced React Development",
                "prerequisite": "react",
                "recommended_skills": ["next.js", "redux", "graphql"],
                "level": "intermediate_to_advanced"
            },
            {
                "path_name": "Full Stack JavaScript",
                "prerequisite": "javascript",
                "recommended_skills": ["node.js", "express", "mongodb"],
                "level": "intermediate"
            },
            {
                "path_name": "Python Data Science",
                "prerequisite": "python",
                "recommended_skills": ["pandas", "numpy", "scikit-learn", "jupyter"],
                "level": "intermediate"
            },
            {
                "path_name": "Machine Learning Engineer",
                "prerequisite": "python",
                "recommended_skills": ["tensorflow", "pytorch", "docker", "aws"],
                "level": "advanced"
            },
            {
                "path_name": "Cloud Infrastructure",
                "prerequisite": "docker",
                "recommended_skills": ["kubernetes", "terraform", "aws"],
                "level": "intermediate_to_advanced"
            }
        ]

        for path in learning_paths:
            if path["prerequisite"] in user_skills:
                # Check how many recommended skills they already have
                recommended = set(path["recommended_skills"])
                already_have = recommended & user_skills
                to_learn = recommended - user_skills

                if to_learn:  # Only recommend if there's something to learn
                    recommendations.append({
                        "learning_path": path["path_name"],
                        "prerequisite_met": path["prerequisite"],
                        "skills_to_learn": list(to_learn),
                        "skills_already_have": list(already_have),
                        "completion_percentage": len(already_have) / len(recommended) * 100,
                        "difficulty_level": path["level"]
                    })

        # Sort by completion percentage (paths they're closest to completing)
        recommendations.sort(key=lambda x: x["completion_percentage"], reverse=True)

        return recommendations

    def _get_category_display_name(self, category: str) -> str:
        """Get display name for category"""
        display_names = {
            "programming_language": "Programming Languages",
            "frontend": "Frontend Development",
            "backend": "Backend Development",
            "database": "Databases",
            "cloud": "Cloud Platforms",
            "devops": "DevOps & Infrastructure",
            "machine_learning": "Machine Learning & AI",
            "testing": "Testing & QA",
            "other": "Other Skills"
        }
        return display_names.get(category, category.replace("_", " ").title())

    def _assess_profile_strength(self, profile_confidence: Dict[str, Any]) -> str:
        """Assess overall profile strength"""
        overall = profile_confidence["overall_confidence"]
        expert_count = profile_confidence["expert_skills"]
        high_count = profile_confidence["high_confidence_skills"]

        if overall >= 85 and expert_count >= 5:
            return "exceptional"
        elif overall >= 75 and (expert_count + high_count) >= 8:
            return "strong"
        elif overall >= 65:
            return "good"
        elif overall >= 50:
            return "developing"
        else:
            return "emerging"

    def _generate_description_text(
        self,
        validated_skills: List[Dict[str, Any]],
        profile_confidence: Dict[str, Any],
        sorted_categories: List[tuple]
    ) -> str:
        """Generate human-readable profile description"""
        total_skills = len(validated_skills)
        expert_count = profile_confidence["expert_skills"]
        high_count = profile_confidence["high_confidence_skills"]
        overall = profile_confidence["overall_confidence"]

        if not sorted_categories:
            return "No validated skills found in profile."

        primary_domain = self._get_category_display_name(sorted_categories[0][0])
        strength = self._assess_profile_strength(profile_confidence)

        description = (
            f"This profile demonstrates {strength} technical expertise with {total_skills} validated skills. "
            f"The primary focus area is {primary_domain}. "
        )

        if expert_count > 0:
            description += f"Shows expert-level proficiency in {expert_count} skill(s). "

        if high_count > 0:
            description += f"Strong competency in {high_count} additional skill(s). "

        description += f"Overall confidence score: {overall:.1f}/100."

        return description


# Singleton instance
_profile_service = None

def get_profile_service() -> SkillProfileService:
    """Get or create the skill profile service singleton"""
    global _profile_service
    if _profile_service is None:
        _profile_service = SkillProfileService()
    return _profile_service
