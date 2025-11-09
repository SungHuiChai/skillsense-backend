"""
Cleanup script to keep only the latest CV submission per user
"""
import os
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models import CVSubmission, ExtractedData
from app.config import settings

def cleanup_old_submissions():
    """
    For each user, keep only the most recent CV submission and delete all older ones
    """
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Get all users who have CV submissions
        users_with_submissions = db.query(CVSubmission.user_id).distinct().all()

        total_deleted = 0
        total_files_deleted = 0

        for (user_id,) in users_with_submissions:
            # Get all submissions for this user, ordered by upload date (newest first)
            submissions = db.query(CVSubmission).filter(
                CVSubmission.user_id == user_id
            ).order_by(CVSubmission.uploaded_at.desc()).all()

            if len(submissions) > 1:
                # Keep the first (newest) one, delete the rest
                submissions_to_delete = submissions[1:]

                print(f"\nUser {user_id}:")
                print(f"  Total submissions: {len(submissions)}")
                print(f"  Keeping: {submissions[0].filename} (uploaded {submissions[0].uploaded_at})")
                print(f"  Deleting {len(submissions_to_delete)} old submission(s):")

                for sub in submissions_to_delete:
                    print(f"    - {sub.filename} (uploaded {sub.uploaded_at})")

                    # Delete file from disk
                    if sub.file_path and os.path.exists(sub.file_path):
                        try:
                            os.remove(sub.file_path)
                            print(f"      ✓ Deleted file: {sub.file_path}")
                            total_files_deleted += 1
                        except Exception as e:
                            print(f"      ✗ Failed to delete file: {e}")

                    # Delete submission record (CASCADE will handle extracted_data)
                    db.delete(sub)
                    total_deleted += 1

        # Commit all deletions
        db.commit()

        print(f"\n{'='*60}")
        print(f"Cleanup complete!")
        print(f"Total submissions deleted: {total_deleted}")
        print(f"Total files deleted: {total_files_deleted}")
        print(f"{'='*60}\n")

    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_old_submissions()
