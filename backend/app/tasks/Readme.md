# Background Tasks

This directory will contain background task definitions for async processing.

## Planned Tasks

1. **Video Processing Task** - Async video processing using Celery/Redis
2. **Embedding Generation Task** - Generate embeddings for video segments
3. **Anomaly Detection Task** - Run anomaly detection on processed videos
4. **Cleanup Task** - Clean up temporary files and old data

## Current Implementation

For the MVP, video processing runs synchronously in the API request.
Background task support will be added in future iterations.
