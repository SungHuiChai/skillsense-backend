"""
Extraction API endpoints
Get, validate, and update extracted CV data
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Dict, Any
import logging

from app.database import get_db
from app.models import User, CVSubmission, ExtractedData, UserEdit
from app.models.collected_data import CollectedSource
from app.schemas import (
    ExtractedDataResponse, ExtractedDataUpdate,
    ExtractionStatusResponse, UserEditCreate
)
from app.core import get_current_user
from app.services.link_validator import LinkValidator
from app.services.throttle_service import ThrottleService
from app.services.collection_orchestrator import CollectionOrchestrator

router = APIRouter(prefix="/extraction", tags=["Extraction"])


def format_extracted_data(extracted_data: ExtractedData, submission: CVSubmission, user: User = None) -> Dict[str, Any]:
    """
    Format extracted data for API response

    Args:
        extracted_data: ExtractedData model instance
        submission: CVSubmission model instance
        user: User model instance (optional, used to auto-populate full_name if missing)

    Returns:
        Dict: Formatted extracted data
    """
    # Auto-populate full_name from user registration if extraction didn't find it
    full_name_value = extracted_data.full_name
    full_name_confidence = float(extracted_data.full_name_confidence) if extracted_data.full_name_confidence else 0
    
    # If full_name is missing or empty, use the user's registered full_name
    if (not full_name_value or full_name_value.strip() == '') and user and user.full_name:
        full_name_value = user.full_name
        # Set a lower confidence since it's from registration, not CV extraction
        if full_name_confidence == 0:
            full_name_confidence = 50.0  # Medium confidence for registration data
    
    return {
        "submission_id": str(submission.id),
        "status": submission.status,
        "extracted_data": {
            "personal_info": {
                "full_name": {
                    "value": full_name_value,
                    "confidence": full_name_confidence
                },
                "email": {
                    "value": extracted_data.email,
                    "confidence": float(extracted_data.email_confidence) if extracted_data.email_confidence else 0
                },
                "phone": {
                    "value": extracted_data.phone,
                    "confidence": float(extracted_data.phone_confidence) if extracted_data.phone_confidence else 0
                },
                "location": {
                    "value": extracted_data.location,
                    "confidence": float(extracted_data.location_confidence) if extracted_data.location_confidence else 0
                }
            },
            "social_links": {
                "github": {
                    "value": extracted_data.github_url,
                    "confidence": float(extracted_data.github_url_confidence) if extracted_data.github_url_confidence else 0,
                    "validated": bool(extracted_data.github_url)
                },
                "linkedin": {
                    "value": extracted_data.linkedin_url,
                    "confidence": float(extracted_data.linkedin_url_confidence) if extracted_data.linkedin_url_confidence else 0,
                    "validated": bool(extracted_data.linkedin_url)
                },
                "portfolio": {
                    "value": extracted_data.portfolio_url,
                    "confidence": float(extracted_data.portfolio_url_confidence) if extracted_data.portfolio_url_confidence else 0,
                    "validated": bool(extracted_data.portfolio_url)
                },
                "twitter": {
                    "value": extracted_data.twitter_url,
                    "confidence": float(extracted_data.twitter_url_confidence) if extracted_data.twitter_url_confidence else 0,
                    "validated": bool(extracted_data.twitter_url)
                }
            },
            "work_history": extracted_data.work_history or [],
            "education": extracted_data.education or [],
            "skills": extracted_data.skills or [],
            "certifications": extracted_data.certifications or [],
            "languages": extracted_data.languages or []
        },
        "overall_confidence": float(extracted_data.overall_confidence) if extracted_data.overall_confidence else 0,
        "is_validated": extracted_data.is_validated,
        "extracted_at": extracted_data.created_at.isoformat() if extracted_data.created_at else None
    }


@router.get("/{submission_id}", response_model=Dict[str, Any])
async def get_extraction(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get extracted data for a CV submission

    Args:
        submission_id: UUID of CV submission
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dict: Extracted data with confidence scores

    Raises:
        HTTPException: If submission not found or not authorized
    """
    # Get submission
    submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV submission not found"
        )

    # Check authorization (user owns this submission)
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this submission"
        )

    # Check if extraction is complete
    if submission.status not in ["extracted", "validated", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extraction not complete. Current status: {submission.status}"
        )

    # Get extracted data
    extracted_data = db.query(ExtractedData).filter(
        ExtractedData.submission_id == submission_id
    ).first()

    if not extracted_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted data not found"
        )

    return format_extracted_data(extracted_data, submission, current_user)


@router.get("/{submission_id}/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get processing status of CV submission

    Args:
        submission_id: UUID of CV submission
        current_user: Current authenticated user
        db: Database session

    Returns:
        ExtractionStatusResponse: Current processing status

    Raises:
        HTTPException: If submission not found or not authorized
    """
    # Get submission
    submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV submission not found"
        )

    # Check authorization
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this submission"
        )

    # Determine message based on status
    status_messages = {
        "uploaded": "CV uploaded, waiting to be processed",
        "processing": "Extracting data from CV",
        "extracted": "Data extraction complete",
        "validated": "User has validated the extracted data",
        "completed": "Processing complete",
        "failed": submission.error_message or "Processing failed"
    }

    # Calculate progress
    progress_map = {
        "uploaded": 20,
        "processing": 50,
        "extracted": 80,
        "validated": 90,
        "completed": 100,
        "failed": 0
    }

    return ExtractionStatusResponse(
        submission_id=submission_id,
        status=submission.status,
        message=status_messages.get(submission.status, "Unknown status"),
        progress=progress_map.get(submission.status, 0)
    )


@router.put("/{submission_id}/validate", response_model=Dict[str, Any])
async def validate_extraction(
    submission_id: str,
    update_data: ExtractedDataUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate and update extracted data

    Args:
        submission_id: UUID of CV submission
        update_data: Updated extracted data from user
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dict: Updated extracted data

    Raises:
        HTTPException: If submission not found or not authorized
    """
    logger = logging.getLogger(__name__)

    # DEBUG: Log the incoming payload
    logger.info(f"=== VALIDATE PAYLOAD DEBUG ===")
    logger.info(f"submission_id: {submission_id}")
    logger.info(f"update_data.full_name: {update_data.full_name}")
    logger.info(f"update_data.email: {update_data.email}")
    logger.info(f"update_data.phone: {update_data.phone}")
    logger.info(f"update_data.location: {update_data.location}")
    logger.info(f"update_data dict: {update_data.model_dump()}")
    logger.info(f"=== END DEBUG ===")


    # Get submission
    submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV submission not found"
        )

    # Check authorization
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this submission"
        )

    # Get extracted data
    extracted_data = db.query(ExtractedData).filter(
        ExtractedData.submission_id == submission_id
    ).first()

    if not extracted_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted data not found"
        )

    # Track user edits and check if GitHub URL changed
    update_dict = update_data.model_dump(exclude_unset=True)
    github_url_changed = False
    old_github_url = extracted_data.github_url
    new_github_url = None

    for field_name, new_value in update_dict.items():
        if field_name in ['is_validated', 'validation_notes']:
            continue

        # Get original value
        original_value = getattr(extracted_data, field_name, None)

        # Convert to string for comparison
        original_str = str(original_value) if original_value is not None else None
        new_str = str(new_value) if new_value is not None else None

        # If value changed, create edit record
        if original_str != new_str:
            user_edit = UserEdit(
                extracted_data_id=extracted_data.id,
                field_name=field_name,
                original_value=original_str,
                edited_value=new_str
            )
            db.add(user_edit)

            # Update the field
            setattr(extracted_data, field_name, new_value)

            # Track GitHub URL change
            if field_name == 'github_url':
                github_url_changed = True
                new_github_url = new_value

    # Check if this is the first validation
    was_unvalidated = not extracted_data.is_validated

    # Mark as validated
    if update_data.is_validated:
        extracted_data.is_validated = True
        extracted_data.validated_at = datetime.utcnow()
        submission.status = "validated"

    if update_data.validation_notes:
        extracted_data.validation_notes = update_data.validation_notes

    db.commit()
    db.refresh(extracted_data)
    db.refresh(submission)

    # Auto-trigger collection EVERY TIME validation is saved if GitHub URL exists
    should_trigger_collection = False
    new_github_url = None

    # Trigger if user is validating AND has a GitHub URL
    if update_data.is_validated and extracted_data.github_url:
        should_trigger_collection = True
        new_github_url = extracted_data.github_url

    if should_trigger_collection and new_github_url:
        logger.info(f"DEBUG: should_trigger_collection=True, new_github_url={new_github_url}")
        try:
            # Validate GitHub URL
            validation_result = await LinkValidator.validate_github_url(new_github_url)
            logger.info(f"DEBUG: validation_result={validation_result}")

            # Only trigger if URL is valid and account exists
            if (validation_result['is_valid_format'] and
                validation_result.get('account_exists') is not False):

                logger.info(f"DEBUG: GitHub URL is valid, checking throttle...")

                # Check throttle
                is_allowed, _, seconds_remaining = ThrottleService.check_throttle(
                    db, str(current_user.id), 'github'
                )

                logger.info(f"DEBUG: Throttle check - is_allowed={is_allowed}, seconds_remaining={seconds_remaining}")

                # Trigger crawl if allowed (silently skip if throttled)
                if is_allowed:
                    logger.info(f"DEBUG: Adding background task for collection")
                    async def trigger_github_crawl():
                        logger.info(f"DEBUG: Background task started for submission {submission_id}")
                        try:
                            orchestrator = CollectionOrchestrator(db)

                            # Create or update source record
                            existing_source = (
                                db.query(CollectedSource)
                                .filter(
                                    and_(
                                        CollectedSource.submission_id == submission_id,
                                        CollectedSource.source_type == 'github'
                                    )
                                )
                                .first()
                            )

                            if not existing_source:
                                source_record = CollectedSource(
                                    submission_id=submission_id,
                                    source_type='github',
                                    source_url=new_github_url,
                                    status='pending'
                                )
                                db.add(source_record)
                                db.commit()

                            # Trigger full collection (includes Phase 2: GitHub + Phase 3: Web sources)
                            await orchestrator.collect_all_sources(submission_id)
                        except Exception as e:
                            # Log but don't fail the request
                            logger.error(f"Error in background collection: {e}")

                    background_tasks.add_task(trigger_github_crawl)

        except Exception as e:
            # Log validation error but don't fail the update
            logger.warning(f"GitHub URL validation failed: {e}")

    return format_extracted_data(extracted_data, submission, current_user)


@router.get("/{submission_id}/edits", response_model=list)
async def get_user_edits(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get history of user edits for a submission

    Args:
        submission_id: UUID of CV submission
        current_user: Current authenticated user
        db: Database session

    Returns:
        List: List of user edits

    Raises:
        HTTPException: If submission not found or not authorized
    """
    # Get submission
    submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV submission not found"
        )

    # Check authorization
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this submission"
        )

    # Get extracted data
    extracted_data = db.query(ExtractedData).filter(
        ExtractedData.submission_id == submission_id
    ).first()

    if not extracted_data:
        return []

    # Get all edits
    edits = db.query(UserEdit).filter(
        UserEdit.extracted_data_id == extracted_data.id
    ).order_by(UserEdit.edited_at.desc()).all()

    return edits
