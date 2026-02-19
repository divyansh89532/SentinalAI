# ChronoTrace Backend

Forensic Video Intelligence Platform - Backend API

## Overview

The ChronoTrace backend is built with FastAPI and uses AWS Strands Agents SDK for AI-powered video processing. It provides APIs for video upload, processing, and retrieval.

## Tech Stack

- **Framework:** FastAPI (Python 3.10+)
- **AI Framework:** AWS Strands Agents SDK
- **LLM:** AWS Bedrock Nova 2 Lite
- **Database:** SQLite with SQLAlchemy (async)
- **Video Processing:** FFmpeg + OpenCV
- **Vector Database:** Qdrant (for future embedding storage)

## Project Structure

```
backend/
├── app/
│   ├── agents/           # AI Agents (Strands SDK)
│   │   ├── tools/        # Agent tools
│   │   └── video_processing_agent.py
│   ├── models/           # Database models
│   ├── router/           # API routes
│   ├── schema/           # Pydantic schemas
│   ├── services/         # Business logic
│   ├── tasks/            # Background tasks (future)
│   ├── config.py         # Configuration
│   └── main.py           # FastAPI application
├── data/                 # Data storage
│   ├── videos/           # Raw uploaded videos
│   ├── processed/        # Processed segments
│   ├── thumbnails/       # Generated thumbnails
│   └── audio/            # Extracted audio
├── requirements.txt
├── .env.example
└── README.md
```

## Quick Start

### Prerequisites

1. Python 3.10+
2. FFmpeg installed and in PATH
3. AWS credentials configured
4. AWS Bedrock access enabled for Nova models

### Installation

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run the server
python -m app.main
```

### Running with Uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health & Info

- `GET /` - API information
- `GET /health` - Health check
- `GET /api/v1/config` - Current configuration

### Videos

- `POST /api/v1/videos/upload` - Upload a video
- `POST /api/v1/videos/{video_id}/process` - Process a video
- `GET /api/v1/videos/{video_id}` - Get video details
- `GET /api/v1/videos/` - List all videos
- `DELETE /api/v1/videos/{video_id}` - Delete a video

### Agent Info

- `GET /api/v1/videos/agent/info` - Get Video Processing Agent info

## API Documentation

Once running, access the interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Video Processing Pipeline

When you process a video, the Video Processing Agent performs:

1. **Analysis** - Extract metadata (duration, resolution, fps, codec)
2. **Segmentation** - Split into 15-second segments
3. **Audio Extraction** - Separate audio track
4. **Thumbnail Generation** - Create preview images

## Example Usage

### Upload a Video

```bash
curl -X POST "http://localhost:8000/api/v1/videos/upload" \
  -F "file=@parking_lot.mp4" \
  -F "camera_id=CAM-01" \
  -F "location=North Parking Lot"
```

### Process the Video

```bash
curl -X POST "http://localhost:8000/api/v1/videos/{video_id}/process"
```

### Get Video Details

```bash
curl "http://localhost:8000/api/v1/videos/{video_id}"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `BEDROCK_MODEL_ID` | Nova model ID | `us.amazon.nova-lite-v1:0` |
| `DATABASE_URL` | Database connection | `sqlite+aiosqlite:///./data/chronotrace.db` |
| `SEGMENT_DURATION` | Segment length (seconds) | `15` |
| `LOG_LEVEL` | Logging level | `INFO` |

## AI Agents

### Video Processing Agent 🎬

The Video Processing Agent uses AWS Strands SDK with Nova 2 Lite to orchestrate video processing tasks. It intelligently decides which tools to use based on the video content and processing requirements.

**Tools:**
- `analyze_video` - FFprobe-based metadata extraction
- `segment_video` - FFmpeg segmentation
- `extract_audio` - Audio track extraction
- `generate_thumbnail` - Frame capture for thumbnails

### Coming Soon

- **Privacy Guardian Agent** 🔒 - Face/license plate blurring
- **Embedding Generator Agent** 🧠 - Vector embeddings for search
- **Anomaly Detection Agent** ⚠️ - Suspicious activity detection

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
isort app/
```

### Type Checking

```bash
mypy app/
```

## Logging

The application uses structured logging with `structlog`. Logs include:

- Request/response timing
- Processing step details
- Error tracking with context
- Agent tool invocations

Set `LOG_FORMAT=json` for production or `LOG_FORMAT=console` for development.

## License

MIT License - See LICENSE file for details.
