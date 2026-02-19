"""
Video processing tools for the Video Processing Agent.
Uses FFmpeg and OpenCV for video manipulation.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime

from strands import tool

from app.config import get_settings, get_logger

logger = get_logger("video_tools")
settings = get_settings()


def _run_ffprobe(video_path: str) -> dict:
    """Run ffprobe to get video metadata."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


@tool
def analyze_video(video_path: str) -> dict[str, Any]:
    """
    Analyze a video file and extract its metadata including duration, resolution, 
    frame rate, codec, and bitrate.
    
    Args:
        video_path: The absolute path to the video file to analyze.
    
    Returns:
        A dictionary containing video metadata:
        - duration: Video duration in seconds
        - width: Video width in pixels
        - height: Video height in pixels
        - fps: Frames per second
        - codec: Video codec name
        - bitrate: Video bitrate in bits per second
        - file_size: File size in bytes
        - format_name: Container format name
    """
    logger.info("Analyzing video", video_path=video_path)
    start_time = datetime.utcnow()
    
    try:
        if not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_path}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
        
        probe_data = _run_ffprobe(video_path)
        
        video_stream = None
        audio_stream = None
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
        
        format_info = probe_data.get("format", {})
        
        duration = float(format_info.get("duration", 0))
        file_size = int(format_info.get("size", 0))
        bitrate = int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None
        format_name = format_info.get("format_name", "unknown")
        
        width = None
        height = None
        fps = None
        codec = None
        
        if video_stream:
            width = video_stream.get("width")
            height = video_stream.get("height")
            codec = video_stream.get("codec_name")
            
            fps_str = video_stream.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) > 0 else 0
            else:
                fps = float(fps_str)
        
        has_audio = audio_stream is not None
        
        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        result = {
            "success": True,
            "video_path": video_path,
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "fps": round(fps, 2) if fps else None,
            "codec": codec,
            "bitrate": bitrate,
            "file_size": file_size,
            "format_name": format_name,
            "has_audio": has_audio,
            "processing_time_ms": elapsed_ms,
        }
        
        logger.info(
            "Video analysis complete",
            video_path=video_path,
            duration=duration,
            resolution=f"{width}x{height}",
            fps=fps,
            processing_time_ms=elapsed_ms
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to analyze video: {str(e)}"
        logger.error(error_msg, video_path=video_path, error=str(e))
        return {"error": error_msg, "success": False}


@tool
def segment_video(
    video_path: str,
    output_dir: str,
    segment_duration: int = 15,
    video_id: str = ""
) -> dict[str, Any]:
    """
    Split a video into segments of specified duration using FFmpeg.
    
    Args:
        video_path: The absolute path to the video file to segment.
        output_dir: The directory where segments will be saved.
        segment_duration: Duration of each segment in seconds (default: 15).
        video_id: Unique identifier for the video (used in output filenames).
    
    Returns:
        A dictionary containing:
        - success: Whether the operation succeeded
        - segments: List of created segment file paths
        - segment_count: Number of segments created
        - segment_duration: Duration used for segmentation
    """
    logger.info(
        "Segmenting video",
        video_path=video_path,
        output_dir=output_dir,
        segment_duration=segment_duration
    )
    start_time = datetime.utcnow()
    
    try:
        if not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_path}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
        
        os.makedirs(output_dir, exist_ok=True)
        
        filename_prefix = video_id if video_id else Path(video_path).stem
        output_pattern = os.path.join(output_dir, f"{filename_prefix}_segment_%03d.mp4")
        
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(segment_duration),
            "-reset_timestamps", "1",
            "-y",
            output_pattern
        ]
        
        logger.debug("Running FFmpeg command", command=" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(
                "FFmpeg returned non-zero exit code",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None
            )
        
        segments = sorted(
            [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.startswith(filename_prefix) and f.endswith(".mp4") and "_segment_" in f
            ]
        )
        
        segment_info = []
        for idx, seg_path in enumerate(segments):
            seg_probe = _run_ffprobe(seg_path)
            seg_duration = float(seg_probe.get("format", {}).get("duration", 0))
            seg_size = int(seg_probe.get("format", {}).get("size", 0))
            
            segment_info.append({
                "index": idx,
                "path": seg_path,
                "start_time": idx * segment_duration,
                "end_time": idx * segment_duration + seg_duration,
                "duration": round(seg_duration, 2),
                "file_size": seg_size,
            })
        
        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        result = {
            "success": True,
            "video_path": video_path,
            "output_dir": output_dir,
            "segments": segment_info,
            "segment_count": len(segments),
            "segment_duration_setting": segment_duration,
            "processing_time_ms": elapsed_ms,
        }
        
        logger.info(
            "Video segmentation complete",
            video_path=video_path,
            segment_count=len(segments),
            processing_time_ms=elapsed_ms
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to segment video: {str(e)}"
        logger.error(error_msg, video_path=video_path, error=str(e))
        return {"error": error_msg, "success": False}


@tool
def extract_audio(
    video_path: str,
    output_path: str
) -> dict[str, Any]:
    """
    Extract the audio track from a video file.
    
    Args:
        video_path: The absolute path to the video file.
        output_path: The path where the audio file will be saved (should end with .aac or .mp3).
    
    Returns:
        A dictionary containing:
        - success: Whether the operation succeeded
        - audio_path: Path to the extracted audio file
        - duration: Duration of the audio in seconds
        - file_size: Size of the audio file in bytes
    """
    logger.info("Extracting audio", video_path=video_path, output_path=output_path)
    start_time = datetime.utcnow()
    
    try:
        if not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_path}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",
            "-acodec", "aac",
            "-y",
            output_path
        ]
        
        logger.debug("Running FFmpeg command", command=" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            if "does not contain any stream" in result.stderr or "no audio" in result.stderr.lower():
                logger.warning("Video has no audio track", video_path=video_path)
                return {
                    "success": True,
                    "audio_path": None,
                    "has_audio": False,
                    "message": "Video has no audio track"
                }
            logger.warning(
                "FFmpeg audio extraction warning",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None
            )
        
        if os.path.exists(output_path):
            audio_probe = _run_ffprobe(output_path)
            duration = float(audio_probe.get("format", {}).get("duration", 0))
            file_size = int(audio_probe.get("format", {}).get("size", 0))
            
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result = {
                "success": True,
                "audio_path": output_path,
                "has_audio": True,
                "duration": round(duration, 2),
                "file_size": file_size,
                "processing_time_ms": elapsed_ms,
            }
            
            logger.info(
                "Audio extraction complete",
                video_path=video_path,
                audio_path=output_path,
                duration=duration,
                processing_time_ms=elapsed_ms
            )
            
            return result
        else:
            return {
                "success": True,
                "audio_path": None,
                "has_audio": False,
                "message": "No audio track found in video"
            }
        
    except Exception as e:
        error_msg = f"Failed to extract audio: {str(e)}"
        logger.error(error_msg, video_path=video_path, error=str(e))
        return {"error": error_msg, "success": False}


@tool
def generate_thumbnail(
    video_path: str,
    output_path: str,
    timestamp: float = 3.0,
    width: int = 320,
    height: int = 180
) -> dict[str, Any]:
    """
    Generate a thumbnail image from a video at a specific timestamp.
    
    Args:
        video_path: The absolute path to the video file.
        output_path: The path where the thumbnail will be saved (should end with .jpg or .png).
        timestamp: The timestamp in seconds to capture the thumbnail from (default: 3.0).
        width: The width of the thumbnail in pixels (default: 320).
        height: The height of the thumbnail in pixels (default: 180).
    
    Returns:
        A dictionary containing:
        - success: Whether the operation succeeded
        - thumbnail_path: Path to the generated thumbnail
        - timestamp: The timestamp used for capture
        - dimensions: The dimensions of the thumbnail
    """
    logger.info(
        "Generating thumbnail",
        video_path=video_path,
        output_path=output_path,
        timestamp=timestamp
    )
    start_time = datetime.utcnow()
    
    try:
        if not os.path.exists(video_path):
            error_msg = f"Video file not found: {video_path}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}",
            "-y",
            output_path
        ]
        
        logger.debug("Running FFmpeg command", command=" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(
                "FFmpeg thumbnail generation warning",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None
            )
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result = {
                "success": True,
                "thumbnail_path": output_path,
                "timestamp": timestamp,
                "width": width,
                "height": height,
                "file_size": file_size,
                "processing_time_ms": elapsed_ms,
            }
            
            logger.info(
                "Thumbnail generation complete",
                video_path=video_path,
                thumbnail_path=output_path,
                processing_time_ms=elapsed_ms
            )
            
            return result
        else:
            error_msg = "Thumbnail file was not created"
            logger.error(error_msg, video_path=video_path)
            return {"error": error_msg, "success": False}
        
    except Exception as e:
        error_msg = f"Failed to generate thumbnail: {str(e)}"
        logger.error(error_msg, video_path=video_path, error=str(e))
        return {"error": error_msg, "success": False}
