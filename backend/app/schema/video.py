"""
Pydantic schemas for video-related API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Video metadata extracted during analysis."""
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    width: Optional[int] = Field(None, description="Video width in pixels")
    height: Optional[int] = Field(None, description="Video height in pixels")
    fps: Optional[float] = Field(None, description="Frames per second")
    codec: Optional[str] = Field(None, description="Video codec")
    bitrate: Optional[int] = Field(None, description="Video bitrate in bps")
    file_size: int = Field(..., description="File size in bytes")
    has_audio: bool = Field(False, description="Whether video has audio track")


class VideoUploadResponse(BaseModel):
    """Response after video upload."""
    success: bool = Field(..., description="Whether upload was successful")
    video_id: str = Field(..., description="Unique video identifier")
    filename: str = Field(..., description="Stored filename")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Upload timestamp")


class VideoProcessingRequest(BaseModel):
    """Request to process a video."""
    video_id: str = Field(..., description="Video ID to process")
    camera_id: Optional[str] = Field(None, description="Camera identifier")
    location: Optional[str] = Field(None, description="Camera location")
    segment_duration: Optional[int] = Field(15, description="Segment duration in seconds")


class VideoSegmentResponse(BaseModel):
    """Information about a video segment."""
    id: str = Field(..., description="Segment ID")
    segment_index: int = Field(..., description="Segment index (0-based)")
    file_path: str = Field(..., description="Path to segment file")
    thumbnail_path: Optional[str] = Field(None, description="Path to thumbnail")
    audio_path: Optional[str] = Field(None, description="Path to audio file")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    duration: float = Field(..., description="Segment duration in seconds")
    file_size: Optional[int] = Field(None, description="Segment file size")
    has_faces: Optional[bool] = Field(None, description="Whether faces were detected")
    face_count: Optional[int] = Field(None, description="Number of faces detected")
    embedding_generated: bool = Field(False, description="Whether embedding was generated")


class ProcessingLogResponse(BaseModel):
    """Processing log entry."""
    id: int = Field(..., description="Log entry ID")
    step: str = Field(..., description="Processing step name")
    status: str = Field(..., description="Step status")
    message: Optional[str] = Field(None, description="Log message")
    details: Optional[dict] = Field(None, description="Additional details")
    started_at: datetime = Field(..., description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    duration_ms: Optional[int] = Field(None, description="Step duration in milliseconds")


class VideoProcessingResponse(BaseModel):
    """Response after video processing."""
    success: bool = Field(..., description="Whether processing was successful")
    video_id: str = Field(..., description="Video ID")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    metadata: Optional[VideoMetadata] = Field(None, description="Video metadata")
    segments: List[VideoSegmentResponse] = Field(default_factory=list, description="Created segments")
    segment_count: int = Field(0, description="Number of segments created")
    processing_time_seconds: Optional[float] = Field(None, description="Total processing time")
    agent_response: Optional[str] = Field(None, description="Agent response summary")
    error: Optional[str] = Field(None, description="Error message if failed")


class VideoDetailResponse(BaseModel):
    """Detailed video information."""
    id: str = Field(..., description="Video ID")
    filename: str = Field(..., description="Stored filename")
    original_filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to video file")
    file_size: int = Field(..., description="File size in bytes")
    
    # Metadata
    duration: Optional[float] = Field(None, description="Duration in seconds")
    width: Optional[int] = Field(None, description="Width in pixels")
    height: Optional[int] = Field(None, description="Height in pixels")
    fps: Optional[float] = Field(None, description="Frames per second")
    codec: Optional[str] = Field(None, description="Video codec")
    bitrate: Optional[int] = Field(None, description="Bitrate in bps")
    
    # Status
    status: str = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # User metadata
    camera_id: Optional[str] = Field(None, description="Camera identifier")
    location: Optional[str] = Field(None, description="Camera location")
    uploaded_by: Optional[str] = Field(None, description="Uploader identifier")
    
    # Timestamps
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    
    # Related data
    segments: List[VideoSegmentResponse] = Field(default_factory=list, description="Video segments")
    processing_logs: List[ProcessingLogResponse] = Field(default_factory=list, description="Processing logs")
    
    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    """Response for listing videos."""
    videos: List[VideoDetailResponse] = Field(..., description="List of videos")
    total: int = Field(..., description="Total number of videos")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Page size")


class AgentInfoResponse(BaseModel):
    """Information about the Video Processing Agent."""
    name: str = Field(..., description="Agent name")
    model_id: str = Field(..., description="LLM model ID")
    region: str = Field(..., description="AWS region")
    tools: List[str] = Field(..., description="Available tools")
    segment_duration: int = Field(..., description="Default segment duration")
    thumbnail_dimensions: str = Field(..., description="Thumbnail dimensions")
