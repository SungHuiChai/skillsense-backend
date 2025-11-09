"""
CV Submission model for tracking uploaded CVs
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class CVSubmission(Base):
    """CV Submission model for tracking uploaded files"""
    __tablename__ = "cv_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))  # 'pdf', 'docx', 'txt'
    status = Column(String(50), default="uploaded", index=True)
    # Status values: 'uploaded', 'processing', 'extracted', 'validated', 'completed', 'failed'
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="cv_submissions")
    extracted_data = relationship("ExtractedData", back_populates="submission", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CVSubmission {self.filename} - {self.status}>"
