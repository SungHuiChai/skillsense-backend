"""
Database connection and session management
Supports PostgreSQL (Supabase)
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings

# Create database engine
# Add connect_args for better IPv6 and SSL support
connect_args = {}
if settings.DATABASE_URL.startswith("postgresql"):
    connect_args = {
        "connect_timeout": 10,
        "options": "-c timezone=utc"
    }

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    Usage in FastAPI endpoints: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    # Import all models here to ensure they're registered
    from app.models import user, cv_submission, extracted_data, collected_data
    Base.metadata.create_all(bind=engine)
