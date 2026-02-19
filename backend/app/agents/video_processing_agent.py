"""
Video Processing Agent using AWS Strands.

This agent handles the complete video processing pipeline:
1. Analyze video metadata (duration, resolution, fps, codec)
2. Split video into 15-second segments
3. Extract audio tracks
4. Generate thumbnails for each segment
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Any
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from app.config import get_settings, get_logger
from app.agents.tools.video_tools import (
    analyze_video,
    segment_video,
    extract_audio,
    generate_thumbnail,
)

logger = get_logger("video_processing_agent")
settings = get_settings()


VIDEO_PROCESSING_SYSTEM_PROMPT = """You are a Video Processing Agent for ChronoTrace, a forensic video intelligence platform.

Your role is to process surveillance videos through a systematic pipeline:

1. **Analyze Video**: First, analyze the video to extract metadata (duration, resolution, fps, codec, etc.)

2. **Segment Video**: Split the video into 15-second segments for easier processing and searching.

3. **Extract Audio**: Extract the audio track from the original video for audio-based analysis.

4. **Generate Thumbnails**: Create thumbnail images for each segment at the 3-second mark.

IMPORTANT GUIDELINES:
- Always start by analyzing the video to understand its properties
- Use the video_id provided for consistent naming across all outputs
- Report progress and any issues encountered during processing
- If a step fails, continue with other steps when possible and report the failure
- Provide a comprehensive summary at the end with all processing results

When processing is complete, provide a structured summary including:
- Video metadata (duration, resolution, fps)
- Number of segments created
- Audio extraction status
- Thumbnail generation status
- Any errors or warnings encountered
- Total processing time
"""


class VideoProcessingAgent:
    """
    Video Processing Agent that handles the complete video processing pipeline.
    
    Uses AWS Strands with AWS Bedrock Nova 2 Lite model for intelligent
    orchestration of video processing tasks.
    """
    
    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
    ):
        """
        Initialize the Video Processing Agent.
        
        Args:
            model_id: AWS Bedrock model ID (defaults to Nova 2 Lite)
            region_name: AWS region (defaults to settings)
        """
        self.model_id = model_id or settings.bedrock_model_id
        self.region_name = region_name or settings.aws_region
        
        logger.info(
            "Initializing Video Processing Agent",
            model_id=self.model_id,
            region=self.region_name
        )
        
        self.bedrock_model = BedrockModel(
            model_id=self.model_id,
            region_name=self.region_name,
            temperature=0.1,
            max_tokens=4096,
        )
        
        self.tools = [
            analyze_video,
            segment_video,
            extract_audio,
            generate_thumbnail,
        ]
        
        self.agent = Agent(
            model=self.bedrock_model,
            system_prompt=VIDEO_PROCESSING_SYSTEM_PROMPT,
            tools=self.tools,
        )
        
        logger.info("Video Processing Agent initialized successfully")
    
    def process_video(
        self,
        video_path: str,
        video_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        location: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process a video through the complete pipeline.
        
        Args:
            video_path: Path to the video file to process
            video_id: Unique identifier for the video (generated if not provided)
            camera_id: Optional camera identifier
            location: Optional location description
        
        Returns:
            Dictionary containing processing results and metadata
        """
        video_id = video_id or str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(
            "Starting video processing",
            video_id=video_id,
            video_path=video_path,
            camera_id=camera_id,
            location=location
        )
        
        output_dir = str(settings.processed_dir / video_id)
        thumbnails_dir = str(settings.thumbnails_dir / video_id)
        audio_dir = str(settings.audio_dir)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(thumbnails_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        
        prompt = f"""Process the video file at: {video_path}

Video ID: {video_id}
Camera ID: {camera_id or 'Not specified'}
Location: {location or 'Not specified'}

Please perform the following steps:

1. First, analyze the video using the analyze_video tool to get its metadata.

2. Then segment the video into 15-second segments using the segment_video tool:
   - Output directory: {output_dir}
   - Segment duration: {settings.segment_duration} seconds
   - Video ID: {video_id}

3. Extract the audio track using the extract_audio tool:
   - Output path: {os.path.join(audio_dir, f"{video_id}_audio.aac")}

4. For each segment created, generate a thumbnail using the generate_thumbnail tool:
   - Output directory for thumbnails: {thumbnails_dir}
   - Timestamp: {settings.thumbnail_timestamp} seconds into each segment
   - Dimensions: {settings.thumbnail_width}x{settings.thumbnail_height}

After completing all steps, provide a comprehensive summary of the processing results."""

        try:
            logger.info("Invoking Video Processing Agent", video_id=video_id)
            
            result = self.agent(prompt)
            
            elapsed_time = (datetime.utcnow() - start_time).total_seconds()
            
            processing_result = {
                "success": True,
                "video_id": video_id,
                "video_path": video_path,
                "camera_id": camera_id,
                "location": location,
                "output_dir": output_dir,
                "thumbnails_dir": thumbnails_dir,
                "audio_dir": audio_dir,
                "agent_response": str(result),
                "processing_time_seconds": round(elapsed_time, 2),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if hasattr(result, 'metrics'):
                metrics = result.metrics
                processing_result["metrics"] = {
                    "total_tokens": metrics.accumulated_usage.get("totalTokens", 0) if hasattr(metrics, 'accumulated_usage') else 0,
                    "input_tokens": metrics.accumulated_usage.get("inputTokens", 0) if hasattr(metrics, 'accumulated_usage') else 0,
                    "output_tokens": metrics.accumulated_usage.get("outputTokens", 0) if hasattr(metrics, 'accumulated_usage') else 0,
                }
            
            logger.info(
                "Video processing completed successfully",
                video_id=video_id,
                processing_time_seconds=elapsed_time
            )
            
            return processing_result
            
        except Exception as e:
            elapsed_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(
                "Video processing failed",
                video_id=video_id,
                error=error_msg,
                processing_time_seconds=elapsed_time
            )
            
            return {
                "success": False,
                "video_id": video_id,
                "video_path": video_path,
                "error": error_msg,
                "processing_time_seconds": round(elapsed_time, 2),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def analyze_only(self, video_path: str) -> dict[str, Any]:
        """
        Only analyze a video without full processing.
        
        Args:
            video_path: Path to the video file
        
        Returns:
            Video metadata dictionary
        """
        logger.info("Analyzing video only", video_path=video_path)
        return analyze_video(video_path)
    
    def get_agent_info(self) -> dict[str, Any]:
        """Get information about the agent configuration."""
        return {
            "name": "VideoProcessingAgent",
            "model_id": self.model_id,
            "region": self.region_name,
            "tools": [tool.__name__ for tool in self.tools],
            "segment_duration": settings.segment_duration,
            "thumbnail_dimensions": f"{settings.thumbnail_width}x{settings.thumbnail_height}",
        }


def create_video_processing_agent(
    model_id: Optional[str] = None,
    region_name: Optional[str] = None,
) -> VideoProcessingAgent:
    """
    Factory function to create a Video Processing Agent.
    
    Args:
        model_id: AWS Bedrock model ID (defaults to Nova 2 Lite)
        region_name: AWS region (defaults to settings)
    
    Returns:
        Configured VideoProcessingAgent instance
    """
    return VideoProcessingAgent(
        model_id=model_id,
        region_name=region_name,
    )
