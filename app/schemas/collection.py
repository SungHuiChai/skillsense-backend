"""
Pydantic schemas for data collection API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class CollectionRequest(BaseModel):
    """Request schema for starting data collection"""
    force_refresh: Optional[bool] = Field(
        default=False,
        description="Force re-collection even if data already exists"
    )


class CollectionResponse(BaseModel):
    """Response schema for collection start"""
    submission_id: UUID
    status: str
    message: str

    class Config:
        from_attributes = True


class SourceStatus(BaseModel):
    """Status of a single data source"""
    type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class CollectionStatusResponse(BaseModel):
    """Response schema for collection status"""
    submission_id: UUID
    total_sources: int
    sources: List[SourceStatus]

    class Config:
        from_attributes = True


class GitHubDataResponse(BaseModel):
    """GitHub data in collection results"""
    username: Optional[str] = None
    name: Optional[str] = None
    repos: Optional[int] = None
    languages: Optional[Dict[str, int]] = None
    technologies: Optional[List[str]] = None

    class Config:
        from_attributes = True


class WebMentionResponse(BaseModel):
    """Web mention data in collection results"""
    title: Optional[str] = None
    url: str
    source: Optional[str] = None
    relevance_score: Optional[float] = None

    class Config:
        from_attributes = True


class AggregatedDataResponse(BaseModel):
    """Aggregated profile data in collection results"""
    name: Optional[str] = None
    skills_count: int = 0
    overall_quality_score: Optional[float] = None

    class Config:
        from_attributes = True


class CollectionResultsResponse(BaseModel):
    """Response schema for collection results"""
    submission_id: UUID
    github: Optional[GitHubDataResponse] = None
    web_mentions: List[WebMentionResponse] = []
    aggregated: Optional[AggregatedDataResponse] = None

    class Config:
        from_attributes = True
