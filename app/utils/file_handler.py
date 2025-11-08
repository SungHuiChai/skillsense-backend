"""
File handling utilities for CV uploads
"""
import os
import uuid
from pathlib import Path
from typing import Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from app.config import settings


def validate_file_type(filename: str) -> str:
    """
    Validate file type based on extension

    Args:
        filename: Name of uploaded file

    Returns:
        str: File extension (pdf, docx, txt)

    Raises:
        HTTPException: If file type is not allowed
    """
    file_extension = filename.split('.')[-1].lower()

    if file_extension not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type .{file_extension} is not allowed. Allowed types: {', '.join(settings.allowed_extensions_list)}"
        )

    return file_extension


def validate_file_size(file_size: int) -> None:
    """
    Validate file size

    Args:
        file_size: Size of file in bytes

    Raises:
        HTTPException: If file size exceeds maximum
    """
    if file_size > settings.MAX_FILE_SIZE:
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename to avoid collisions

    Args:
        original_filename: Original filename from upload

    Returns:
        str: Unique filename with UUID prefix
    """
    file_extension = original_filename.split('.')[-1].lower()
    unique_id = str(uuid.uuid4())
    return f"{unique_id}.{file_extension}"


async def save_upload_file(upload_file: UploadFile, user_id: str) -> Tuple[str, int]:
    """
    Save uploaded file to disk

    Args:
        upload_file: FastAPI UploadFile object
        user_id: UUID of user uploading file

    Returns:
        Tuple[str, int]: File path and file size

    Raises:
        HTTPException: If file save fails
    """
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Create user-specific subdirectory
        user_dir = upload_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        unique_filename = generate_unique_filename(upload_file.filename)
        file_path = user_dir / unique_filename

        # Read and save file
        contents = await upload_file.read()
        file_size = len(contents)

        # Validate file size
        validate_file_size(file_size)

        # Write file to disk
        with open(file_path, 'wb') as f:
            f.write(contents)

        return str(file_path), file_size

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


def delete_file(file_path: str) -> bool:
    """
    Delete a file from disk

    Args:
        file_path: Path to file to delete

    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False


def get_file_size(file_path: str) -> Optional[int]:
    """
    Get size of a file

    Args:
        file_path: Path to file

    Returns:
        Optional[int]: File size in bytes, None if file doesn't exist
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return None
    except Exception:
        return None
