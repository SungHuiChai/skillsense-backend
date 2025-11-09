"""
Throttle Service
Manages rate limiting for data collection operations per user
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.collected_data import CollectedSource
from app.models.cv_submission import CVSubmission
from app.config import settings


class ThrottleService:
    """Manage rate limiting for GitHub and other data collection sources"""

    @staticmethod
    def check_throttle(
        db: Session,
        user_id: str,
        source_type: str
    ) -> Tuple[bool, Optional[datetime], Optional[int]]:
        """
        Check if a user is allowed to trigger a new collection for a source type

        Args:
            db: Database session
            user_id: User ID to check
            source_type: Source type ('github', 'web_search', etc.)

        Returns:
            Tuple[bool, Optional[datetime], Optional[int]]:
                - is_allowed: Whether user can trigger collection
                - last_collected_at: When the last collection occurred
                - seconds_remaining: Seconds until next allowed collection (if throttled)
        """
        if not settings.ENABLE_CRAWL_THROTTLING:
            return True, None, None

        # Get cooldown period based on source type
        cooldown_seconds = ThrottleService._get_cooldown_seconds(source_type)

        # Find the most recent completed collection for this user and source type
        last_collection = (
            db.query(CollectedSource)
            .join(CVSubmission, CollectedSource.submission_id == CVSubmission.id)
            .filter(
                and_(
                    CVSubmission.user_id == user_id,
                    CollectedSource.source_type == source_type,
                    CollectedSource.status.in_(["completed", "failed"])
                )
            )
            .order_by(desc(CollectedSource.completed_at))
            .first()
        )

        if not last_collection or not last_collection.completed_at:
            # No previous collection, allow
            return True, None, None

        # Calculate time since last collection
        now = datetime.now(last_collection.completed_at.tzinfo)
        time_since_last = now - last_collection.completed_at
        cooldown_delta = timedelta(seconds=cooldown_seconds)

        if time_since_last >= cooldown_delta:
            # Cooldown period has passed
            return True, last_collection.completed_at, None
        else:
            # Still in cooldown
            time_remaining = cooldown_delta - time_since_last
            seconds_remaining = int(time_remaining.total_seconds())
            return False, last_collection.completed_at, seconds_remaining

    @staticmethod
    def _get_cooldown_seconds(source_type: str) -> int:
        """
        Get cooldown period for a specific source type

        Args:
            source_type: Source type ('github', 'web_search', etc.)

        Returns:
            int: Cooldown period in seconds
        """
        # Map source types to their cooldown periods
        cooldown_map = {
            'github': settings.GITHUB_CRAWL_COOLDOWN_SECONDS,
            'web_search': settings.GITHUB_CRAWL_COOLDOWN_SECONDS,  # Can be customized
        }

        return cooldown_map.get(source_type, settings.GITHUB_CRAWL_COOLDOWN_SECONDS)

    @staticmethod
    def get_next_allowed_time(
        db: Session,
        user_id: str,
        source_type: str
    ) -> Optional[datetime]:
        """
        Get the next time a user can trigger collection for a source type

        Args:
            db: Database session
            user_id: User ID
            source_type: Source type

        Returns:
            Optional[datetime]: Next allowed collection time, or None if allowed now
        """
        is_allowed, last_collected_at, seconds_remaining = ThrottleService.check_throttle(
            db, user_id, source_type
        )

        if is_allowed:
            return None

        if last_collected_at and seconds_remaining:
            return last_collected_at + timedelta(seconds=ThrottleService._get_cooldown_seconds(source_type))

        return None

    @staticmethod
    def format_time_remaining(seconds: int) -> str:
        """
        Format seconds into human-readable time

        Args:
            seconds: Seconds remaining

        Returns:
            str: Formatted time string
        """
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
            return f"{hours} hour{'s' if hours != 1 else ''}"
