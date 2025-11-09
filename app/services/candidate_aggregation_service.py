"""
HR Candidate Aggregation Service

Merges all data sources for comprehensive candidate profiles:
- CV data (personal info, work history, education, skills)
- GitHub analysis (professional summary, skills, activity metrics)
- Web mentions (articles, talks, projects)
- Stack Overflow (reputation, expertise areas)
- Aggregated profile (cross-source validation)
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.cv_submission import CVSubmission
from app.models.extracted_data import ExtractedData
from app.models.collected_data import (
    GitHubData,
    GitHubAnalysis,
    WebMention,
    StackOverflowData,
    SkillWebMention,
    AggregatedProfile
)
from app.models.user import User


class CandidateAggregationService:
    """Service for aggregating all candidate data from multiple sources"""

    def __init__(self, db: Session):
        self.db = db

    async def get_all_candidates(self) -> List[Dict[str, Any]]:
        """
        Get all candidates with comprehensive data from all sources

        Returns:
            List of candidate dictionaries with merged data
        """
        # Get all CV submissions with completed processing
        submissions = self.db.execute(
            select(CVSubmission)
            .where(CVSubmission.status.in_(["validated", "completed"]))
        ).scalars().all()

        candidates = []
        for submission in submissions:
            candidate_data = await self.get_candidate_profile(submission.id)
            if candidate_data:
                candidates.append(candidate_data)

        return candidates

    async def get_candidate_profile(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive profile for a single candidate

        Args:
            submission_id: CV submission ID

        Returns:
            Dictionary with all candidate data merged from all sources
        """
        # Get submission
        submission = self.db.execute(
            select(CVSubmission).where(CVSubmission.id == submission_id)
        ).scalar_one_or_none()

        if not submission:
            return None

        # Get user info
        user = self.db.execute(
            select(User).where(User.id == submission.user_id)
        ).scalar_one_or_none()

        # Get all data sources
        extracted_data = self._get_extracted_data(submission_id)
        github_data = self._get_github_data(submission_id)
        github_analysis = self._get_github_analysis(submission_id)
        web_mentions = self._get_web_mentions(submission_id)
        stackoverflow_data = self._get_stackoverflow_data(submission_id)
        skill_web_mentions = self._get_skill_web_mentions(submission_id)
        aggregated_profile = self._get_aggregated_profile(submission_id)

        # Merge all data into comprehensive profile
        profile = {
            "submission_id": submission_id,
            "user_id": submission.user_id,
            "user_email": user.email if user else None,

            # Personal Information (from CV)
            "personal_info": self._extract_personal_info(extracted_data),

            # Professional Summary (AI-generated from GitHub)
            "professional_summary": github_analysis.professional_summary if github_analysis else None,

            # Skills Summary (AI-generated)
            "skills_summary": github_analysis.skill_summary if github_analysis else None,

            # Detailed Skills (from multiple sources)
            "skills": self._merge_skills(extracted_data, github_analysis, stackoverflow_data),

            # Work History & Education (from CV)
            "work_history": extracted_data.work_history if extracted_data else [],
            "education": extracted_data.education if extracted_data else [],
            "certifications": extracted_data.certifications if extracted_data else [],
            "languages": extracted_data.languages if extracted_data else [],

            # GitHub Metrics
            "github_metrics": self._extract_github_metrics(github_data, github_analysis),

            # Web Presence
            "web_presence": self._extract_web_presence(web_mentions, skill_web_mentions, aggregated_profile),

            # Stack Overflow Expertise
            "stackoverflow_expertise": self._extract_stackoverflow_expertise(stackoverflow_data),

            # Strengths & Growth Areas (AI-generated)
            "strengths": github_analysis.strengths if github_analysis else [],
            "areas_for_growth": github_analysis.areas_for_growth if github_analysis else [],

            # Recommended Roles (AI-generated)
            "recommended_roles": github_analysis.recommended_roles if github_analysis else [],

            # Quality Scores
            "quality_scores": self._extract_quality_scores(aggregated_profile, github_analysis),

            # Raw data for detailed analysis
            "raw_data": {
                "cv_extraction_confidence": float(extracted_data.overall_confidence) if extracted_data and extracted_data.overall_confidence else None,
                "github_username": github_data.username if github_data else None,
                "stackoverflow_username": stackoverflow_data.username if stackoverflow_data else None,
                "total_web_mentions": len(web_mentions),
                "total_skill_mentions": len(skill_web_mentions),
            }
        }

        return profile

    def _get_extracted_data(self, submission_id: str) -> Optional[ExtractedData]:
        """Get extracted CV data"""
        return self.db.execute(
            select(ExtractedData).where(ExtractedData.submission_id == submission_id)
        ).scalar_one_or_none()

    def _get_github_data(self, submission_id: str) -> Optional[GitHubData]:
        """Get GitHub profile data (most recent if duplicates exist)"""
        return self.db.execute(
            select(GitHubData)
            .where(GitHubData.submission_id == submission_id)
            .order_by(GitHubData.collected_at.desc())
        ).scalars().first()

    def _get_github_analysis(self, submission_id: str) -> Optional[GitHubAnalysis]:
        """Get GPT-4o GitHub analysis (most recent if duplicates exist)"""
        return self.db.execute(
            select(GitHubAnalysis)
            .where(GitHubAnalysis.submission_id == submission_id)
            .order_by(GitHubAnalysis.analyzed_at.desc())
        ).scalars().first()

    def _get_web_mentions(self, submission_id: str) -> List[WebMention]:
        """Get all web mentions"""
        return list(self.db.execute(
            select(WebMention).where(WebMention.submission_id == submission_id)
        ).scalars().all())

    def _get_stackoverflow_data(self, submission_id: str) -> Optional[StackOverflowData]:
        """Get Stack Overflow profile data (most recent if duplicates exist)"""
        return self.db.execute(
            select(StackOverflowData)
            .where(StackOverflowData.submission_id == submission_id)
            .order_by(StackOverflowData.collected_at.desc())
        ).scalars().first()

    def _get_skill_web_mentions(self, submission_id: str) -> List[SkillWebMention]:
        """Get skill-specific web mentions"""
        return list(self.db.execute(
            select(SkillWebMention).where(SkillWebMention.submission_id == submission_id)
        ).scalars().all())

    def _get_aggregated_profile(self, submission_id: str) -> Optional[AggregatedProfile]:
        """Get aggregated profile (most recent if duplicates exist)"""
        return self.db.execute(
            select(AggregatedProfile)
            .where(AggregatedProfile.submission_id == submission_id)
            .order_by(AggregatedProfile.last_aggregated_at.desc())
        ).scalars().first()

    def _extract_personal_info(self, extracted_data: Optional[ExtractedData]) -> Dict[str, Any]:
        """Extract personal information from CV data"""
        if not extracted_data:
            return {}

        return {
            "name": extracted_data.full_name,
            "email": extracted_data.email,
            "phone": extracted_data.phone,
            "location": extracted_data.location,
            "github_url": extracted_data.github_url,
            "linkedin_url": extracted_data.linkedin_url,
            "portfolio_url": extracted_data.portfolio_url,
            "twitter_url": extracted_data.twitter_url,
        }

    def _merge_skills(
        self,
        extracted_data: Optional[ExtractedData],
        github_analysis: Optional[GitHubAnalysis],
        stackoverflow_data: Optional[StackOverflowData]
    ) -> Dict[str, Any]:
        """Merge skills from all sources"""
        skills = {
            "technical_skills": [],
            "frameworks": [],
            "languages": [],
            "tools": [],
            "domains": [],
            "soft_skills": [],
            "cv_skills": [],
            "stackoverflow_tags": []
        }

        # From GitHub Analysis (GPT-4o)
        if github_analysis:
            skills["technical_skills"] = github_analysis.technical_skills or []
            skills["frameworks"] = github_analysis.frameworks or []
            skills["languages"] = github_analysis.languages or []
            skills["tools"] = github_analysis.tools or []
            skills["domains"] = github_analysis.domains or []
            skills["soft_skills"] = github_analysis.soft_skills or []

        # From CV
        if extracted_data and extracted_data.skills:
            skills["cv_skills"] = extracted_data.skills

        # From Stack Overflow
        if stackoverflow_data and stackoverflow_data.skills_from_tags:
            skills["stackoverflow_tags"] = stackoverflow_data.skills_from_tags

        return skills

    def _extract_github_metrics(
        self,
        github_data: Optional[GitHubData],
        github_analysis: Optional[GitHubAnalysis]
    ) -> Dict[str, Any]:
        """Extract GitHub activity metrics"""
        if not github_data and not github_analysis:
            return {}

        metrics = {}

        if github_data:
            metrics.update({
                "username": github_data.username,
                "bio": github_data.bio,
                "location": github_data.location,
                "company": github_data.company,
                "public_repos": github_data.public_repos,
                "followers": github_data.followers,
                "following": github_data.following,
                "contributions_last_year": github_data.contributions_last_year,
                "top_languages": github_data.languages,
            })

        if github_analysis:
            metrics.update({
                "activity_level": github_analysis.activity_level,
                "commit_quality_score": github_analysis.commit_quality_score,
                "contribution_consistency": github_analysis.contribution_consistency,
                "collaboration_score": github_analysis.collaboration_score,
                "project_diversity": github_analysis.project_diversity,
                "activity_insights": github_analysis.activity_insights,
                "commit_quality_insights": github_analysis.commit_quality_insights,
                "collaboration_insights": github_analysis.collaboration_insights,
                "project_insights": github_analysis.project_insights,
            })

        return metrics

    def _extract_web_presence(
        self,
        web_mentions: List[WebMention],
        skill_web_mentions: List[SkillWebMention],
        aggregated_profile: Optional[AggregatedProfile]
    ) -> Dict[str, Any]:
        """Extract web presence information"""
        presence = {
            "total_web_mentions": len(web_mentions),
            "total_skill_mentions": len(skill_web_mentions),
            "articles": [],
            "talks": [],
            "projects": [],
        }

        # Categorize web mentions
        for mention in web_mentions:
            item = {
                "title": mention.title,
                "url": mention.url,
                "source": mention.source_name,
                "published_date": str(mention.published_date) if mention.published_date else None,
                "snippet": mention.snippet,
            }

            if mention.source_type in ["article", "blog"]:
                presence["articles"].append(item)
            elif mention.source_type in ["talk", "conference", "podcast"]:
                presence["talks"].append(item)
            elif mention.source_type in ["project", "portfolio"]:
                presence["projects"].append(item)

        # Add aggregated metrics
        if aggregated_profile:
            presence.update({
                "github_contributions": aggregated_profile.github_contributions,
                "web_mentions_count": aggregated_profile.web_mentions_count,
                "conferences_spoken": aggregated_profile.conferences_spoken,
                "articles_published": aggregated_profile.articles_published,
            })

        return presence

    def _extract_stackoverflow_expertise(
        self,
        stackoverflow_data: Optional[StackOverflowData]
    ) -> Optional[Dict[str, Any]]:
        """Extract Stack Overflow expertise"""
        if not stackoverflow_data:
            return None

        return {
            "username": stackoverflow_data.username,
            "reputation": stackoverflow_data.reputation,
            "badges": {
                "gold": stackoverflow_data.gold_badges,
                "silver": stackoverflow_data.silver_badges,
                "bronze": stackoverflow_data.bronze_badges,
            },
            "activity": {
                "total_questions": stackoverflow_data.total_questions,
                "total_answers": stackoverflow_data.total_answers,
                "accepted_answers": stackoverflow_data.accepted_answers,
                "upvotes_received": stackoverflow_data.upvotes_received,
                "activity_level": stackoverflow_data.activity_level,
                "posts_per_month_avg": float(stackoverflow_data.posts_per_month_avg) if stackoverflow_data.posts_per_month_avg else None,
            },
            "top_tags": stackoverflow_data.top_tags or [],
            "expertise_areas": stackoverflow_data.skills_from_tags or [],
        }

    def _extract_quality_scores(
        self,
        aggregated_profile: Optional[AggregatedProfile],
        github_analysis: Optional[GitHubAnalysis]
    ) -> Dict[str, Any]:
        """Extract quality and confidence scores"""
        scores = {}

        if aggregated_profile:
            scores.update({
                "overall_quality_score": float(aggregated_profile.overall_quality_score) if aggregated_profile.overall_quality_score else None,
                "data_freshness_score": float(aggregated_profile.data_freshness_score) if aggregated_profile.data_freshness_score else None,
                "collection_completeness": float(aggregated_profile.collection_completeness) if aggregated_profile.collection_completeness else None,
                "sources_collected": aggregated_profile.sources_collected,
            })

        if github_analysis:
            scores.update({
                "commit_quality_score": github_analysis.commit_quality_score,
                "collaboration_score": github_analysis.collaboration_score,
                "project_diversity": github_analysis.project_diversity,
            })

        return scores

    async def get_candidates_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about all candidates

        Returns:
            Dictionary with aggregate statistics
        """
        total_candidates = self.db.execute(
            select(CVSubmission)
            .where(CVSubmission.status.in_(["validated", "completed"]))
        ).scalars().all()

        return {
            "total_candidates": len(total_candidates),
            "candidates_with_github": self.db.execute(
                select(GitHubData)
            ).scalars().all().__len__(),
            "candidates_with_stackoverflow": self.db.execute(
                select(StackOverflowData)
            ).scalars().all().__len__(),
            "total_web_mentions": self.db.execute(
                select(WebMention)
            ).scalars().all().__len__(),
        }
