"""
Migration: Add GPT-enhanced data collection fields
Date: 2025-01-09

Changes:
1. Add readme_samples, commit_samples, commit_statistics to github_data table
2. Create linkedin_data table for LinkedIn profile data
3. Add linkedin_data relationship to collected_sources
"""

import logging
from sqlalchemy import text, Column, String, Text, Date, Numeric, DateTime, JSON
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)


def column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='{table_name}' AND column_name='{column_name}'
            """))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking column existence: {e}")
        return False


def table_exists(engine, table_name: str) -> bool:
    """Check if a table exists"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name='{table_name}'
            """))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking table existence: {e}")
        return False


def upgrade(engine):
    """Apply migration"""
    logger.info("Running migration: 001_add_gpt_data_collection")

    try:
        with engine.connect() as conn:
            # 1. Add new columns to github_data table
            logger.info("Adding new columns to github_data table...")

            if not column_exists(engine, 'github_data', 'readme_samples'):
                conn.execute(text("""
                    ALTER TABLE github_data
                    ADD COLUMN readme_samples JSON
                """))
                conn.commit()
                logger.info("✓ Added readme_samples column")
            else:
                logger.info("✓ Column readme_samples already exists")

            if not column_exists(engine, 'github_data', 'commit_samples'):
                conn.execute(text("""
                    ALTER TABLE github_data
                    ADD COLUMN commit_samples JSON
                """))
                conn.commit()
                logger.info("✓ Added commit_samples column")
            else:
                logger.info("✓ Column commit_samples already exists")

            if not column_exists(engine, 'github_data', 'commit_statistics'):
                conn.execute(text("""
                    ALTER TABLE github_data
                    ADD COLUMN commit_statistics JSON
                """))
                conn.commit()
                logger.info("✓ Added commit_statistics column")
            else:
                logger.info("✓ Column commit_statistics already exists")

            # 2. Create linkedin_data table
            logger.info("Creating linkedin_data table...")

            if not table_exists(engine, 'linkedin_data'):
                conn.execute(text("""
                    CREATE TABLE linkedin_data (
                        id VARCHAR(36) PRIMARY KEY,
                        source_id VARCHAR(36) NOT NULL,
                        submission_id VARCHAR(36) NOT NULL UNIQUE,
                        profile_url VARCHAR(500) NOT NULL,
                        username VARCHAR(255),
                        full_name VARCHAR(255),
                        headline TEXT,
                        summary TEXT,
                        experience JSON,
                        education JSON,
                        certifications JSON,
                        skills JSON,
                        recommendations JSON,
                        posts_sample JSON,
                        data_source VARCHAR(50),
                        collection_method VARCHAR(50),
                        error_message TEXT,
                        raw_search_results JSON,
                        collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        CONSTRAINT fk_linkedin_source
                            FOREIGN KEY (source_id)
                            REFERENCES collected_sources(id)
                            ON DELETE CASCADE,
                        CONSTRAINT fk_linkedin_submission
                            FOREIGN KEY (submission_id)
                            REFERENCES cv_submissions(id)
                            ON DELETE CASCADE
                    )
                """))
                conn.commit()
                logger.info("✓ Created linkedin_data table")

                # Create indexes
                conn.execute(text("""
                    CREATE INDEX idx_linkedin_data_id ON linkedin_data(id)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_linkedin_data_source_id ON linkedin_data(source_id)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_linkedin_data_submission_id ON linkedin_data(submission_id)
                """))
                conn.execute(text("""
                    CREATE INDEX idx_linkedin_data_username ON linkedin_data(username)
                """))
                conn.commit()
                logger.info("✓ Created indexes for linkedin_data table")
            else:
                logger.info("✓ Table linkedin_data already exists")

            logger.info("✅ Migration completed successfully!")
            return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def downgrade(engine):
    """Rollback migration"""
    logger.info("Rolling back migration: 001_add_gpt_data_collection")

    try:
        with engine.connect() as conn:
            # Remove columns from github_data
            if column_exists(engine, 'github_data', 'readme_samples'):
                conn.execute(text("ALTER TABLE github_data DROP COLUMN readme_samples"))
                conn.commit()
                logger.info("✓ Removed readme_samples column")

            if column_exists(engine, 'github_data', 'commit_samples'):
                conn.execute(text("ALTER TABLE github_data DROP COLUMN commit_samples"))
                conn.commit()
                logger.info("✓ Removed commit_samples column")

            if column_exists(engine, 'github_data', 'commit_statistics'):
                conn.execute(text("ALTER TABLE github_data DROP COLUMN commit_statistics"))
                conn.commit()
                logger.info("✓ Removed commit_statistics column")

            # Drop linkedin_data table
            if table_exists(engine, 'linkedin_data'):
                conn.execute(text("DROP TABLE linkedin_data CASCADE"))
                conn.commit()
                logger.info("✓ Dropped linkedin_data table")

            logger.info("✅ Rollback completed successfully!")
            return True

    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        raise


if __name__ == "__main__":
    """Run migration directly"""
    import sys
    from app.database import engine

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade(engine)
    else:
        upgrade(engine)
