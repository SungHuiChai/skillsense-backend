"""
HR API Endpoints
- Get all candidates with comprehensive data
- Match candidates to job description
- Get candidate summary statistics
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import User
from app.core import get_current_admin
from app.services.candidate_aggregation_service import CandidateAggregationService
from app.services.job_matching_service import JobMatchingService

router = APIRouter(prefix="/hr", tags=["HR Dashboard"])


class JobDescriptionRequest(BaseModel):
    """Request model for job matching"""
    job_description: str = Field(..., min_length=50, description="Job description text (minimum 50 characters)")
    top_n: Optional[int] = Field(None, ge=1, le=100, description="Limit results to top N candidates")


@router.get("/candidates")
async def get_all_candidates(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all candidates with comprehensive data from all sources

    Requires admin authentication.

    Returns:
        List of candidates with merged data from CV, GitHub, web mentions, Stack Overflow, etc.
    """
    try:
        aggregation_service = CandidateAggregationService(db)
        candidates = await aggregation_service.get_all_candidates()

        return {
            "total_candidates": len(candidates),
            "candidates": candidates
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching candidates: {str(e)}"
        )


@router.get("/candidates/{submission_id}")
async def get_candidate_profile(
    submission_id: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed profile for a single candidate

    Requires admin authentication.

    Args:
        submission_id: CV submission ID

    Returns:
        Comprehensive candidate profile with all data sources
    """
    try:
        aggregation_service = CandidateAggregationService(db)
        candidate = await aggregation_service.get_candidate_profile(submission_id)

        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate with submission_id {submission_id} not found"
            )

        return candidate

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching candidate profile: {str(e)}"
        )


@router.post("/match-candidates")
async def match_candidates(
    request: JobDescriptionRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Match candidates to a job description using AI analysis

    Requires admin authentication.

    This endpoint:
    1. Fetches all candidates with comprehensive data
    2. Sends job description + candidate data to GPT-4o
    3. Returns ranked candidates with detailed match analysis

    Args:
        request: Job description and optional top_n limit

    Returns:
        Ranked candidates with AI-generated match analysis including:
        - Match scores (0-100)
        - Key strengths relevant to the role
        - Potential concerns or gaps
        - Overall assessment
        - Hiring recommendations
    """
    try:
        # Get all candidates
        aggregation_service = CandidateAggregationService(db)
        candidates = await aggregation_service.get_all_candidates()

        if not candidates:
            return {
                "job_description": request.job_description,
                "total_candidates_analyzed": 0,
                "total_matches_returned": 0,
                "matches": [],
                "message": "No candidates available in the system"
            }

        # Match candidates to job
        matching_service = JobMatchingService()
        results = await matching_service.match_candidates_to_job(
            job_description=request.job_description,
            candidates=candidates,
            top_n=request.top_n
        )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error matching candidates: {str(e)}"
        )


@router.get("/summary")
async def get_candidates_summary(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics about all candidates

    Requires admin authentication.

    Returns:
        Aggregate statistics including:
        - Total candidates
        - Candidates with GitHub profiles
        - Candidates with Stack Overflow profiles
        - Total web mentions
    """
    try:
        aggregation_service = CandidateAggregationService(db)
        summary = await aggregation_service.get_candidates_summary()

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching summary: {str(e)}"
        )
