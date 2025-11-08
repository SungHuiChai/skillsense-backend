"""
Pydantic schemas for CV Submission model
"""
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


class CVSubmissionBase(BaseModel):
    """Base CV submission schema"""
    filename: str
    file_type: str  # 'pdf', 'docx', 'txt'


class CVSubmissionCreate(CVSubmissionBase):
    """Schema for creating a new CV submission"""
    file_path: str
    file_size: int
    user_id: UUID


class CVSubmissionUpdate(BaseModel):
    """Schema for updating CV submission"""
    status: Optional[str] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CVSubmissionResponse(CVSubmissionBase):
    """Schema for CV submission response"""
    id: UUID
    user_id: UUID
    file_path: str
    file_size: int
    status: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class CVSubmissionListResponse(BaseModel):
    """Schema for CV submission list response (admin)"""
    id: UUID
    user_email: str = Field(..., description="Email of user who uploaded")
    filename: str
    file_type: str
    status: str
    uploaded_at: datetime
    overall_confidence: Optional[float] = Field(None, description="Overall extraction confidence")

    model_config = {
        "from_attributes": True
    }


class CVUploadResponse(BaseModel):
    """Response after successful CV upload"""
    submission_id: UUID
    filename: str
    status: str
    message: str
