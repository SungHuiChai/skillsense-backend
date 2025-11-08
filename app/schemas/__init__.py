"""
Pydantic schemas for SkillSense API
"""
from app.schemas.user import (
    UserBase, UserCreate, UserLogin, UserUpdate, UserResponse,
    Token, TokenData
)
from app.schemas.cv_submission import (
    CVSubmissionBase, CVSubmissionCreate, CVSubmissionUpdate,
    CVSubmissionResponse, CVSubmissionListResponse, CVUploadResponse
)
from app.schemas.extracted_data import (
    ExtractedDataCreate, ExtractedDataUpdate, ExtractedDataResponse,
    ExtractedDataDetailed, ExtractionStatusResponse,
    UserEditCreate, UserEditResponse,
    PersonalInfo, SocialLinks, WorkExperience, Education, Skill
)

__all__ = [
    # User schemas
    "UserBase", "UserCreate", "UserLogin", "UserUpdate", "UserResponse",
    "Token", "TokenData",
    # CV Submission schemas
    "CVSubmissionBase", "CVSubmissionCreate", "CVSubmissionUpdate",
    "CVSubmissionResponse", "CVSubmissionListResponse", "CVUploadResponse",
    # Extracted Data schemas
    "ExtractedDataCreate", "ExtractedDataUpdate", "ExtractedDataResponse",
    "ExtractedDataDetailed", "ExtractionStatusResponse",
    "UserEditCreate", "UserEditResponse",
    "PersonalInfo", "SocialLinks", "WorkExperience", "Education", "Skill"
]
