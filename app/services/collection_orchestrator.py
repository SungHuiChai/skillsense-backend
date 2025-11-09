"""
Collection Orchestrator Service
Coordinates data collection from multiple external sources.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
import asyncio
import logging

from app.models.cv_submission import CVSubmission
from app.models.extracted_data import ExtractedData
from app.models.collected_data import (
    CollectedSource,
    GitHubData,
    WebMention,
    AggregatedProfile
)
from app.scrapers.github_scraper import GitHubScraper
from app.search.tavily_search import TavilySearch
from app.config import settings

logger = logging.getLogger(__name__)


class CollectionOrchestrator:
    """Orchestrates data collection from multiple sources"""

    def __init__(self, db: Session):
        """
        Initialize orchestrator with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

        # Initialize scrapers and search
        scraper_config = {
            'github_token': settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None,
            'rate_limit_delay': 1.0,
            'max_retries': 3,
            'timeout': 30
        }

        search_config = {
            'tavily_api_key': settings.TAVILY_API_KEY if hasattr(settings, 'TAVILY_API_KEY') else None,
            'search_depth': 'advanced',
            'max_results': 10,
            'rate_limit_delay': 1.0,
            'timeout': 30
        }

        try:
            self.github_scraper = GitHubScraper(scraper_config)
            logger.info("GitHub scraper initialized")
        except Exception as e:
            logger.warning(f"GitHub scraper initialization failed: {e}")
            self.github_scraper = None

        try:
            self.tavily_search = TavilySearch(search_config)
            logger.info("Tavily search initialized")
        except Exception as e:
            logger.warning(f"Tavily search initialization failed: {e}")
            self.tavily_search = None

    def get_submission(self, submission_id: str, user_id: str) -> Optional[CVSubmission]:
        """
        Get submission by ID and verify ownership.

        Args:
            submission_id: Submission UUID
            user_id: User UUID

        Returns:
            CVSubmission or None
        """
        return self.db.query(CVSubmission).filter(
            and_(
                CVSubmission.id == submission_id,
                CVSubmission.user_id == user_id
            )
        ).first()

    async def collect_all_sources(self, submission_id: str) -> Dict[str, Any]:
        """
        Collect data from all available sources for a submission.

        Args:
            submission_id: Submission UUID

        Returns:
            Dictionary with collection results
        """
        logger.info(f"Starting data collection for submission: {submission_id}")

        # Get submission and extracted data
        submission = self.db.query(CVSubmission).filter(
            CVSubmission.id == submission_id
        ).first()

        if not submission:
            logger.error(f"Submission not found: {submission_id}")
            return {"error": "Submission not found"}

        extracted_data = self.db.query(ExtractedData).filter(
            ExtractedData.submission_id == submission_id
        ).first()

        if not extracted_data:
            logger.error(f"No extracted data found for submission: {submission_id}")
            return {"error": "No extracted data found"}

        # Identify sources to collect
        sources_to_collect = self._identify_sources(extracted_data)
        logger.info(f"Identified {len(sources_to_collect)} sources to collect")

        # Create collection source records
        for source in sources_to_collect:
            self._create_source_record(submission_id, source)

        self.db.commit()

        # Collect from each source in parallel
        tasks = []
        if 'github' in sources_to_collect:
            tasks.append(self._collect_github(submission_id, sources_to_collect['github']))

        if 'web_search' in sources_to_collect:
            tasks.append(self._collect_web_mentions(submission_id, extracted_data))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Collection completed for {len(results)} sources")
        else:
            logger.warning("No sources available for collection")

        # Phase 3: Trigger web source processing after collection completes
        # Run this BEFORE aggregation so it always executes even if aggregation fails
        try:
            from app.services.web_source_orchestrator import get_web_orchestrator
            logger.info(f"Triggering Phase 3 web source processing for submission: {submission_id}")
            orchestrator = get_web_orchestrator()
            await orchestrator.process_submission(
                submission_id=submission_id,
                db=self.db,
                force_reprocess=False
            )
            logger.info(f"Phase 3 processing completed for submission: {submission_id}")
        except Exception as e:
            logger.error(f"Error in Phase 3 processing: {e}")
            # Don't fail the whole collection if Phase 3 fails

        # Aggregate collected data
        # Wrap in try-except to handle duplicate entry errors gracefully
        try:
            await self._aggregate_data(submission_id)
        except Exception as e:
            logger.error(f"Error during aggregation: {e}")
            # Continue even if aggregation fails (e.g., duplicate entries)

        return {
            "submission_id": submission_id,
            "sources_attempted": len(sources_to_collect),
            "status": "completed"
        }

    def _identify_sources(self, extracted_data: ExtractedData) -> Dict[str, str]:
        """
        Identify which sources are available for collection.

        Args:
            extracted_data: Extracted data from CV

        Returns:
            Dictionary mapping source type to URL
        """
        sources = {}

        # Check for GitHub URL
        if extracted_data.github_url:
            sources['github'] = extracted_data.github_url

        # Always try web search if we have a name
        if extracted_data.full_name:
            sources['web_search'] = extracted_data.full_name

        return sources

    def _create_source_record(self, submission_id: str, source: tuple):
        """
        Create a CollectedSource record.

        Args:
            submission_id: Submission UUID
            source: Tuple of (source_type, source_url)
        """
        source_type, source_url = source if isinstance(source, tuple) else (source, None)

        existing = self.db.query(CollectedSource).filter(
            and_(
                CollectedSource.submission_id == submission_id,
                CollectedSource.source_type == source_type
            )
        ).first()

        if not existing:
            source_record = CollectedSource(
                submission_id=submission_id,
                source_type=source_type,
                source_url=source_url,
                status='pending'
            )
            self.db.add(source_record)
            logger.debug(f"Created source record: {source_type}")

    async def _collect_github(self, submission_id: str, github_url: str) -> Dict[str, Any]:
        """
        Collect data from GitHub.

        Args:
            submission_id: Submission UUID
            github_url: GitHub profile URL

        Returns:
            Collection result dictionary
        """
        logger.info(f"Collecting GitHub data from: {github_url}")

        # Get source record
        source = self.db.query(CollectedSource).filter(
            and_(
                CollectedSource.submission_id == submission_id,
                CollectedSource.source_type == 'github'
            )
        ).first()

        if not source:
            logger.error("GitHub source record not found")
            return {"error": "Source record not found"}

        # Update status
        source.status = 'collecting'
        source.started_at = datetime.utcnow()
        self.db.commit()

        try:
            if not self.github_scraper:
                raise Exception("GitHub scraper not initialized")

            # Scrape GitHub data
            github_data = await self.github_scraper.scrape(github_url)

            # Save to database
            github_record = GitHubData(
                source_id=source.id,
                submission_id=submission_id,
                username=github_data.get('username'),
                name=github_data.get('name'),
                bio=github_data.get('bio'),
                location=github_data.get('location'),
                company=github_data.get('company'),
                blog=github_data.get('blog'),
                email=github_data.get('email'),
                public_repos=github_data.get('public_repos'),
                public_gists=github_data.get('public_gists'),
                followers=github_data.get('followers'),
                following=github_data.get('following'),
                repositories=github_data.get('repositories'),
                languages=github_data.get('languages'),
                top_repos=github_data.get('top_repos'),
                contributions_last_year=github_data.get('contributions_last_year'),
                commit_activity=github_data.get('commit_activity'),
                technologies=github_data.get('technologies'),
                frameworks=github_data.get('frameworks'),
                raw_data=github_data.get('raw_data')
            )
            self.db.add(github_record)

            # Update source status
            source.status = 'completed'
            source.completed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Successfully collected GitHub data for: {github_data.get('username')}")

            # Auto-trigger GPT-4o analysis
            await self._analyze_github_with_ai(submission_id, github_record)

            return {"status": "success", "data": github_data}

        except Exception as e:
            logger.error(f"Error collecting GitHub data: {e}")
            source.status = 'failed'
            source.error_message = str(e)
            source.completed_at = datetime.utcnow()
            self.db.commit()
            return {"status": "failed", "error": str(e)}

    async def _collect_web_mentions(
        self,
        submission_id: str,
        extracted_data: ExtractedData
    ) -> Dict[str, Any]:
        """
        Collect web mentions using Tavily search.

        Args:
            submission_id: Submission UUID
            extracted_data: Extracted data from CV

        Returns:
            Collection result dictionary
        """
        logger.info(f"Collecting web mentions for: {extracted_data.full_name}")

        # Get source record
        source = self.db.query(CollectedSource).filter(
            and_(
                CollectedSource.submission_id == submission_id,
                CollectedSource.source_type == 'web_search'
            )
        ).first()

        if not source:
            logger.error("Web search source record not found")
            return {"error": "Source record not found"}

        # Update status
        source.status = 'collecting'
        source.started_at = datetime.utcnow()
        self.db.commit()

        try:
            if not self.tavily_search:
                raise Exception("Tavily search not initialized")

            # Prepare context
            context = {
                'company': extracted_data.work_history[0].get('company') if extracted_data.work_history else None,
                'skills': [skill.get('name') for skill in (extracted_data.skills or [])[:3]]
            }

            # Search for person
            results = await self.tavily_search.search_person(
                extracted_data.full_name,
                context=context
            )

            # Save web mentions to database
            mentions_saved = 0
            for result in results:
                # Calculate scores
                relevance_score = self.tavily_search.calculate_relevance_score(
                    result,
                    extracted_data.full_name,
                    context.get('skills', [])
                )
                credibility_score = self.tavily_search.calculate_credibility_score(result)

                web_mention = WebMention(
                    source_id=source.id,
                    submission_id=submission_id,
                    title=result.get('title'),
                    url=result.get('url'),
                    snippet=result.get('content'),
                    full_content=result.get('raw_content'),
                    source_name=result.get('source'),
                    source_type='article',  # Default type
                    published_date=None,  # Tavily doesn't always provide this
                    mention_context=result.get('content'),
                    relevance_score=relevance_score,
                    source_credibility_score=credibility_score,
                    raw_data=result
                )
                self.db.add(web_mention)
                mentions_saved += 1

            # Update source status
            source.status = 'completed'
            source.completed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Successfully collected {mentions_saved} web mentions")
            return {"status": "success", "mentions_count": mentions_saved}

        except Exception as e:
            logger.error(f"Error collecting web mentions: {e}")
            source.status = 'failed'
            source.error_message = str(e)
            source.completed_at = datetime.utcnow()
            self.db.commit()
            return {"status": "failed", "error": str(e)}

    async def _aggregate_data(self, submission_id: str):
        """
        Aggregate data from all collected sources.

        Args:
            submission_id: Submission UUID
        """
        logger.info(f"Aggregating data for submission: {submission_id}")

        # Import aggregator here to avoid circular imports
        from app.aggregation.data_aggregator import DataAggregator

        aggregator = DataAggregator(self.db)
        await aggregator.aggregate(submission_id)

    def get_collection_status(self, submission_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get collection status for a submission.

        Args:
            submission_id: Submission UUID
            user_id: User UUID

        Returns:
            Status dictionary or None
        """
        # Verify ownership
        submission = self.get_submission(submission_id, user_id)
        if not submission:
            return None

        # Get all source records
        sources = self.db.query(CollectedSource).filter(
            CollectedSource.submission_id == submission_id
        ).all()

        return {
            "submission_id": submission_id,
            "total_sources": len(sources),
            "sources": [
                {
                    "type": source.source_type,
                    "status": source.status,
                    "started_at": source.started_at.isoformat() if source.started_at else None,
                    "completed_at": source.completed_at.isoformat() if source.completed_at else None,
                    "error": source.error_message
                }
                for source in sources
            ]
        }

    def get_collected_data(self, submission_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get all collected data for a submission.

        Args:
            submission_id: Submission UUID
            user_id: User UUID

        Returns:
            Collected data dictionary or None
        """
        # Verify ownership
        submission = self.get_submission(submission_id, user_id)
        if not submission:
            return None

        # Get GitHub data
        github_data = self.db.query(GitHubData).filter(
            GitHubData.submission_id == submission_id
        ).first()

        # Get web mentions
        web_mentions = self.db.query(WebMention).filter(
            WebMention.submission_id == submission_id
        ).all()

        # Get aggregated profile
        aggregated = self.db.query(AggregatedProfile).filter(
            AggregatedProfile.submission_id == submission_id
        ).first()

        return {
            "submission_id": submission_id,
            "github": {
                "username": github_data.username,
                "name": github_data.name,
                "bio": github_data.bio,
                "location": github_data.location,
                "company": github_data.company,
                "blog": github_data.blog,
                "email": github_data.email,
                "public_repos": github_data.public_repos,
                "public_gists": github_data.public_gists,
                "followers": github_data.followers,
                "following": github_data.following,
                "repositories": github_data.repositories or [],
                "languages": github_data.languages or {},
                "top_repos": github_data.top_repos or [],
                "technologies": github_data.technologies or [],
                "frameworks": github_data.frameworks or [],
                "collected_at": github_data.collected_at.isoformat() if github_data.collected_at else None
            } if github_data else None,
            "web_mentions": [
                {
                    "title": mention.title,
                    "url": mention.url,
                    "source": mention.source_name,
                    "relevance_score": float(mention.relevance_score) if mention.relevance_score else None
                }
                for mention in web_mentions
            ],
            "aggregated": {
                "name": aggregated.verified_name if aggregated else None,
                "skills_count": len(aggregated.all_skills) if aggregated and aggregated.all_skills else 0,
                "overall_quality_score": float(aggregated.overall_quality_score) if aggregated and aggregated.overall_quality_score else None
            } if aggregated else None
        }

    async def _analyze_github_with_ai(self, submission_id: str, github_data):
        """
        Analyze GitHub data with GPT-4o and save results

        Args:
            submission_id: Submission UUID
            github_data: GitHubData model instance
        """
        try:
            from app.services.openai_analyzer import OpenAIAnalyzer
            from app.models.collected_data import GitHubAnalysis

            logger.info(f"Starting GPT-4o analysis for submission {submission_id}")

            # Prepare GitHub data dict
            github_dict = {
                'username': github_data.username,
                'name': github_data.name,
                'bio': github_data.bio,
                'location': github_data.location,
                'company': github_data.company,
                'blog': github_data.blog,
                'email': github_data.email,
                'public_repos': github_data.public_repos,
                'public_gists': github_data.public_gists,
                'followers': github_data.followers,
                'following': github_data.following,
                'repositories': github_data.repositories,
                'languages': github_data.languages,
                'top_repos': github_data.top_repos,
                'technologies': github_data.technologies,
                'frameworks': github_data.frameworks
            }

            # Analyze with OpenAI
            analyzer = OpenAIAnalyzer()
            analysis_result = await analyzer.comprehensive_analysis(github_dict)

            skills_analysis = analysis_result.get('skills_analysis', {})
            activity_analysis = analysis_result.get('activity_analysis', {})

            # Check if analysis already exists for this submission
            existing_analysis = self.db.query(GitHubAnalysis).filter(
                GitHubAnalysis.submission_id == submission_id
            ).first()

            if existing_analysis:
                # Update existing analysis
                logger.info(f"Updating existing GitHub analysis for submission {submission_id}")
                existing_analysis.github_data_id = github_data.id
                existing_analysis.technical_skills = skills_analysis.get('technical_skills')
                existing_analysis.frameworks = skills_analysis.get('frameworks')
                existing_analysis.languages = skills_analysis.get('languages')
                existing_analysis.tools = skills_analysis.get('tools')
                existing_analysis.domains = skills_analysis.get('domains')
                existing_analysis.soft_skills = skills_analysis.get('soft_skills')
                existing_analysis.skill_summary = skills_analysis.get('skill_summary')
                existing_analysis.activity_level = activity_analysis.get('activity_level')
                existing_analysis.commit_quality_score = activity_analysis.get('commit_quality_score')
                existing_analysis.contribution_consistency = activity_analysis.get('contribution_consistency')
                existing_analysis.collaboration_score = activity_analysis.get('collaboration_score')
                existing_analysis.project_diversity = activity_analysis.get('project_diversity')
                existing_analysis.strengths = activity_analysis.get('strengths')
                existing_analysis.areas_for_growth = activity_analysis.get('areas_for_growth')
                existing_analysis.activity_insights = activity_analysis.get('insights', {}).get('activity_insights')
                existing_analysis.commit_quality_insights = activity_analysis.get('insights', {}).get('commit_quality_insights')
                existing_analysis.collaboration_insights = activity_analysis.get('insights', {}).get('collaboration_insights')
                existing_analysis.project_insights = activity_analysis.get('insights', {}).get('project_insights')
                existing_analysis.professional_summary = activity_analysis.get('professional_summary')
                existing_analysis.recommended_roles = activity_analysis.get('recommended_roles')
                existing_analysis.raw_analysis = analysis_result
            else:
                # Create new analysis
                logger.info(f"Creating new GitHub analysis for submission {submission_id}")
                analysis_record = GitHubAnalysis(
                    submission_id=submission_id,
                    github_data_id=github_data.id,
                    # Skills
                    technical_skills=skills_analysis.get('technical_skills'),
                    frameworks=skills_analysis.get('frameworks'),
                    languages=skills_analysis.get('languages'),
                    tools=skills_analysis.get('tools'),
                    domains=skills_analysis.get('domains'),
                    soft_skills=skills_analysis.get('soft_skills'),
                    skill_summary=skills_analysis.get('skill_summary'),
                    # Activity
                    activity_level=activity_analysis.get('activity_level'),
                    commit_quality_score=activity_analysis.get('commit_quality_score'),
                    contribution_consistency=activity_analysis.get('contribution_consistency'),
                    collaboration_score=activity_analysis.get('collaboration_score'),
                    project_diversity=activity_analysis.get('project_diversity'),
                    strengths=activity_analysis.get('strengths'),
                    areas_for_growth=activity_analysis.get('areas_for_growth'),
                    activity_insights=activity_analysis.get('insights', {}).get('activity_insights'),
                    commit_quality_insights=activity_analysis.get('insights', {}).get('commit_quality_insights'),
                    collaboration_insights=activity_analysis.get('insights', {}).get('collaboration_insights'),
                    project_insights=activity_analysis.get('insights', {}).get('project_insights'),
                    professional_summary=activity_analysis.get('professional_summary'),
                    recommended_roles=activity_analysis.get('recommended_roles'),
                    raw_analysis=analysis_result
                )
                self.db.add(analysis_record)

            self.db.commit()

            logger.info(f"GPT-4o analysis completed and saved for submission {submission_id}")

            # Update extracted_data with merged skills
            await self._merge_skills_to_extracted_data(submission_id, skills_analysis)

        except Exception as e:
            logger.error(f"Error in GPT-4o analysis: {e}")
            # Don't fail the GitHub collection if analysis fails

    async def _merge_skills_to_extracted_data(self, submission_id: str, skills_analysis: dict):
        """
        Merge GitHub-extracted skills with CV extracted data

        Args:
            submission_id: Submission UUID
            skills_analysis: Skills analysis from GPT-4o
        """
        try:
            from app.models.extracted_data import ExtractedData

            extracted_data = self.db.query(ExtractedData).filter(
                ExtractedData.submission_id == submission_id
            ).first()

            if not extracted_data:
                logger.warning(f"No extracted data found for submission {submission_id}")
                return

            # Merge skills from CV and GitHub
            existing_skills = extracted_data.skills or []
            github_skills = skills_analysis.get('technical_skills', [])

            # Convert to skill names for comparison
            existing_skill_names = {skill.get('name', '').lower() for skill in existing_skills if isinstance(skill, dict)}

            # Add GitHub skills that aren't already in CV skills
            for github_skill in github_skills:
                skill_name = github_skill.get('name', '')
                if skill_name.lower() not in existing_skill_names:
                    # Add new skill with GitHub source
                    existing_skills.append({
                        'name': skill_name,
                        'source': 'github',
                        'proficiency': github_skill.get('proficiency'),
                        'confidence': 85  # GitHub-derived skills have high confidence
                    })

            extracted_data.skills = existing_skills
            self.db.commit()

            logger.info(f"Merged GitHub skills into extracted data for submission {submission_id}")

        except Exception as e:
            logger.error(f"Error merging skills: {e}")
