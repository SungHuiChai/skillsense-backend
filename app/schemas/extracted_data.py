"""
Pydantic schemas for Extracted Data model
"""
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from decimal import Decimal


class FieldWithConfidence(BaseModel):
    """Generic schema for a field with confidence score"""
    value: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=100, description="Confidence score 0-100")


class WorkExperience(BaseModel):
    """Schema for work experience entry"""
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=100)


class Education(BaseModel):
    """Schema for education entry"""
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    year: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=100)


class Skill(BaseModel):
    """Schema for skill entry"""
    name: str
    confidence: Optional[float] = Field(None, ge=0, le=100)


class PersonalInfo(BaseModel):
    """Schema for personal information"""
    full_name: FieldWithConfidence
    email: FieldWithConfidence
    phone: FieldWithConfidence
    location: FieldWithConfidence


class SocialLinks(BaseModel):
    """Schema for social media links"""
    github: FieldWithConfidence
    linkedin: FieldWithConfidence
    portfolio: FieldWithConfidence
    twitter: FieldWithConfidence
    other: Optional[List[Dict[str, Any]]] = []


class ExtractedDataBase(BaseModel):
    """Base schema for extracted data"""
    submission_id: UUID


class ExtractedDataCreate(ExtractedDataBase):
    """Schema for creating extracted data"""
    # Personal Information
    full_name: Optional[str] = None
    full_name_confidence: Optional[float] = None
    email: Optional[str] = None
    email_confidence: Optional[float] = None
    phone: Optional[str] = None
    phone_confidence: Optional[float] = None
    location: Optional[str] = None
    location_confidence: Optional[float] = None

    # Social Media Links
    github_url: Optional[str] = None
    github_url_confidence: Optional[float] = None
    linkedin_url: Optional[str] = None
    linkedin_url_confidence: Optional[float] = None
    portfolio_url: Optional[str] = None
    portfolio_url_confidence: Optional[float] = None
    twitter_url: Optional[str] = None
    twitter_url_confidence: Optional[float] = None
    other_urls: Optional[str] = None

    # Extracted Sections
    work_history: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    languages: Optional[List[str]] = None

    # Metadata
    extraction_method: Optional[str] = None
    overall_confidence: Optional[float] = None
    raw_text: Optional[str] = None


class ExtractedDataUpdate(BaseModel):
    """Schema for updating extracted data (user validation)"""
    # Personal Information
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    # Social Media Links
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    twitter_url: Optional[str] = None

    # Extracted Sections
    work_history: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None

    # Validation Status
    is_validated: Optional[bool] = None
    validation_notes: Optional[str] = None


class ExtractedDataResponse(BaseModel):
    """Schema for extracted data response (formatted)"""
    submission_id: UUID
    status: str
    extracted_data: Dict[str, Any]
    overall_confidence: Optional[float] = None
    extracted_at: datetime


class ExtractedDataDetailed(BaseModel):
    """Detailed schema for extracted data with all fields"""
    id: UUID
    submission_id: UUID
    personal_info: PersonalInfo
    social_links: SocialLinks
    work_history: List[WorkExperience] = []
    education: List[Education] = []
    skills: List[Skill] = []
    certifications: List[Dict[str, Any]] = []
    languages: List[str] = []
    extraction_method: Optional[str] = None
    overall_confidence: Optional[float] = None
    is_validated: bool = False
    validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class UserEditCreate(BaseModel):
    """Schema for creating user edit record"""
    extracted_data_id: UUID
    field_name: str
    original_value: Optional[str] = None
    edited_value: Optional[str] = None


class UserEditResponse(BaseModel):
    """Schema for user edit response"""
    id: UUID
    extracted_data_id: UUID
    field_name: str
    original_value: Optional[str] = None
    edited_value: Optional[str] = None
    edited_at: datetime

    model_config = {
        "from_attributes": True
    }


class ExtractionStatusResponse(BaseModel):
    """Schema for extraction status check"""
    submission_id: UUID
    status: str
    message: str
    progress: Optional[int] = Field(None, ge=0, le=100, description="Processing progress 0-100")
