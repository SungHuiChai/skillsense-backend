"""
Processing API endpoints
Handles skill processing, validation, and profile building
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.services.web_source_orchestrator import get_web_orchestrator
from app.services.skill_validation_service import get_validation_service
from app.services.skill_profile_service import get_profile_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])


@router.post("/start/{submission_id}")
async def start_processing(
    submission_id: UUID,
    background_tasks: BackgroundTasks,
    force_reprocess: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start processing for a submission (web extraction).

    This triggers:
    1. Stack Overflow profile discovery
    2. Web mentions search
    3. Personal blog discovery
    4. Skill extraction from all sources
    """
    logger.info(f"Starting processing for submission {submission_id}")

    # Verify submission exists and belongs to user
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Start processing in background
    orchestrator = get_web_orchestrator()

    async def process_task():
        try:
            await orchestrator.process_submission(
                submission_id=submission_id,
                db=db,
                force_reprocess=force_reprocess
            )
        except Exception as e:
            logger.error(f"Error in background processing: {e}")

    background_tasks.add_task(process_task)

    return {
        "message": "Processing started",
        "submission_id": str(submission_id),
        "status": "processing"
    }


@router.get("/status/{submission_id}")
def get_processing_status(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get processing status for a submission"""
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    orchestrator = get_web_orchestrator()
    status = orchestrator.get_processing_status(submission_id, db)

    return status


@router.post("/validate/{submission_id}")
def validate_skills(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate skills across all sources for a submission.

    Returns:
    - Cross-source validated skills
    - Confidence scores
    - Hallucination detection results
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    validation_service = get_validation_service()
    results = validation_service.validate_submission_skills(submission_id, db)

    return results


@router.post("/build-profile/{submission_id}")
def build_skill_profile(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Build comprehensive skill profile for a submission.

    Returns:
    - Categorized skills
    - Skill relationships
    - Professional summary
    - Learning recommendations
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    profile_service = get_profile_service()
    profile = profile_service.build_skill_profile(submission_id, db)

    return profile


@router.get("/web-sources/{submission_id}")
def get_web_sources(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get web source data (Stack Overflow, web mentions, blog).
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Get Stack Overflow data
    from app.models.collected_data import StackOverflowData, SkillWebMention

    stackoverflow = db.query(StackOverflowData).filter(
        StackOverflowData.submission_id == str(submission_id)
    ).first()

    # Get web mentions
    web_mentions = db.query(SkillWebMention).filter(
        SkillWebMention.submission_id == str(submission_id)
    ).all()

    # Group web mentions by source type
    mentions_by_type = {}
    for mention in web_mentions:
        source_type = mention.source_type or "other"
        if source_type not in mentions_by_type:
            mentions_by_type[source_type] = []

        mentions_by_type[source_type].append({
            "skill": mention.skill_name,
            "canonical_skill": mention.canonical_skill,
            "url": mention.url,
            "title": mention.title,
            "credibility": mention.credibility,
            "credibility_score": float(mention.credibility_score) if mention.credibility_score else None,
            "source_type": mention.source_type
        })

    # Build response
    result = {
        "submission_id": str(submission_id),
        "stackoverflow": None,
        "web_mentions": {
            "total": len(web_mentions),
            "by_type": mentions_by_type
        }
    }

    if stackoverflow:
        result["stackoverflow"] = {
            "profile_url": stackoverflow.profile_url,
            "username": stackoverflow.username,
            "reputation": stackoverflow.reputation,
            "total_answers": stackoverflow.total_answers,
            "total_questions": stackoverflow.total_questions,
            "activity_level": stackoverflow.activity_level,
            "top_tags": stackoverflow.top_tags or [],
            "skills_from_tags": stackoverflow.skills_from_tags or []
        }

    return result
