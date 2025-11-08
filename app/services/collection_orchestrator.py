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

        # Aggregate collected data
        await self._aggregate_data(submission_id)

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
                "username": github_data.username if github_data else None,
                "name": github_data.name if github_data else None,
                "repos": github_data.public_repos if github_data else None,
                "languages": github_data.languages if github_data else None,
                "technologies": github_data.technologies if github_data else None
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
