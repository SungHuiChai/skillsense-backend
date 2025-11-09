"""
SkillSense API - FastAPI Application
Main application entry point
"""
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import asyncio
from typing import Dict, Set

from app.config import settings
from app.database import init_db
from app.api import auth, cv_upload, extraction, admin, collection, profile, processing, skills

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

# Add CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(profile.router, prefix=settings.API_V1_PREFIX)  # Phase 2: Profile
app.include_router(processing.router)  # Phase 3: Processing Layer
app.include_router(skills.router)  # Phase 3: Skills API


# WebSocket Connection Manager
class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""

    def __init__(self):
        # Map submission_id to set of active connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, submission_id: str):
        await websocket.accept()
        if submission_id not in self.active_connections:
            self.active_connections[submission_id] = set()
        self.active_connections[submission_id].add(websocket)
        logger.info(f"WebSocket connected for submission: {submission_id}")

    def disconnect(self, websocket: WebSocket, submission_id: str):
        if submission_id in self.active_connections:
            self.active_connections[submission_id].discard(websocket)
            if not self.active_connections[submission_id]:
                del self.active_connections[submission_id]
        logger.info(f"WebSocket disconnected for submission: {submission_id}")

    async def send_message(self, message: dict, submission_id: str):
        """Send message to all connections for a submission"""
        if submission_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[submission_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending WebSocket message: {e}")
                    dead_connections.add(connection)

            # Clean up dead connections
            for connection in dead_connections:
                self.disconnect(connection, submission_id)

manager = ConnectionManager()


# WebSocket endpoint for real-time collection status
@app.websocket("/ws/collection/{submission_id}")
async def websocket_collection_status(websocket: WebSocket, submission_id: str):
    """
    WebSocket endpoint for real-time collection status updates

    Args:
        websocket: WebSocket connection
        submission_id: CV submission ID to monitor
    """
    await manager.connect(websocket, submission_id)

    try:
        # Send initial status
        from app.database import SessionLocal
        from app.models.collected_data import CollectedSource

        db = SessionLocal()
        try:
            sources = db.query(CollectedSource).filter(
                CollectedSource.submission_id == submission_id
            ).all()

            await websocket.send_json({
                "type": "initial_status",
                "submission_id": submission_id,
                "sources": [{
                    "source_type": s.source_type,
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "error_message": s.error_message
                } for s in sources]
            })
        finally:
            db.close()

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for messages (ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Check status and send updates
                db = SessionLocal()
                try:
                    sources = db.query(CollectedSource).filter(
                        CollectedSource.submission_id == submission_id
                    ).all()

                    await websocket.send_json({
                        "type": "status_update",
                        "submission_id": submission_id,
                        "sources": [{
                            "source_type": s.source_type,
                            "status": s.status,
                            "started_at": s.started_at.isoformat() if s.started_at else None,
                            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                            "error_message": s.error_message
                        } for s in sources]
                    })
                finally:
                    db.close()

            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, submission_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, submission_id)


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
            "collection": f"{settings.API_V1_PREFIX}/collection",
            "profile": f"{settings.API_V1_PREFIX}/profile",
            "processing": f"{settings.API_V1_PREFIX}/processing",
            "skills": f"{settings.API_V1_PREFIX}/skills"
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
