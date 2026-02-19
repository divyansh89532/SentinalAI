# AI Agents

This directory contains the AI agents for ChronoTrace, built using AWS Strands Agents SDK.

## Implemented Agents

### 1. Video Processing Agent 🎬

**File:** `video_processing_agent.py`

**Purpose:** Handles the complete video processing pipeline.

**Capabilities:**
- Analyze video metadata (duration, resolution, fps, codec)
- Split videos into 15-second segments
- Extract audio tracks
- Generate thumbnails for each segment

**Technology:**
- AWS Strands Agents SDK
- AWS Bedrock Nova 2 Lite (LLM)
- FFmpeg for video processing
- OpenCV for frame extraction

**Tools:**
- `analyze_video` - Extract video metadata using FFprobe
- `segment_video` - Split video into segments using FFmpeg
- `extract_audio` - Extract audio track from video
- `generate_thumbnail` - Create thumbnail images from video frames

## Planned Agents

### 2. Privacy Guardian Agent 🔒 (Coming Soon)

**Purpose:** Automatically detect and blur faces/license plates.

**Planned Capabilities:**
- Face detection using MediaPipe
- License plate detection
- Gaussian blur application
- PII location logging

### 3. Embedding Generator Agent 🧠 (Coming Soon)

**Purpose:** Convert video segments into searchable vectors.

**Planned Capabilities:**
- AWS Nova Multimodal Embeddings integration
- Vector storage in Qdrant
- Caching with Redis

### 4. Anomaly Detection Agent ⚠️ (Coming Soon)

**Purpose:** Automatically flag suspicious activities.

**Planned Capabilities:**
- Loitering detection
- Crowd formation detection
- Object abandonment detection
- After-hours access detection
- Unusual movement patterns

## Usage

```python
from app.agents import VideoProcessingAgent

# Create agent
agent = VideoProcessingAgent()

# Process a video
result = agent.process_video(
    video_path="/path/to/video.mp4",
    video_id="unique-id",
    camera_id="CAM-01",
    location="Parking Lot"
)

# Check result
if result["success"]:
    print(f"Created {result['segment_count']} segments")
```

## Configuration

Agents are configured via environment variables:

- `BEDROCK_MODEL_ID` - AWS Bedrock model ID (default: `us.amazon.nova-lite-v1:0`)
- `AWS_REGION` - AWS region (default: `us-east-1`)
- `SEGMENT_DURATION` - Video segment duration in seconds (default: 15)
