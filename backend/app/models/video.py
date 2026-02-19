"""
Video and VideoSegment database models.
"""

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ProcessingStatus(str, enum.Enum):
    """Status of video processing."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    SEGMENTING = "segmenting"
    EXTRACTING_AUDIO = "extracting_audio"
    GENERATING_THUMBNAILS = "generating_thumbnails"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    """Model representing an uploaded video."""
    
    __tablename__ = "videos"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Video metadata
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    codec: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Processing info
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # User metadata
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    segments: Mapped[List["VideoSegment"]] = relationship(
        "VideoSegment",
        back_populates="video",
        cascade="all, delete-orphan"
    )
    processing_logs: Mapped[List["ProcessingLog"]] = relationship(
        "ProcessingLog",
        back_populates="video",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Video(id={self.id}, filename={self.filename}, status={self.status})>"


class VideoSegment(Base):
    """Model representing a video segment."""
    
    __tablename__ = "video_segments"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # File paths
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Segment timing
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Processing metadata
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_faces: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)
    face_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Embedding info
    embedding_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_generated: Mapped[bool] = mapped_column(Integer, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="segments")
    
    def __repr__(self) -> str:
        return f"<VideoSegment(id={self.id}, video_id={self.video_id}, index={self.segment_index})>"


class ProcessingLog(Base):
    """Model for tracking processing steps and their status."""
    
    __tablename__ = "processing_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Log details
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="processing_logs")
    
    def __repr__(self) -> str:
        return f"<ProcessingLog(id={self.id}, video_id={self.video_id}, step={self.step})>"
