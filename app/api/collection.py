"""
Collection API endpoints for Phase 2 data collection.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.collection_orchestrator import CollectionOrchestrator
from app.schemas.collection import (
    CollectionRequest,
    CollectionResponse,
    CollectionStatusResponse,
    CollectionResultsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collection",
    tags=["collection"]
)


@router.post("/start/{submission_id}", response_model=CollectionResponse)
async def start_collection(
    submission_id: UUID,
    background_tasks: BackgroundTasks,
    request: CollectionRequest = CollectionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start data collection for a submission.

    This endpoint initiates data collection from external sources (GitHub, Tavily)
    for the specified CV submission. The collection runs in the background.

    Args:
        submission_id: UUID of the CV submission
        background_tasks: FastAPI background tasks
        request: Collection request parameters
        db: Database session
        current_user: Authenticated user

    Returns:
        CollectionResponse with status

    Raises:
        HTTPException: 404 if submission not found, 403 if unauthorized
    """
    logger.info(f"User {current_user.email} starting collection for submission {submission_id}")

    orchestrator = CollectionOrchestrator(db)

    # Verify submission belongs to user
    submission = orchestrator.get_submission(str(submission_id), str(current_user.id))
    if not submission:
        logger.warning(f"Submission {submission_id} not found or unauthorized")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Check if submission has extracted data
    if submission.status not in ['extracted', 'validated', 'completed']:
        logger.warning(f"Submission {submission_id} not ready for collection: {submission.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission must have extracted data before collection can start"
        )

    # Start collection in background
    background_tasks.add_task(
        _run_collection_task,
        str(submission_id),
        db
    )

    logger.info(f"Collection started in background for submission {submission_id}")

    return CollectionResponse(
        submission_id=submission_id,
        status="started",
        message="Data collection started in background. Use /collection/status/{submission_id} to check progress."
    )


async def _run_collection_task(submission_id: str, db: Session):
    """
    Background task for running data collection.

    Args:
        submission_id: Submission UUID
        db: Database session
    """
    try:
        logger.info(f"Background collection task started for submission {submission_id}")

        # Create new database session for background task
        from app.database import SessionLocal
        task_db = SessionLocal()

        try:
            orchestrator = CollectionOrchestrator(task_db)
            await orchestrator.collect_all_sources(submission_id)
            logger.info(f"Collection completed successfully for submission {submission_id}")
        finally:
            task_db.close()

    except Exception as e:
        logger.error(f"Collection task failed for submission {submission_id}: {e}", exc_info=True)


@router.get("/status/{submission_id}", response_model=CollectionStatusResponse)
def get_collection_status(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get status of data collection for a submission.

    Returns the current status of data collection from all sources,
    including which sources are pending, collecting, completed, or failed.

    Args:
        submission_id: UUID of the CV submission
        db: Database session
        current_user: Authenticated user

    Returns:
        CollectionStatusResponse with source statuses

    Raises:
        HTTPException: 404 if not found or unauthorized
    """
    logger.info(f"User {current_user.email} checking collection status for {submission_id}")

    orchestrator = CollectionOrchestrator(db)
    status_data = orchestrator.get_collection_status(str(submission_id), str(current_user.id))

    if not status_data:
        logger.warning(f"Collection status not found for submission {submission_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection status not found"
        )

    return status_data


@router.get("/results/{submission_id}", response_model=CollectionResultsResponse)
def get_collection_results(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get collected data for a submission.

    Returns all data collected from external sources, including GitHub profile,
    web mentions, and aggregated profile information.

    Args:
        submission_id: UUID of the CV submission
        db: Database session
        current_user: Authenticated user

    Returns:
        CollectionResultsResponse with collected data

    Raises:
        HTTPException: 404 if not found or unauthorized
    """
    logger.info(f"User {current_user.email} retrieving collection results for {submission_id}")

    orchestrator = CollectionOrchestrator(db)
    results = orchestrator.get_collected_data(str(submission_id), str(current_user.id))

    if not results:
        logger.warning(f"Collection results not found for submission {submission_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No collected data found"
        )

    return results


@router.get("/analysis/{submission_id}")
def get_github_analysis(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get stored GitHub analysis results for a submission.

    Returns the comprehensive GPT-4o analysis including skills, activity patterns,
    and professional insights that were automatically generated after GitHub crawling.

    Args:
        submission_id: UUID of the CV submission
        db: Database session
        current_user: Authenticated user

    Returns:
        Dict with complete analysis data including skills and activity analysis

    Raises:
        HTTPException: 404 if not found or unauthorized
    """
    from app.models.collected_data import GitHubAnalysis, GitHubData

    logger.info(f"User {current_user.email} retrieving GitHub analysis for {submission_id}")

    # Verify submission belongs to user
    orchestrator = CollectionOrchestrator(db)
    submission = orchestrator.get_submission(str(submission_id), str(current_user.id))

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Get analysis data
    analysis = db.query(GitHubAnalysis).filter(
        GitHubAnalysis.submission_id == str(submission_id)
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub analysis found. Analysis may still be in progress or GitHub crawling may not have completed."
        )

    # Get associated GitHub data for context
    github_data = db.query(GitHubData).filter(
        GitHubData.id == analysis.github_data_id
    ).first()

    return {
        "submission_id": str(submission_id),
        "github_username": github_data.username if github_data else None,
        "skills_analysis": {
            "technical_skills": analysis.technical_skills,
            "frameworks": analysis.frameworks,
            "languages": analysis.languages,
            "tools": analysis.tools,
            "domains": analysis.domains,
            "soft_skills": analysis.soft_skills,
            "skill_summary": analysis.skill_summary
        },
        "activity_analysis": {
            "activity_level": analysis.activity_level,
            "commit_quality_score": analysis.commit_quality_score,
            "contribution_consistency": analysis.contribution_consistency,
            "collaboration_score": analysis.collaboration_score,
            "project_diversity": analysis.project_diversity,
            "strengths": analysis.strengths,
            "areas_for_growth": analysis.areas_for_growth,
            "insights": {
                "activity_insights": analysis.activity_insights,
                "commit_quality_insights": analysis.commit_quality_insights,
                "collaboration_insights": analysis.collaboration_insights,
                "project_insights": analysis.project_insights
            }
        },
        "professional_summary": analysis.professional_summary,
        "recommended_roles": analysis.recommended_roles,
        "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None
    }


@router.post("/analyze-github/{submission_id}")
async def analyze_github_with_ai(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze GitHub data using GPT-4o to extract structured skills

    Args:
        submission_id: UUID of the CV submission
        db: Database session
        current_user: Authenticated user

    Returns:
        Dict with extracted skills and analysis

    Raises:
        HTTPException: 404 if not found, 500 if analysis fails
    """
    from app.models.collected_data import GitHubData
    from app.services.openai_analyzer import OpenAIAnalyzer

    logger.info(f"User {current_user.email} requesting AI analysis for {submission_id}")

    # Get GitHub data
    orchestrator = CollectionOrchestrator(db)
    submission = orchestrator.get_submission(str(submission_id), str(current_user.id))

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Get GitHub data for this submission
    github_data = db.query(GitHubData).filter(
        GitHubData.submission_id == str(submission_id)
    ).first()

    if not github_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub data found. Please ensure GitHub crawling has completed."
        )

    # Prepare data for analysis
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
    skills_analysis = await analyzer.extract_skills_from_github(github_dict)

    return {
        "submission_id": str(submission_id),
        "github_username": github_data.username,
        "analysis": skills_analysis,
        "collected_at": github_data.collected_at.isoformat() if github_data.collected_at else None
    }
