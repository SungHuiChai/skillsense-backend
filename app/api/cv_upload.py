"""
CV Upload API endpoints
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import User, CVSubmission, ExtractedData
from app.schemas import CVUploadResponse
from app.core import get_current_user
from app.utils import validate_file_type, save_upload_file
from app.services import CVParser, DataExtractor

router = APIRouter(prefix="/cv", tags=["CV Upload"])


async def process_cv_extraction(
    submission_id: str,
    file_path: str,
    file_type: str,
    db_connection_string: str
):
    """
    Background task to process CV extraction

    Args:
        submission_id: UUID of CV submission
        file_path: Path to uploaded file
        file_type: Type of file
        db_connection_string: Database connection string
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Create new database session for background task
    engine = create_engine(db_connection_string)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Update submission status to processing
        submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()
        if not submission:
            return

        submission.status = "processing"
        db.commit()

        # Parse CV
        raw_text, parse_method = CVParser.parse_cv(file_path, file_type)

        if not raw_text:
            submission.status = "failed"
            submission.error_message = f"Failed to parse {file_type} file"
            db.commit()
            return

        # Extract data
        email, email_conf = DataExtractor.extract_email(raw_text)
        phone, phone_conf = DataExtractor.extract_phone(raw_text)
        social_links = DataExtractor.extract_social_links(raw_text)
        work_history = DataExtractor.extract_work_history(raw_text)
        education = DataExtractor.extract_education(raw_text)
        skills = DataExtractor.extract_skills(raw_text)

        # Prepare extracted data
        extracted_data_dict = {
            'email': email,
            'email_confidence': email_conf,
            'phone': phone,
            'phone_confidence': phone_conf,
            'github_url': social_links['github'][0],
            'github_url_confidence': social_links['github'][1],
            'linkedin_url': social_links['linkedin'][0],
            'linkedin_url_confidence': social_links['linkedin'][1],
            'portfolio_url': social_links['portfolio'][0],
            'portfolio_url_confidence': social_links['portfolio'][1],
            'twitter_url': social_links['twitter'][0],
            'twitter_url_confidence': social_links['twitter'][1],
            'work_history': work_history,
            'education': education,
            'skills': skills,
            'raw_text': raw_text,
            'extraction_method': f"regex+{parse_method}"
        }

        # Calculate overall confidence
        overall_confidence = DataExtractor.calculate_overall_confidence(extracted_data_dict)
        extracted_data_dict['overall_confidence'] = overall_confidence

        # Create ExtractedData record
        extracted_data = ExtractedData(
            submission_id=submission_id,
            **extracted_data_dict
        )

        db.add(extracted_data)

        # Update submission status
        submission.status = "extracted"
        submission.processed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        submission = db.query(CVSubmission).filter(CVSubmission.id == submission_id).first()
        if submission:
            submission.status = "failed"
            submission.error_message = f"Extraction error: {str(e)}"
            db.commit()

    finally:
        db.close()


@router.post("/upload", response_model=CVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload CV file for processing

    Args:
        file: Uploaded CV file (PDF, DOCX, TXT)
        current_user: Current authenticated user
        db: Database session

    Returns:
        CVUploadResponse: Upload confirmation with submission ID

    Raises:
        HTTPException: If file validation fails
    """
    # Validate file type
    file_type = validate_file_type(file.filename)

    # Save file to disk
    file_path, file_size = await save_upload_file(file, str(current_user.id))

    # Create CV submission record
    submission = CVSubmission(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        file_type=file_type,
        status="uploaded"
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Add background task to process CV
    from app.config import settings
    background_tasks.add_task(
        process_cv_extraction,
        str(submission.id),
        file_path,
        file_type,
        settings.DATABASE_URL
    )

    return CVUploadResponse(
        submission_id=submission.id,
        filename=file.filename,
        status=submission.status,
        message="CV uploaded successfully. Processing will begin shortly."
    )


@router.get("/submissions", response_model=list)
async def get_my_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all CV submissions for current user

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List: List of user's CV submissions
    """
    submissions = db.query(CVSubmission).filter(
        CVSubmission.user_id == current_user.id
    ).order_by(CVSubmission.uploaded_at.desc()).all()

    return submissions
