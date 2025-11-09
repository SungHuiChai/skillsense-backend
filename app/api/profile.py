"""
Profile API endpoints
User profile management and social links with automatic GitHub crawling
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import User, CVSubmission, ExtractedData
from app.models.collected_data import CollectedSource
from app.schemas import (
    ProfileResponse, SocialLinksUpdate, SocialLinksUpdateResponse,
    GitHubValidationRequest, GitHubValidationResponse,
    GitHubSyncStatusResponse
)
from app.core import get_current_user
from app.services.link_validator import LinkValidator
from app.services.throttle_service import ThrottleService
from app.services.collection_orchestrator import CollectionOrchestrator

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile including social links from latest submission

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        ProfileResponse: User profile data
    """
    # Get latest submission
    latest_submission = (
        db.query(CVSubmission)
        .filter(CVSubmission.user_id == current_user.id)
        .order_by(desc(CVSubmission.uploaded_at))
        .first()
    )

    social_links = None
    latest_submission_id = None

    if latest_submission:
        latest_submission_id = str(latest_submission.id)

        # Get extracted data
        extracted_data = (
            db.query(ExtractedData)
            .filter(ExtractedData.submission_id == latest_submission.id)
            .first()
        )

        if extracted_data:
            social_links = {
                'github': extracted_data.github_url,
                'linkedin': extracted_data.linkedin_url,
                'portfolio': extracted_data.portfolio_url,
                'twitter': extracted_data.twitter_url
            }

    return ProfileResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        social_links=social_links,
        latest_submission_id=latest_submission_id,
        created_at=current_user.created_at
    )


@router.post("/validate-github", response_model=GitHubValidationResponse)
async def validate_github(
    request: GitHubValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate GitHub URL format and check if account exists

    Args:
        request: GitHub URL validation request
        current_user: Current authenticated user

    Returns:
        GitHubValidationResponse: Validation result
    """
    result = await LinkValidator.validate_github_url(request.github_url)

    return GitHubValidationResponse(
        is_valid_format=result['is_valid_format'],
        username=result.get('username'),
        account_exists=result.get('account_exists'),
        error_message=result.get('error_message'),
        profile_data=result.get('profile_data')
    )


@router.get("/github-status", response_model=GitHubSyncStatusResponse)
async def get_github_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get GitHub sync status including throttling info

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        GitHubSyncStatusResponse: Sync status and throttle info
    """
    # Check throttle status
    is_allowed, last_synced_at, seconds_remaining = ThrottleService.check_throttle(
        db, str(current_user.id), 'github'
    )

    # Check if currently syncing
    is_syncing = False
    latest_submission = (
        db.query(CVSubmission)
        .filter(CVSubmission.user_id == current_user.id)
        .order_by(desc(CVSubmission.uploaded_at))
        .first()
    )

    if latest_submission:
        github_source = (
            db.query(CollectedSource)
            .filter(
                CollectedSource.submission_id == latest_submission.id,
                CollectedSource.source_type == 'github',
                CollectedSource.status == 'collecting'
            )
            .first()
        )
        is_syncing = github_source is not None

    next_allowed_at = None
    time_remaining_text = None

    if not is_allowed and seconds_remaining:
        next_allowed_at = ThrottleService.get_next_allowed_time(
            db, str(current_user.id), 'github'
        )
        time_remaining_text = ThrottleService.format_time_remaining(seconds_remaining)

    return GitHubSyncStatusResponse(
        can_sync=is_allowed and not is_syncing,
        is_syncing=is_syncing,
        last_synced_at=last_synced_at,
        next_allowed_at=next_allowed_at,
        seconds_remaining=seconds_remaining,
        time_remaining_text=time_remaining_text
    )


async def trigger_github_crawl_bg(
    submission_id: str,
    github_url: str,
    db: Session
):
    """
    Background task to trigger GitHub crawl

    Args:
        submission_id: Submission ID
        github_url: GitHub URL to crawl
        db: Database session
    """
    try:
        orchestrator = CollectionOrchestrator(db)

        # Create source record if not exists
        existing_source = (
            db.query(CollectedSource)
            .filter(
                CollectedSource.submission_id == submission_id,
                CollectedSource.source_type == 'github'
            )
            .first()
        )

        if not existing_source:
            source_record = CollectedSource(
                submission_id=submission_id,
                source_type='github',
                source_url=github_url,
                status='pending'
            )
            db.add(source_record)
            db.commit()

        # Trigger GitHub collection
        await orchestrator._collect_github(submission_id, github_url)

    except Exception as e:
        # Log error but don't fail the API request
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in background GitHub crawl: {e}")


@router.put("/social-links", response_model=SocialLinksUpdateResponse)
async def update_social_links(
    social_links: SocialLinksUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update social links and auto-trigger GitHub crawl if URL changed

    Args:
        social_links: Social links to update
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session

    Returns:
        SocialLinksUpdateResponse: Update result and crawl status
    """
    # Get latest submission
    latest_submission = (
        db.query(CVSubmission)
        .filter(CVSubmission.user_id == current_user.id)
        .order_by(desc(CVSubmission.uploaded_at))
        .first()
    )

    if not latest_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV submission found. Please upload a CV first."
        )

    # Get extracted data
    extracted_data = (
        db.query(ExtractedData)
        .filter(ExtractedData.submission_id == latest_submission.id)
        .first()
    )

    if not extracted_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extracted data found for your submission."
        )

    # Track if GitHub URL changed
    github_url_changed = False
    old_github_url = extracted_data.github_url
    new_github_url = social_links.github

    # Update social links
    if social_links.github is not None:
        if social_links.github != old_github_url:
            github_url_changed = True
        extracted_data.github_url = social_links.github if social_links.github else None

    if social_links.linkedin is not None:
        extracted_data.linkedin_url = social_links.linkedin if social_links.linkedin else None

    if social_links.portfolio is not None:
        extracted_data.portfolio_url = social_links.portfolio if social_links.portfolio else None

    if social_links.twitter is not None:
        extracted_data.twitter_url = social_links.twitter if social_links.twitter else None

    db.commit()
    db.refresh(extracted_data)

    # Check if we should trigger GitHub crawl
    github_crawl_triggered = False
    crawl_status = None

    if github_url_changed and new_github_url:
        # Validate GitHub URL
        validation_result = await LinkValidator.validate_github_url(new_github_url)

        if not validation_result['is_valid_format']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result.get('error_message', 'Invalid GitHub URL')
            )

        if validation_result.get('account_exists') is False:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=validation_result.get('error_message', 'GitHub account not found')
            )

        # Check throttle
        is_allowed, _, seconds_remaining = ThrottleService.check_throttle(
            db, str(current_user.id), 'github'
        )

        if not is_allowed:
            time_text = ThrottleService.format_time_remaining(seconds_remaining)
            crawl_status = f"throttled_{seconds_remaining}"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {time_text} before triggering another GitHub sync."
            )

        # Trigger background crawl
        background_tasks.add_task(
            trigger_github_crawl_bg,
            str(latest_submission.id),
            new_github_url,
            db
        )

        github_crawl_triggered = True
        crawl_status = "triggered"

    return SocialLinksUpdateResponse(
        success=True,
        message="Social links updated successfully",
        updated_links={
            'github': extracted_data.github_url,
            'linkedin': extracted_data.linkedin_url,
            'portfolio': extracted_data.portfolio_url,
            'twitter': extracted_data.twitter_url
        },
        github_crawl_triggered=github_crawl_triggered,
        crawl_status=crawl_status
    )
