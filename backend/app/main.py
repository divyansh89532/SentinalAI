"""
ChronoTrace Backend - Main FastAPI Application

Forensic Video Intelligence Platform powered by AWS Nova and Strands Agents.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.config import get_settings, setup_logging, get_logger
from app.models.database import init_db
from app.router.video import router as video_router

settings = get_settings()
setup_logging(settings)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info(
        "Starting ChronoTrace API",
        version=settings.app_version,
        debug=settings.debug
    )
    
    await init_db()
    logger.info("Database initialized")
    
    settings.ensure_directories()
    logger.info(
        "Storage directories ready",
        videos_dir=str(settings.videos_dir),
        processed_dir=str(settings.processed_dir)
    )
    
    logger.info(
        "ChronoTrace API started successfully",
        host=settings.host,
        port=settings.port
    )
    
    yield
    
    logger.info("Shutting down ChronoTrace API")


app = FastAPI(
    title="ChronoTrace API",
    description="""
    ## Forensic Video Intelligence Platform
    
    ChronoTrace transforms surveillance footage into searchable, actionable intelligence
    using AWS Nova AI and Strands Agents.
    
    ### Features
    
    - **Video Upload & Processing**: Upload videos and automatically process them into searchable segments
    - **AI-Powered Analysis**: Uses AWS Bedrock Nova 2 Lite for intelligent video processing
    - **Automatic Segmentation**: Splits videos into 15-second searchable chunks
    - **Audio Extraction**: Separates audio tracks for audio-based analysis
    - **Thumbnail Generation**: Creates preview thumbnails for each segment
    
    ### AI Agents
    
    1. **Video Processing Agent** 🎬 - Handles video analysis, segmentation, and metadata extraction
    2. **Privacy Guardian Agent** 🔒 - (Coming Soon) Automatic face and license plate blurring
    3. **Embedding Generator Agent** 🧠 - (Coming Soon) Converts videos to searchable vectors
    4. **Anomaly Detection Agent** ⚠️ - (Coming Soon) Flags suspicious activities
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests with timing information."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


app.include_router(video_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Forensic Video Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "service": "chronotrace-api",
    }


@app.get("/api/v1/config", tags=["Config"])
async def get_config():
    """Get current configuration (non-sensitive values only)."""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "aws_region": settings.aws_region,
        "bedrock_model_id": settings.bedrock_model_id,
        "segment_duration": settings.segment_duration,
        "thumbnail_dimensions": f"{settings.thumbnail_width}x{settings.thumbnail_height}",
        "qdrant_host": settings.qdrant_host,
        "qdrant_port": settings.qdrant_port,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
