"""
SkillSense API - FastAPI Application
Main application entry point
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db
from app.api import auth, cv_upload, extraction, admin, collection

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Runs on startup and shutdown
    """
    # Startup
    logger.info("Starting SkillSense API...")

    # Initialize database (create tables if they don't exist)
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")

    # Create default admin user if it doesn't exist
    try:
        from app.database import SessionLocal
        from app.models import User
        from app.utils import get_password_hash

        db = SessionLocal()
        admin_exists = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()

        if not admin_exists:
            admin_user = User(
                email=settings.ADMIN_EMAIL,
                password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Default admin user created: {settings.ADMIN_EMAIL}")
        else:
            logger.info("Admin user already exists")

        db.close()
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down SkillSense API...")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered talent identification system - Input Layer API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(cv_upload.router, prefix=settings.API_V1_PREFIX)
app.include_router(extraction.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(collection.router, prefix=settings.API_V1_PREFIX)  # Phase 2


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "skillsense-api"
    }


# API info endpoint
@app.get(f"{settings.API_V1_PREFIX}/info")
async def api_info():
    """Get API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_prefix": settings.API_V1_PREFIX,
        "endpoints": {
            "auth": f"{settings.API_V1_PREFIX}/auth",
            "cv_upload": f"{settings.API_V1_PREFIX}/cv",
            "extraction": f"{settings.API_V1_PREFIX}/extraction",
            "admin": f"{settings.API_V1_PREFIX}/admin",
            "collection": f"{settings.API_V1_PREFIX}/collection"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
