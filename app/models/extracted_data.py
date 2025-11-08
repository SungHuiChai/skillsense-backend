"""
Extracted Data model for storing parsed CV information
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class ExtractedData(Base):
    """Extracted data from CV with confidence scores"""
    __tablename__ = "extracted_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Personal Information
    full_name = Column(String(255))
    full_name_confidence = Column(Numeric(5, 2))  # 0-100
    email = Column(String(255))
    email_confidence = Column(Numeric(5, 2))
    phone = Column(String(50))
    phone_confidence = Column(Numeric(5, 2))
    location = Column(String(255))
    location_confidence = Column(Numeric(5, 2))

    # Social Media Links
    github_url = Column(String(500))
    github_url_confidence = Column(Numeric(5, 2))
    linkedin_url = Column(String(500))
    linkedin_url_confidence = Column(Numeric(5, 2))
    portfolio_url = Column(String(500))
    portfolio_url_confidence = Column(Numeric(5, 2))
    twitter_url = Column(String(500))
    twitter_url_confidence = Column(Numeric(5, 2))
    other_urls = Column(Text)  # JSON string of other URLs

    # Extracted Sections (JSONB for flexible structure)
    work_history = Column(JSONB)  # Array of work experiences
    education = Column(JSONB)  # Array of education entries
    skills = Column(JSONB)  # Array of skills
    certifications = Column(JSONB)  # Array of certifications
    languages = Column(JSONB)  # Array of languages

    # Metadata
    extraction_method = Column(String(50))  # 'regex', 'spacy', 'llm', 'hybrid'
    overall_confidence = Column(Numeric(5, 2))
    raw_text = Column(Text)  # Full extracted text from CV

    # User Validation Status
    is_validated = Column(Boolean, default=False)
    validated_at = Column(DateTime(timezone=True))
    validation_notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    submission = relationship("CVSubmission", back_populates="extracted_data")
    user_edits = relationship("UserEdit", back_populates="extracted_data", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExtractedData {self.full_name} - {self.overall_confidence}%>"


class UserEdit(Base):
    """Track user edits to extracted data"""
    __tablename__ = "user_edits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    extracted_data_id = Column(UUID(as_uuid=True), ForeignKey("extracted_data.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    original_value = Column(Text)
    edited_value = Column(Text)
    edited_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    extracted_data = relationship("ExtractedData", back_populates="user_edits")

    def __repr__(self):
        return f"<UserEdit {self.field_name}>"
