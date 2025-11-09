"""
Admin API endpoints
Admin access only - view all submissions, users, and statistics
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, CVSubmission, ExtractedData
from app.models.collected_data import CollectedSource, GitHubData
from app.schemas import CVSubmissionListResponse
from app.core import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/submissions", response_model=Dict[str, Any])
async def get_all_submissions(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by email or filename"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all CV submissions (admin only) with pagination and filters

    Args:
        page: Page number
        per_page: Items per page
        status: Filter by submission status
        search: Search query for email or filename
        file_type: Filter by file type
        current_admin: Current authenticated admin
        db: Database session

    Returns:
        Dict: Paginated list of submissions with metadata
    """
    # Base query
    query = db.query(
        CVSubmission,
        User.email,
        ExtractedData.overall_confidence
    ).join(
        User, CVSubmission.user_id == User.id
    ).outerjoin(
        ExtractedData, CVSubmission.id == ExtractedData.submission_id
    )

    # Apply filters
    if status:
        query = query.filter(CVSubmission.status == status)

    if file_type:
        query = query.filter(CVSubmission.file_type == file_type)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.email.ilike(search_term)) | (CVSubmission.filename.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    submissions_data = query.order_by(
        CVSubmission.uploaded_at.desc()
    ).offset(offset).limit(per_page).all()

    # Format results
    submissions = []
    for submission, user_email, confidence in submissions_data:
        submissions.append({
            "id": str(submission.id),
            "user_email": user_email,
            "filename": submission.filename,
            "file_type": submission.file_type,
            "file_size": submission.file_size,
            "status": submission.status,
            "uploaded_at": submission.uploaded_at.isoformat() if submission.uploaded_at else None,
            "processed_at": submission.processed_at.isoformat() if submission.processed_at else None,
            "overall_confidence": float(confidence) if confidence else None,
            "error_message": submission.error_message
        })

    # Calculate pagination metadata
    total_pages = (total + per_page - 1) // per_page

    return {
        "submissions": submissions,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }


@router.get("/submissions/{submission_id}", response_model=Dict[str, Any])
async def get_submission_detail(
    submission_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a submission (admin only)

    Args:
        submission_id: UUID of submission
        current_admin: Current authenticated admin
        db: Database session

    Returns:
        Dict: Complete submission details

    Raises:
        HTTPException: If submission not found
    """
    # Get submission with user info
    submission_data = db.query(
        CVSubmission,
        User
    ).join(
        User, CVSubmission.user_id == User.id
    ).filter(
        CVSubmission.id == submission_id
    ).first()

    if not submission_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    submission, user = submission_data

    # Get extracted data
    extracted_data = db.query(ExtractedData).filter(
        ExtractedData.submission_id == submission_id
    ).first()

    # Format response
    result = {
        "id": str(submission.id),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "filename": submission.filename,
        "file_path": submission.file_path,
        "file_size": submission.file_size,
        "file_type": submission.file_type,
        "status": submission.status,
        "uploaded_at": submission.uploaded_at.isoformat() if submission.uploaded_at else None,
        "processed_at": submission.processed_at.isoformat() if submission.processed_at else None,
        "error_message": submission.error_message,
        "extracted_data": None
    }

    if extracted_data:
        result["extracted_data"] = {
            "personal_info": {
                "full_name": extracted_data.full_name,
                "email": extracted_data.email,
                "phone": extracted_data.phone,
                "location": extracted_data.location
            },
            "social_links": {
                "github": extracted_data.github_url,
                "linkedin": extracted_data.linkedin_url,
                "portfolio": extracted_data.portfolio_url,
                "twitter": extracted_data.twitter_url
            },
            "work_history": extracted_data.work_history,
            "education": extracted_data.education,
            "skills": extracted_data.skills,
            "overall_confidence": float(extracted_data.overall_confidence) if extracted_data.overall_confidence else 0,
            "is_validated": extracted_data.is_validated,
            "validated_at": extracted_data.validated_at.isoformat() if extracted_data.validated_at else None,
            "raw_text_preview": extracted_data.raw_text[:500] if extracted_data.raw_text else None
        }

    return result


@router.get("/stats", response_model=Dict[str, Any])
async def get_statistics(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get system statistics (admin only)

    Args:
        current_admin: Current authenticated admin
        db: Database session

    Returns:
        Dict: System statistics
    """
    # Total submissions
    total_submissions = db.query(func.count(CVSubmission.id)).scalar()

    # Submissions by status
    status_counts = db.query(
        CVSubmission.status,
        func.count(CVSubmission.id)
    ).group_by(CVSubmission.status).all()

    status_breakdown = {status: count for status, count in status_counts}

    # Submissions by file type
    file_type_counts = db.query(
        CVSubmission.file_type,
        func.count(CVSubmission.id)
    ).group_by(CVSubmission.file_type).all()

    file_type_breakdown = {file_type: count for file_type, count in file_type_counts}

    # Total users
    total_users = db.query(func.count(User.id)).scalar()

    # Average confidence score
    avg_confidence = db.query(
        func.avg(ExtractedData.overall_confidence)
    ).scalar()

    # Submissions in last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_submissions = db.query(
        func.count(CVSubmission.id)
    ).filter(
        CVSubmission.uploaded_at >= seven_days_ago
    ).scalar()

    # Success rate (completed vs failed)
    completed = status_breakdown.get('completed', 0) + status_breakdown.get('validated', 0)
    failed = status_breakdown.get('failed', 0)
    success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0

    # Recent activity (last 10 submissions)
    recent_activity = db.query(
        CVSubmission.id,
        CVSubmission.filename,
        CVSubmission.status,
        CVSubmission.uploaded_at,
        User.email
    ).join(
        User, CVSubmission.user_id == User.id
    ).order_by(
        CVSubmission.uploaded_at.desc()
    ).limit(10).all()

    formatted_activity = [
        {
            "id": str(activity[0]),
            "filename": activity[1],
            "status": activity[2],
            "uploaded_at": activity[3].isoformat() if activity[3] else None,
            "user_email": activity[4]
        }
        for activity in recent_activity
    ]

    # Phase 2: GitHub Crawling Statistics
    total_collections = db.query(func.count(CollectedSource.id)).scalar() or 0

    # Collection status breakdown
    collection_status_counts = db.query(
        CollectedSource.status,
        func.count(CollectedSource.id)
    ).group_by(CollectedSource.status).all()

    collection_status_breakdown = {status: count for status, count in collection_status_counts}

    # Collections by source type
    source_type_counts = db.query(
        CollectedSource.source_type,
        func.count(CollectedSource.id)
    ).group_by(CollectedSource.source_type).all()

    source_type_breakdown = {source: count for source, count in source_type_counts}

    # GitHub profiles collected
    total_github_profiles = db.query(func.count(GitHubData.id)).scalar() or 0

    # Collections in last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    recent_collections = db.query(
        func.count(CollectedSource.id)
    ).filter(
        CollectedSource.created_at >= twenty_four_hours_ago
    ).scalar() or 0

    # Failed collections in last 24 hours
    recent_failures = db.query(
        func.count(CollectedSource.id)
    ).filter(
        CollectedSource.status == 'failed',
        CollectedSource.completed_at >= twenty_four_hours_ago
    ).scalar() or 0

    # Active (collecting) right now
    active_collections = db.query(
        func.count(CollectedSource.id)
    ).filter(
        CollectedSource.status == 'collecting'
    ).scalar() or 0

    # Recent collection activity (last 10)
    recent_collection_activity = db.query(
        CollectedSource.source_type,
        CollectedSource.source_url,
        CollectedSource.status,
        CollectedSource.started_at,
        CollectedSource.completed_at,
        CollectedSource.error_message
    ).order_by(
        CollectedSource.created_at.desc()
    ).limit(10).all()

    formatted_collection_activity = [
        {
            "source_type": activity[0],
            "source_url": activity[1],
            "status": activity[2],
            "started_at": activity[3].isoformat() if activity[3] else None,
            "completed_at": activity[4].isoformat() if activity[4] else None,
            "error_message": activity[5]
        }
        for activity in recent_collection_activity
    ]

    return {
        "overview": {
            "total_submissions": total_submissions,
            "total_users": total_users,
            "recent_submissions_7d": recent_submissions,
            "average_confidence": round(float(avg_confidence), 2) if avg_confidence else 0,
            "success_rate": round(success_rate, 2)
        },
        "status_breakdown": status_breakdown,
        "file_type_breakdown": file_type_breakdown,
        "recent_activity": formatted_activity,
        # Phase 2: Collection Statistics
        "collection_stats": {
            "total_collections": total_collections,
            "total_github_profiles": total_github_profiles,
            "recent_collections_24h": recent_collections,
            "recent_failures_24h": recent_failures,
            "active_collections": active_collections,
            "collection_status_breakdown": collection_status_breakdown,
            "source_type_breakdown": source_type_breakdown
        },
        "recent_collection_activity": formatted_collection_activity
    }


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a submission (admin only)

    Args:
        submission_id: UUID of submission to delete
        current_admin: Current authenticated admin
        db: Database session

    Raises:
        HTTPException: If submission not found
    """
    submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # Delete file from disk (optional)
    from app.utils import delete_file
    delete_file(submission.file_path)

    # Delete from database (CASCADE will delete related extracted_data)
    db.delete(submission)
    db.commit()

    return None
