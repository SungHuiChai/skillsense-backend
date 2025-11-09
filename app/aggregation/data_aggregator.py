"""
Data Aggregator
Combines and validates data from multiple sources.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
import logging
import asyncio

from app.models.cv_submission import CVSubmission
from app.models.extracted_data import ExtractedData
from app.models.collected_data import (
    CollectedSource,
    GitHubData,
    WebMention,
    LinkedInData,
    AggregatedProfile
)
from app.services.gpt_scoring_service import get_gpt_scoring_service

logger = logging.getLogger(__name__)


class DataAggregator:
    """Aggregates data from multiple sources into a unified profile"""

    def __init__(self, db: Session, use_gpt_quality: bool = True):
        """
        Initialize aggregator with database session.

        Args:
            db: SQLAlchemy database session
            use_gpt_quality: If True, use GPT for profile quality assessment
        """
        self.db = db
        self.use_gpt_quality = use_gpt_quality
        self.gpt_scorer = get_gpt_scoring_service() if use_gpt_quality else None

    async def aggregate(self, submission_id: str) -> AggregatedProfile:
        """
        Aggregate data from all sources for a submission.

        Args:
            submission_id: Submission UUID

        Returns:
            AggregatedProfile instance
        """
        logger.info(f"Starting aggregation for submission: {submission_id}")

        # Get all data sources
        extracted_data = self.db.query(ExtractedData).filter(
            ExtractedData.submission_id == submission_id
        ).first()

        github_data = self.db.query(GitHubData).filter(
            GitHubData.submission_id == submission_id
        ).first()

        web_mentions = self.db.query(WebMention).filter(
            WebMention.submission_id == submission_id
        ).all()

        linkedin_data = self.db.query(LinkedInData).filter(
            LinkedInData.submission_id == submission_id
        ).first()

        sources = self.db.query(CollectedSource).filter(
            CollectedSource.submission_id == submission_id
        ).all()

        # Aggregate personal information
        verified_name = self._aggregate_name(extracted_data, github_data)
        verified_email = self._aggregate_email(extracted_data, github_data)
        verified_location = self._aggregate_location(extracted_data, github_data)

        # Calculate consistency scores
        name_consistency = self._calculate_name_consistency(
            extracted_data,
            github_data
        )
        location_consistency = self._calculate_location_consistency(
            extracted_data,
            github_data
        )

        # Aggregate skills
        all_skills = self._aggregate_skills(extracted_data, github_data, web_mentions)
        skills_cross_validated = self._count_cross_validated_skills(all_skills)

        # Calculate metrics
        sources_collected = sum(1 for s in sources if s.status == 'completed')
        total_sources = len(sources)
        completeness = (sources_collected / total_sources * 100) if total_sources > 0 else 0

        # External visibility metrics
        github_contributions = github_data.public_repos if github_data else 0
        web_mentions_count = len(web_mentions)

        # Quality scores (GPT or legacy)
        if self.use_gpt_quality and self.gpt_scorer:
            # Use GPT for comprehensive profile quality assessment
            gpt_quality = asyncio.run(self._calculate_gpt_profile_quality(
                github_data,
                linkedin_data,
                web_mentions,
                extracted_data
            ))
            overall_quality = gpt_quality.get("overall_quality_score", 50.0)
            data_freshness = gpt_quality.get("data_freshness", 50.0)
        else:
            # Use legacy mathematical quality calculation
            overall_quality = self._calculate_legacy_quality(
                completeness,
                name_consistency,
                location_consistency,
                github_data,
                web_mentions
            )
            data_freshness = self._calculate_freshness_score(github_data, web_mentions)

        # Create or update aggregated profile
        aggregated = self.db.query(AggregatedProfile).filter(
            AggregatedProfile.submission_id == submission_id
        ).first()

        if aggregated:
            # Update existing
            aggregated.verified_name = verified_name
            aggregated.verified_email = verified_email
            aggregated.verified_location = verified_location
            aggregated.sources_collected = sources_collected
            aggregated.total_sources_attempted = total_sources
            aggregated.collection_completeness = Decimal(str(completeness))
            aggregated.name_consistency_score = Decimal(str(name_consistency))
            aggregated.location_consistency_score = Decimal(str(location_consistency))
            aggregated.skills_cross_validated = skills_cross_validated
            aggregated.all_skills = all_skills
            aggregated.github_contributions = github_contributions
            aggregated.web_mentions_count = web_mentions_count
            aggregated.overall_quality_score = Decimal(str(overall_quality))
            aggregated.data_freshness_score = Decimal(str(data_freshness))
            aggregated.last_aggregated_at = datetime.utcnow()
        else:
            # Create new
            aggregated = AggregatedProfile(
                submission_id=submission_id,
                verified_name=verified_name,
                verified_email=verified_email,
                verified_location=verified_location,
                sources_collected=sources_collected,
                total_sources_attempted=total_sources,
                collection_completeness=Decimal(str(completeness)),
                name_consistency_score=Decimal(str(name_consistency)),
                location_consistency_score=Decimal(str(location_consistency)),
                skills_cross_validated=skills_cross_validated,
                all_skills=all_skills,
                github_contributions=github_contributions,
                linkedin_connections=0,  # Not implemented yet
                web_mentions_count=web_mentions_count,
                conferences_spoken=0,  # Not implemented yet
                articles_published=0,  # Not implemented yet
                overall_quality_score=Decimal(str(overall_quality)),
                data_freshness_score=Decimal(str(data_freshness))
            )
            self.db.add(aggregated)

        self.db.commit()
        logger.info(f"Aggregation completed for submission: {submission_id}")
        return aggregated

    def _aggregate_name(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData]
    ) -> Optional[str]:
        """
        Aggregate name from multiple sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data

        Returns:
            Best name or None
        """
        # Priority: CV extracted name > GitHub name
        if extracted_data and extracted_data.full_name:
            return extracted_data.full_name
        if github_data and github_data.name:
            return github_data.name
        return None

    def _aggregate_email(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData]
    ) -> Optional[str]:
        """
        Aggregate email from multiple sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data

        Returns:
            Best email or None
        """
        # Priority: CV extracted email > GitHub email
        if extracted_data and extracted_data.email:
            return extracted_data.email
        if github_data and github_data.email:
            return github_data.email
        return None

    def _aggregate_location(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData]
    ) -> Optional[str]:
        """
        Aggregate location from multiple sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data

        Returns:
            Best location or None
        """
        # Priority: CV extracted location > GitHub location
        if extracted_data and extracted_data.location:
            return extracted_data.location
        if github_data and github_data.location:
            return github_data.location
        return None

    def _calculate_name_consistency(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData]
    ) -> float:
        """
        Calculate name consistency across sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data

        Returns:
            Consistency score (0-100)
        """
        names = []
        if extracted_data and extracted_data.full_name:
            names.append(extracted_data.full_name.lower().strip())
        if github_data and github_data.name:
            names.append(github_data.name.lower().strip())

        if len(names) < 2:
            return 100.0  # Only one source, perfect consistency

        # Simple string matching
        if names[0] == names[1]:
            return 100.0

        # Check if one name is contained in another (e.g., "John Smith" vs "John A. Smith")
        if names[0] in names[1] or names[1] in names[0]:
            return 90.0

        # Check if first and last names match
        parts1 = names[0].split()
        parts2 = names[1].split()
        if parts1[0] == parts2[0] and parts1[-1] == parts2[-1]:
            return 80.0

        return 50.0  # Names are different

    def _calculate_location_consistency(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData]
    ) -> float:
        """
        Calculate location consistency across sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data

        Returns:
            Consistency score (0-100)
        """
        locations = []
        if extracted_data and extracted_data.location:
            locations.append(extracted_data.location.lower().strip())
        if github_data and github_data.location:
            locations.append(github_data.location.lower().strip())

        if len(locations) < 2:
            return 100.0  # Only one source

        if locations[0] == locations[1]:
            return 100.0

        # Check if one location is contained in another
        if locations[0] in locations[1] or locations[1] in locations[0]:
            return 85.0

        return 50.0  # Different locations

    def _aggregate_skills(
        self,
        extracted_data: Optional[ExtractedData],
        github_data: Optional[GitHubData],
        web_mentions: List[WebMention]
    ) -> List[Dict[str, Any]]:
        """
        Aggregate skills from all sources.

        Args:
            extracted_data: Extracted data from CV
            github_data: GitHub data
            web_mentions: List of web mentions

        Returns:
            List of skill dictionaries
        """
        all_skills = []
        skill_names_seen = set()

        # Add skills from CV
        if extracted_data and extracted_data.skills:
            for skill in extracted_data.skills:
                skill_name = skill.get('name', '').lower()
                if skill_name and skill_name not in skill_names_seen:
                    all_skills.append({
                        'name': skill.get('name'),
                        'category': 'cv_skill',
                        'source': 'cv',
                        'confidence': 90
                    })
                    skill_names_seen.add(skill_name)

        # Add skills from GitHub
        if github_data:
            # Programming languages
            for lang in (github_data.languages or {}).keys():
                lang_lower = lang.lower()
                if lang_lower not in skill_names_seen:
                    all_skills.append({
                        'name': lang,
                        'category': 'programming_language',
                        'source': 'github',
                        'confidence': 85
                    })
                    skill_names_seen.add(lang_lower)

            # Technologies
            for tech in (github_data.technologies or []):
                tech_lower = tech.lower()
                if tech_lower not in skill_names_seen:
                    all_skills.append({
                        'name': tech,
                        'category': 'technology',
                        'source': 'github',
                        'confidence': 80
                    })
                    skill_names_seen.add(tech_lower)

            # Frameworks
            for framework in (github_data.frameworks or []):
                framework_lower = framework.lower()
                if framework_lower not in skill_names_seen:
                    all_skills.append({
                        'name': framework,
                        'category': 'framework',
                        'source': 'github',
                        'confidence': 80
                    })
                    skill_names_seen.add(framework_lower)

        logger.info(f"Aggregated {len(all_skills)} unique skills from all sources")
        return all_skills

    def _count_cross_validated_skills(self, all_skills: List[Dict[str, Any]]) -> int:
        """
        Count skills found in multiple sources.

        Args:
            all_skills: List of skill dictionaries

        Returns:
            Number of cross-validated skills
        """
        skill_sources = {}
        for skill in all_skills:
            name = skill['name'].lower()
            source = skill['source']
            if name not in skill_sources:
                skill_sources[name] = set()
            skill_sources[name].add(source)

        # Count skills found in more than one source
        cross_validated = sum(1 for sources in skill_sources.values() if len(sources) > 1)
        return cross_validated

    async def _calculate_gpt_profile_quality(
        self,
        github_data: Optional[GitHubData],
        linkedin_data: Optional[LinkedInData],
        web_mentions: List[WebMention],
        extracted_data: Optional[ExtractedData]
    ) -> Dict[str, Any]:
        """
        Calculate profile quality using GPT-4o analysis.

        Args:
            github_data: GitHub data with enhanced fields
            linkedin_data: LinkedIn profile data
            web_mentions: List of web mentions
            extracted_data: CV extracted data

        Returns:
            Dictionary with quality metrics from GPT
        """
        logger.info("Calculating profile quality using GPT")

        # Prepare data for GPT scoring
        github_dict = None
        if github_data:
            github_dict = {
                "username": github_data.username,
                "name": github_data.name,
                "bio": github_data.bio,
                "public_repos": github_data.public_repos,
                "followers": github_data.followers,
                "languages": github_data.languages,
                "repositories": github_data.repositories,
                "readme_samples": github_data.readme_samples,
                "commit_samples": github_data.commit_samples,
                "commit_statistics": github_data.commit_statistics
            }

        linkedin_dict = None
        if linkedin_data:
            linkedin_dict = {
                "full_name": linkedin_data.full_name,
                "headline": linkedin_data.headline,
                "summary": linkedin_data.summary,
                "experience": linkedin_data.experience,
                "skills": linkedin_data.skills,
                "education": linkedin_data.education
            }

        web_mentions_list = []
        if web_mentions:
            web_mentions_list = [
                {
                    "title": m.title,
                    "url": m.url,
                    "snippet": m.snippet,
                    "source_name": m.source_name,
                    "source_type": m.source_type
                }
                for m in web_mentions
            ]

        cv_dict = None
        if extracted_data:
            skills_data = extracted_data.skills
            if isinstance(skills_data, list):
                skills = [s.get("name") if isinstance(s, dict) else s for s in skills_data]
            elif isinstance(skills_data, dict):
                skills = skills_data.get("technical_skills", [])
            else:
                skills = []

            cv_dict = {
                "skills": skills,
                "work_history": extracted_data.work_history,
                "education": extracted_data.education
            }

        # Call GPT scoring service
        gpt_result = await self.gpt_scorer.calculate_profile_quality(
            github_data=github_dict,
            linkedin_data=linkedin_dict,
            web_mentions=web_mentions_list,
            cv_data=cv_dict
        )

        # Extract relevant metrics
        return {
            "overall_quality_score": gpt_result.get("overall_quality_score", 50.0),
            "profile_completeness": gpt_result.get("profile_completeness", 50.0),
            "technical_depth": gpt_result.get("technical_depth", "medium"),
            "professional_presence": gpt_result.get("professional_presence", "medium"),
            "activity_level": gpt_result.get("activity_level", "moderate"),
            "data_freshness": 80.0,  # Default freshness for recent collection
            "hirability_score": gpt_result.get("hirability_score", 50.0),
            "strengths": gpt_result.get("strengths", []),
            "areas_for_improvement": gpt_result.get("areas_for_improvement", []),
            "summary": gpt_result.get("summary", "")
        }

    def _calculate_legacy_quality(
        self,
        completeness: float,
        name_consistency: float,
        location_consistency: float,
        github_data: Optional[GitHubData],
        web_mentions: List[WebMention]
    ) -> float:
        """
        Calculate overall data quality score using legacy mathematical formula.

        Args:
            completeness: Collection completeness percentage
            name_consistency: Name consistency score
            location_consistency: Location consistency score
            github_data: GitHub data
            web_mentions: List of web mentions

        Returns:
            Overall quality score (0-100)
        """
        score = 0.0

        # Completeness (30%)
        score += completeness * 0.3

        # Consistency (30%)
        avg_consistency = (name_consistency + location_consistency) / 2
        score += avg_consistency * 0.3

        # GitHub data quality (20%)
        if github_data:
            github_quality = min(100, (github_data.public_repos or 0) * 2)
            score += github_quality * 0.2

        # Web mentions quality (20%)
        if web_mentions:
            avg_relevance = sum(
                float(m.relevance_score or 0) for m in web_mentions
            ) / len(web_mentions)
            score += avg_relevance * 0.2

        return round(score, 2)

    def _calculate_freshness_score(
        self,
        github_data: Optional[GitHubData],
        web_mentions: List[WebMention]
    ) -> float:
        """
        Calculate data freshness score based on recency.

        Args:
            github_data: GitHub data
            web_mentions: List of web mentions

        Returns:
            Freshness score (0-100)
        """
        score = 0.0
        count = 0

        # GitHub data is always fresh (just collected)
        if github_data:
            score += 100
            count += 1

        # Web mentions freshness (based on published date if available)
        if web_mentions:
            mention_freshness = 80  # Default if no date available
            score += mention_freshness
            count += 1

        return round(score / count, 2) if count > 0 else 50.0
