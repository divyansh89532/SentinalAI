"""
Video API endpoints for upload, processing, and retrieval.
"""

from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_logger
from app.models.database import get_db
from app.models.video import ProcessingStatus
from app.services.video_service import VideoService
from app.schema.video import (
    VideoUploadResponse,
    VideoProcessingRequest,
    VideoProcessingResponse,
    VideoDetailResponse,
    VideoListResponse,
    VideoSegmentResponse,
    ProcessingLogResponse,
    AgentInfoResponse,
)

logger = get_logger("video_router")

router = APIRouter(prefix="/videos", tags=["Videos"])


def get_video_service(db: AsyncSession = Depends(get_db)) -> VideoService:
    """Dependency to get video service instance."""
    return VideoService(db)


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(..., description="Video file to upload"),
    camera_id: Optional[str] = Form(None, description="Camera identifier"),
    location: Optional[str] = Form(None, description="Camera location"),
    uploaded_by: Optional[str] = Form(None, description="Uploader identifier"),
    service: VideoService = Depends(get_video_service),
):
    """
    Upload a video file for processing.
    
    The video will be stored and queued for processing. Use the returned
    video_id to check status and trigger processing.
    """
    logger.info(
        "Video upload request",
        filename=file.filename,
        camera_id=camera_id,
        location=location
    )
    
    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        video = await service.upload_video(                                    # this is the main function for uploading the video to the database and the file system note the processing doesn't start automatically here there is a seperate endpoint for this. 
            file=file,
            camera_id=camera_id,
            location=location,
            uploaded_by=uploaded_by,
        )
        
        return VideoUploadResponse(
            success=True,
            video_id=video.id,
            filename=video.filename,
            original_filename=video.original_filename,
            file_size=video.file_size,
            status=video.status.value,
            message="Video uploaded successfully. Ready for processing.",
            created_at=video.created_at,
        )
        
    except Exception as e:
        logger.error("Video upload failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/{video_id}/process", response_model=VideoProcessingResponse)
async def process_video(
    video_id: str,
    camera_id: Optional[str] = None,
    location: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    service: VideoService = Depends(get_video_service),
):
    """
    Process an uploaded video using the Video Processing Agent.
    
    This will:
    1. Analyze video metadata
    2. Split into 15-second segments
    3. Extract audio track
    4. Generate thumbnails for each segment
    
    Processing runs synchronously and returns results when complete.
    """
    logger.info(
        "Video processing request",
        video_id=video_id,
        camera_id=camera_id,
        location=location
    )
    
    video = await service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    if video.status == ProcessingStatus.PROCESSING:                                   # prevents the same video from being processed multiple times. 
        raise HTTPException(
            status_code=409,
            detail="Video is already being processed"
        )
    
    if video.status == ProcessingStatus.COMPLETED:                                    # prevents the same video from being processed multiple times. 
        return VideoProcessingResponse(
            success=True,
            video_id=video_id,
            status=video.status.value,
            message="Video has already been processed",
            segments=[
                VideoSegmentResponse(
                    id=seg.id,
                    segment_index=seg.segment_index,
                    file_path=seg.file_path,
                    thumbnail_path=seg.thumbnail_path,
                    audio_path=seg.audio_path,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    duration=seg.duration,
                    file_size=seg.file_size,
                    has_faces=seg.has_faces,
                    face_count=seg.face_count,
                    embedding_generated=seg.embedding_generated,
                )
                for seg in video.segments
            ],
            segment_count=len(video.segments),
        )

        
        # this is the place where the main code starts for the porcessing if the video is queued for processing. 


    try:
        result = await service.process_video(                                    # this is the main function for processing the video, which in turn is calling the agent to process the video. 
            video_id=video_id,
            camera_id=camera_id,
            location=location,
        )
        
        video = await service.get_video(video_id)
        
        return VideoProcessingResponse(
            success=result.get("success", False),
            video_id=video_id,
            status=video.status.value if video else "unknown",
            message="Video processing completed" if result.get("success") else "Processing failed",
            segments=[
                VideoSegmentResponse(
                    id=seg.id,
                    segment_index=seg.segment_index,
                    file_path=seg.file_path,
                    thumbnail_path=seg.thumbnail_path,
                    audio_path=seg.audio_path,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    duration=seg.duration,
                    file_size=seg.file_size,
                    has_faces=seg.has_faces,
                    face_count=seg.face_count,
                    embedding_generated=seg.embedding_generated,
                )
                for seg in (video.segments if video else [])
            ],
            segment_count=len(video.segments) if video else 0,
            processing_time_seconds=result.get("processing_time_seconds"),
            agent_response=result.get("agent_response"),
            error=result.get("error"),
        )
        
    except Exception as e:
        logger.error("Video processing failed", video_id=video_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video(
    video_id: str,
    service: VideoService = Depends(get_video_service),
):
    """Get detailed information about a video."""
    video = await service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    return VideoDetailResponse(
        id=video.id,
        filename=video.filename,
        original_filename=video.original_filename,
        file_path=video.file_path,
        file_size=video.file_size,
        duration=video.duration,
        width=video.width,
        height=video.height,
        fps=video.fps,
        codec=video.codec,
        bitrate=video.bitrate,
        status=video.status.value,
        error_message=video.error_message,
        camera_id=video.camera_id,
        location=video.location,
        uploaded_by=video.uploaded_by,
        created_at=video.created_at,
        updated_at=video.updated_at,
        processing_started_at=video.processing_started_at,
        processing_completed_at=video.processing_completed_at,
        segments=[
            VideoSegmentResponse(
                id=seg.id,
                segment_index=seg.segment_index,
                file_path=seg.file_path,
                thumbnail_path=seg.thumbnail_path,
                audio_path=seg.audio_path,
                start_time=seg.start_time,
                end_time=seg.end_time,
                duration=seg.duration,
                file_size=seg.file_size,
                has_faces=seg.has_faces,
                face_count=seg.face_count,
                embedding_generated=seg.embedding_generated,
            )
            for seg in video.segments
        ],
        processing_logs=[
            ProcessingLogResponse(
                id=log.id,
                step=log.step,
                status=log.status,
                message=log.message,
                details=log.details,
                started_at=log.started_at,
                completed_at=log.completed_at,
                duration_ms=log.duration_ms,
            )
            for log in video.processing_logs
        ],
    )


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    service: VideoService = Depends(get_video_service),
):
    """List all videos with pagination."""
    status_filter = None
    if status:
        try:
            status_filter = ProcessingStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {[s.value for s in ProcessingStatus]}"
            )
    
    videos, total = await service.list_videos(
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    
    return VideoListResponse(
        videos=[
            VideoDetailResponse(
                id=video.id,
                filename=video.filename,
                original_filename=video.original_filename,
                file_path=video.file_path,
                file_size=video.file_size,
                duration=video.duration,
                width=video.width,
                height=video.height,
                fps=video.fps,
                codec=video.codec,
                bitrate=video.bitrate,
                status=video.status.value,
                error_message=video.error_message,
                camera_id=video.camera_id,
                location=video.location,
                uploaded_by=video.uploaded_by,
                created_at=video.created_at,
                updated_at=video.updated_at,
                processing_started_at=video.processing_started_at,
                processing_completed_at=video.processing_completed_at,
                segments=[
                    VideoSegmentResponse(
                        id=seg.id,
                        segment_index=seg.segment_index,
                        file_path=seg.file_path,
                        thumbnail_path=seg.thumbnail_path,
                        audio_path=seg.audio_path,
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        duration=seg.duration,
                        file_size=seg.file_size,
                        has_faces=seg.has_faces,
                        face_count=seg.face_count,
                        embedding_generated=seg.embedding_generated,
                    )
                    for seg in video.segments
                ],
                processing_logs=[
                    ProcessingLogResponse(
                        id=log.id,
                        step=log.step,
                        status=log.status,
                        message=log.message,
                        details=log.details,
                        started_at=log.started_at,
                        completed_at=log.completed_at,
                        duration_ms=log.duration_ms,
                    )
                    for log in video.processing_logs
                ],
            )
            for video in videos
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    service: VideoService = Depends(get_video_service),
):
    """Delete a video and all associated files."""
    deleted = await service.delete_video(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    return {"success": True, "message": f"Video {video_id} deleted successfully"}


@router.get("/agent/info", response_model=AgentInfoResponse)
async def get_agent_info(
    service: VideoService = Depends(get_video_service),
):
    """Get information about the Video Processing Agent."""
    info = service.get_agent_info()
    return AgentInfoResponse(**info)
