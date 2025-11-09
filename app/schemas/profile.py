"""
Pydantic schemas for Profile/User endpoints
"""
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class SocialLinksUpdate(BaseModel):
    """Schema for updating social links"""
    github: Optional[str] = Field(None, description="GitHub profile URL")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    portfolio: Optional[str] = Field(None, description="Portfolio website URL")
    twitter: Optional[str] = Field(None, description="Twitter/X profile URL")

    @field_validator('github', 'linkedin', 'portfolio', 'twitter')
    @classmethod
    def validate_url_format(cls, v):
        """Validate URL format if provided"""
        if v and v.strip():
            # Basic URL validation
            v = v.strip()
            if not v.startswith(('http://', 'https://')):
                v = 'https://' + v
            return v
        return None


class GitHubValidationRequest(BaseModel):
    """Schema for GitHub URL validation request"""
    github_url: str = Field(..., description="GitHub URL to validate")


class GitHubValidationResponse(BaseModel):
    """Schema for GitHub URL validation response"""
    is_valid_format: bool
    username: Optional[str] = None
    account_exists: Optional[bool] = None
    error_message: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None


class GitHubSyncStatusResponse(BaseModel):
    """Schema for GitHub crawl status response"""
    can_sync: bool
    is_syncing: bool = False
    last_synced_at: Optional[datetime] = None
    next_allowed_at: Optional[datetime] = None
    seconds_remaining: Optional[int] = None
    time_remaining_text: Optional[str] = None
    error_message: Optional[str] = None


class ProfileResponse(BaseModel):
    """Schema for user profile response"""
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    social_links: Optional[Dict[str, Optional[str]]] = None
    latest_submission_id: Optional[str] = None
    created_at: datetime


class SocialLinksUpdateResponse(BaseModel):
    """Schema for social links update response"""
    success: bool
    message: str
    updated_links: Dict[str, Optional[str]]
    github_crawl_triggered: bool = False
    crawl_status: Optional[str] = None
