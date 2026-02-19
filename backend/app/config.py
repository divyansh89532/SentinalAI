"""
Configuration module for ChronoTrace backend.
Handles all application settings, AWS configuration, and logging setup.
"""

import os
import logging
import structlog
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application Settings
    app_name: str = "ChronoTrace"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # AWS Settings
    aws_region: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: str | None = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: str | None = Field(default=None, description="AWS secret access key")
    
    # AWS Bedrock Model Settings
    bedrock_model_id: str = Field(
        default="us.amazon.nova-lite-v1:0",
        description="AWS Bedrock model ID for Nova 2 Lite"
    )
    bedrock_embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="AWS Bedrock embedding model ID"
    )
    
    # Database Settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/chronotrace.db",
        description="Database connection URL"
    )
    
    # Storage Paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    videos_dir: Path = Field(default=Path("./data/videos"), description="Raw videos directory")
    processed_dir: Path = Field(default=Path("./data/processed"), description="Processed videos directory")
    thumbnails_dir: Path = Field(default=Path("./data/thumbnails"), description="Thumbnails directory")
    audio_dir: Path = Field(default=Path("./data/audio"), description="Audio files directory")
    
    # Video Processing Settings
    segment_duration: int = Field(default=15, description="Video segment duration in seconds")
    thumbnail_timestamp: int = Field(default=3, description="Timestamp for thumbnail extraction in seconds")
    thumbnail_width: int = Field(default=320, description="Thumbnail width")
    thumbnail_height: int = Field(default=180, description="Thumbnail height")
    
    # Qdrant Settings
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant port")
    qdrant_collection: str = Field(default="video_segments", description="Qdrant collection name")
    embedding_dimension: int = Field(default=1024, description="Embedding vector dimension")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or console)")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        directories = [
            self.data_dir,
            self.videos_dir,
            self.processed_dir,
            self.thumbnails_dir,
            self.audio_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings


def setup_logging(settings: Settings | None = None) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.
    
    Args:
        settings: Application settings. If None, will fetch from get_settings().
    
    Returns:
        Configured structlog logger.
    """
    if settings is None:
        settings = get_settings()
    
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    structlog.configure(
        processors=shared_processors + [
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[logging.StreamHandler()],
    )
    
    for logger_name in ["boto3", "botocore", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    return structlog.get_logger()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance with optional name binding.
    
    Args:
        name: Optional logger name to bind.
    
    Returns:
        Configured structlog logger.
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger_name=name)
    return logger
