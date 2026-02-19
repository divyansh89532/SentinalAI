"""
Video service for handling video upload, storage, and processing orchestration.
"""

import os
import uuid
import aiofiles
from datetime import datetime
from typing import Optional, List, Any
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import UploadFile

from app.config import get_settings, get_logger
from app.models.video import Video, VideoSegment, ProcessingLog, ProcessingStatus
from app.agents.video_processing_agent import VideoProcessingAgent, create_video_processing_agent

logger = get_logger("video_service")
settings = get_settings()


class VideoService:
    """Service for video operations."""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the video service.
        
        Args:
            db: Database session
        """
        self.db = db
        self._agent: Optional[VideoProcessingAgent] = None
    
    @property
    def agent(self) -> VideoProcessingAgent:
        """Lazy-load the video processing agent."""
        if self._agent is None:
            self._agent = create_video_processing_agent()
        return self._agent
    
    async def upload_video(
        self,
        file: UploadFile,
        camera_id: Optional[str] = None,
        location: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> Video:
        """
        Upload and store a video file.
        
        Args:
            file: Uploaded file
            camera_id: Optional camera identifier
            location: Optional location description
            uploaded_by: Optional uploader identifier
        
        Returns:
            Created Video model instance
        """
        video_id = str(uuid.uuid4())
        
        file_extension = Path(file.filename).suffix.lower()
        stored_filename = f"{video_id}{file_extension}"
        file_path = settings.videos_dir / stored_filename
        
        logger.info(
            "Uploading video",
            video_id=video_id,
            original_filename=file.filename,
            stored_filename=stored_filename
        )
        
        file_size = 0
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                await f.write(chunk)
                file_size += len(chunk)
        
        video = Video(
            id=video_id,
            filename=stored_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            status=ProcessingStatus.PENDING,
            camera_id=camera_id,
            location=location,
            uploaded_by=uploaded_by,
        )
        
        self.db.add(video)
        await self.db.flush()
        
        await self._log_processing_step(
            video_id=video_id,
            step="upload",
            status="completed",
            message=f"Video uploaded successfully: {file.filename}",
            details={"file_size": file_size, "stored_path": str(file_path)}
        )
        
        logger.info(
            "Video uploaded successfully",
            video_id=video_id,
            file_size=file_size
        )
        
        return video
    
    async def process_video(
        self,
        video_id: str,
        camera_id: Optional[str] = None,
        location: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process a video using the Video Processing Agent.
        
        Args:
            video_id: Video ID to process
            camera_id: Optional camera identifier (overrides stored value)
            location: Optional location (overrides stored value)
        
        Returns:
            Processing result dictionary
        """
        video = await self.get_video(video_id)
        if not video:
            raise ValueError(f"Video not found: {video_id}")
        
        if camera_id:
            video.camera_id = camera_id
        if location:
            video.location = location
        
        video.status = ProcessingStatus.PROCESSING
        video.processing_started_at = datetime.utcnow()
        await self.db.flush()
        
        await self._log_processing_step(
            video_id=video_id,
            step="processing_start",
            status="started",
            message="Video processing started"
        )
        
        logger.info("Starting video processing", video_id=video_id)
        
        try:
            result = self.agent.process_video(            # this is the main agent that is processing the video, which in turn is calling the tools to process the video. 
                video_path=video.file_path,
                video_id=video_id,
                camera_id=video.camera_id,
                location=video.location,
            )
            
            if result.get("success"):
                await self._update_video_metadata(video, result)
                await self._create_segments_from_result(video_id, result)
                
                video.status = ProcessingStatus.COMPLETED
                video.processing_completed_at = datetime.utcnow()
                
                await self._log_processing_step(
                    video_id=video_id,
                    step="processing_complete",
                    status="completed",
                    message="Video processing completed successfully",
                    details={
                        "processing_time_seconds": result.get("processing_time_seconds"),
                        "segment_count": result.get("segment_count", 0),
                    }
                )
                
                logger.info(
                    "Video processing completed",
                    video_id=video_id,
                    processing_time=result.get("processing_time_seconds")
                )
            else:
                video.status = ProcessingStatus.FAILED
                video.error_message = result.get("error", "Unknown error")
                
                await self._log_processing_step(
                    video_id=video_id,
                    step="processing_failed",
                    status="failed",
                    message=result.get("error", "Unknown error")
                )
                
                logger.error(
                    "Video processing failed",
                    video_id=video_id,
                    error=result.get("error")
                )
            
            await self.db.flush()
            return result
            
        except Exception as e:
            video.status = ProcessingStatus.FAILED
            video.error_message = str(e)
            
            await self._log_processing_step(
                video_id=video_id,
                step="processing_error",
                status="failed",
                message=str(e)
            )
            
            await self.db.flush()
            
            logger.error(
                "Video processing error",
                video_id=video_id,
                error=str(e)
            )
            raise
    
    async def _update_video_metadata(self, video: Video, result: dict) -> None:
        """Update video metadata from processing result."""
        if "metadata" in result:
            metadata = result["metadata"]
            video.duration = metadata.get("duration")
            video.width = metadata.get("width")
            video.height = metadata.get("height")
            video.fps = metadata.get("fps")
            video.codec = metadata.get("codec")
            video.bitrate = metadata.get("bitrate")
    
    async def _create_segments_from_result(
        self,
        video_id: str,
        result: dict
    ) -> List[VideoSegment]:
        """Create VideoSegment records from processing result."""
        segments = []
        
        output_dir = result.get("output_dir", "")
        thumbnails_dir = result.get("thumbnails_dir", "")
        
        if output_dir and os.path.exists(output_dir):
            segment_files = sorted([
                f for f in os.listdir(output_dir)
                if f.endswith(".mp4") and "_segment_" in f
            ])
            
            for idx, seg_file in enumerate(segment_files):
                segment_id = str(uuid.uuid4())
                seg_path = os.path.join(output_dir, seg_file)
                
                thumb_path = None
                thumb_file = f"{video_id}_segment_{idx:03d}_thumb.jpg"
                potential_thumb = os.path.join(thumbnails_dir, thumb_file)
                if os.path.exists(potential_thumb):
                    thumb_path = potential_thumb
                
                file_size = os.path.getsize(seg_path) if os.path.exists(seg_path) else None
                
                segment = VideoSegment(
                    id=segment_id,
                    video_id=video_id,
                    segment_index=idx,
                    file_path=seg_path,
                    thumbnail_path=thumb_path,
                    start_time=idx * settings.segment_duration,
                    end_time=(idx + 1) * settings.segment_duration,
                    duration=settings.segment_duration,
                    file_size=file_size,
                )
                
                self.db.add(segment)
                segments.append(segment)
                
                logger.debug(
                    "Created segment record",
                    video_id=video_id,
                    segment_index=idx,
                    segment_id=segment_id
                )
        
        await self.db.flush()
        return segments
    
    async def _log_processing_step(
        self,
        video_id: str,
        step: str,
        status: str,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> ProcessingLog:
        """Log a processing step."""
        log = ProcessingLog(
            video_id=video_id,
            step=step,
            status=status,
            message=message,
            details=details,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if status in ["completed", "failed"] else None,
        )
        self.db.add(log)
        await self.db.flush()
        return log
    
    async def get_video(self, video_id: str) -> Optional[Video]:
        """
        Get a video by ID.
        
        Args:
            video_id: Video ID
        
        Returns:
            Video instance or None
        """
        result = await self.db.execute(
            select(Video)
            .options(
                selectinload(Video.segments),
                selectinload(Video.processing_logs)
            )
            .where(Video.id == video_id)
        )
        return result.scalar_one_or_none()
    
    async def list_videos(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ProcessingStatus] = None,
    ) -> tuple[List[Video], int]:
        """
        List videos with pagination.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            status: Optional status filter
        
        Returns:
            Tuple of (videos list, total count)
        """
        query = select(Video).options(
            selectinload(Video.segments),
            selectinload(Video.processing_logs)
        )
        
        if status:
            query = query.where(Video.status == status)
        
        count_result = await self.db.execute(
            select(Video.id).where(Video.status == status) if status
            else select(Video.id)
        )
        total = len(count_result.all())
        
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(Video.created_at.desc())
        
        result = await self.db.execute(query)
        videos = result.scalars().all()
        
        return list(videos), total
    
    async def delete_video(self, video_id: str) -> bool:
        """
        Delete a video and its associated files.
        
        Args:
            video_id: Video ID to delete
        
        Returns:
            True if deleted, False if not found
        """
        video = await self.get_video(video_id)
        if not video:
            return False
        
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
        
        for segment in video.segments:
            if segment.file_path and os.path.exists(segment.file_path):
                os.remove(segment.file_path)
            if segment.thumbnail_path and os.path.exists(segment.thumbnail_path):
                os.remove(segment.thumbnail_path)
            if segment.audio_path and os.path.exists(segment.audio_path):
                os.remove(segment.audio_path)
        
        await self.db.delete(video)
        await self.db.flush()
        
        logger.info("Video deleted", video_id=video_id)
        return True
    
    def get_agent_info(self) -> dict[str, Any]:
        """Get information about the video processing agent."""
        return self.agent.get_agent_info()
