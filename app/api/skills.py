"""
Skills API endpoints
Retrieve and query skill information
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.services.skill_validation_service import get_validation_service
from app.services.skill_normalization import get_normalization_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("/{submission_id}")
def get_skills(
    submission_id: UUID,
    category: Optional[str] = None,
    min_confidence: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all validated skills for a submission.

    Query parameters:
    - category: Filter by skill category (frontend, backend, database, etc.)
    - min_confidence: Minimum confidence score (0-100)
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Get validated skills
    validation_service = get_validation_service()
    results = validation_service.validate_submission_skills(submission_id, db)

    skills = results["validated_skills"]

    # Apply filters
    if category:
        skills = [s for s in skills if s.get("category") == category]

    if min_confidence is not None:
        skills = [s for s in skills if s.get("confidence_score", 0) >= min_confidence]

    return {
        "submission_id": str(submission_id),
        "total_skills": len(skills),
        "filters_applied": {
            "category": category,
            "min_confidence": min_confidence
        },
        "skills": skills
    }


@router.get("/{submission_id}/details/{skill_name}")
def get_skill_details(
    submission_id: UUID,
    skill_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific skill.

    Returns:
    - All sources where skill was found
    - Evidence from each source
    - Synonyms and related skills
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
    details = validation_service.get_skill_details(submission_id, skill_name, db)

    return details


@router.get("/{submission_id}/by-category")
def get_skills_by_category(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get skills grouped by category.
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    from app.services.skill_profile_service import get_profile_service
    profile_service = get_profile_service()
    profile = profile_service.build_skill_profile(submission_id, db)

    return {
        "submission_id": str(submission_id),
        "categories": profile["skills_by_category"]
    }


@router.get("/{submission_id}/top")
def get_top_skills(
    submission_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get top N skills by confidence score.
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

    top_skills = results["validated_skills"][:limit]

    return {
        "submission_id": str(submission_id),
        "limit": limit,
        "top_skills": top_skills
    }


@router.get("/{submission_id}/relationships")
def get_skill_relationships(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get skill relationships and common stacks.
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    from app.services.skill_profile_service import get_profile_service
    profile_service = get_profile_service()
    profile = profile_service.build_skill_profile(submission_id, db)

    return {
        "submission_id": str(submission_id),
        "skill_relationships": profile["skill_relationships"],
        "recommended_learning": profile["recommended_learning"]
    }


@router.get("/{submission_id}/gaps")
def get_skill_gaps(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get identified skill gaps and recommendations.
    """
    # Verify ownership
    from app.models.cv_submission import CVSubmission
    submission = db.query(CVSubmission).filter(
        CVSubmission.id == str(submission_id),
        CVSubmission.user_id == current_user.id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    from app.services.skill_profile_service import get_profile_service
    profile_service = get_profile_service()
    profile = profile_service.build_skill_profile(submission_id, db)

    return {
        "submission_id": str(submission_id),
        "skill_gaps": profile["skill_gaps"],
        "recommended_learning": profile["recommended_learning"]
    }


@router.post("/normalize")
def normalize_skills(
    skills: List[str],
    current_user: User = Depends(get_current_user)
):
    """
    Normalize a list of skill names to canonical forms.

    Useful for:
    - Cleaning user input
    - Standardizing skill names
    - Removing duplicates
    """
    normalizer = get_normalization_service()
    normalized = normalizer.normalize_skills(skills)

    # Build mapping of original to normalized
    mapping = {}
    for skill in skills:
        normalized_skill = normalizer.normalize_skill(skill)
        if normalized_skill not in mapping:
            mapping[normalized_skill] = []
        mapping[normalized_skill].append(skill)

    return {
        "input_count": len(skills),
        "normalized_count": len(normalized),
        "normalized_skills": normalized,
        "mapping": mapping
    }


@router.get("/categories/list")
def list_categories(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all skill categories.
    """
    categories = [
        {
            "id": "programming_language",
            "name": "Programming Languages",
            "description": "Core programming languages"
        },
        {
            "id": "frontend",
            "name": "Frontend Development",
            "description": "Frontend frameworks and libraries"
        },
        {
            "id": "backend",
            "name": "Backend Development",
            "description": "Backend frameworks and tools"
        },
        {
            "id": "database",
            "name": "Databases",
            "description": "Database systems and technologies"
        },
        {
            "id": "cloud",
            "name": "Cloud Platforms",
            "description": "Cloud infrastructure and services"
        },
        {
            "id": "devops",
            "name": "DevOps & Infrastructure",
            "description": "DevOps tools and practices"
        },
        {
            "id": "machine_learning",
            "name": "Machine Learning & AI",
            "description": "ML/AI frameworks and tools"
        },
        {
            "id": "testing",
            "name": "Testing & QA",
            "description": "Testing frameworks and tools"
        },
        {
            "id": "other",
            "name": "Other Skills",
            "description": "Miscellaneous technical skills"
        }
    ]

    return {"categories": categories}
