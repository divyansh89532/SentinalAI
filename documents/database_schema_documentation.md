# ChronoTrace - Complete Database Schema Documentation

---

## Table of Contents
1. [PostgreSQL Relational Database](#postgresql-relational-database)
2. [Qdrant Vector Database](#qdrant-vector-database)
3. [Database Relationships](#database-relationships)
4. [Indexes & Performance](#indexes--performance)
5. [Sample Data & Queries](#sample-data--queries)

---

## PostgreSQL Relational Database

### Overview
- **Database Name**: `chronotrace`
- **Engine**: PostgreSQL 15+
- **Character Set**: UTF8
- **Timezone**: UTC
- **Connection Pool**: 20 connections

---

### Table: `users`
**Purpose**: User authentication and authorization

```sql
CREATE TABLE users (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Authentication
    email               VARCHAR(255) UNIQUE NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,  -- bcrypt hash
    
    -- Profile
    full_name           VARCHAR(255),
    organization        VARCHAR(255),
    
    -- Authorization
    role                VARCHAR(50) NOT NULL DEFAULT 'viewer',
    -- Roles: 'viewer', 'analyst', 'admin', 'api_user'
    
    -- Account Status
    is_active           BOOLEAN DEFAULT true,
    is_verified         BOOLEAN DEFAULT false,
    email_verified_at   TIMESTAMP,
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    last_login_at       TIMESTAMP,
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb
    -- Example: {"preferences": {"theme": "dark"}, "notifications": {...}}
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Constraints
ALTER TABLE users ADD CONSTRAINT check_email_format 
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');
ALTER TABLE users ADD CONSTRAINT check_role_valid 
    CHECK (role IN ('viewer', 'analyst', 'admin', 'api_user'));
```

**Sample Data**:
```sql
INSERT INTO users (email, password_hash, full_name, role) VALUES
('admin@chronotrace.ai', '$2b$12$...', 'Admin User', 'admin'),
('analyst@pd.gov', '$2b$12$...', 'John Detective', 'analyst'),
('viewer@security.com', '$2b$12$...', 'Security Viewer', 'viewer');
```

---

### Table: `videos`
**Purpose**: Store metadata about uploaded videos

```sql
CREATE TABLE videos (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- File Information
    filename            VARCHAR(255) NOT NULL,
    original_path       TEXT NOT NULL,
    s3_key              TEXT,  -- AWS S3 object key
    s3_bucket           VARCHAR(255) DEFAULT 'chronotrace-videos',
    
    -- Video Properties
    duration_seconds    INTEGER,  -- Total duration in seconds
    resolution          VARCHAR(20),  -- e.g., "1920x1080"
    fps                 INTEGER,  -- Frames per second
    codec               VARCHAR(50),  -- e.g., "h264"
    file_size_bytes     BIGINT,
    
    -- Processing Status
    processing_status   VARCHAR(50) DEFAULT 'pending',
    -- Status values: 'pending', 'uploading', 'processing', 
    --                'completed', 'failed', 'archived'
    
    error_message       TEXT,  -- If processing failed
    
    -- Source Information
    camera_id           VARCHAR(100),
    location            VARCHAR(255),
    recorded_at         TIMESTAMP,  -- When video was recorded
    
    -- Ownership
    uploaded_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Timestamps
    uploaded_at         TIMESTAMP DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "device": "Camera-01",
    --   "weather": "sunny",
    --   "incident_id": "INC-2024-0001"
    -- }
    
    -- Soft Delete
    deleted_at          TIMESTAMP
);

-- Indexes
CREATE INDEX idx_videos_uploaded_by ON videos(uploaded_by);
CREATE INDEX idx_videos_status ON videos(processing_status);
CREATE INDEX idx_videos_camera_id ON videos(camera_id);
CREATE INDEX idx_videos_location ON videos(location);
CREATE INDEX idx_videos_recorded_at ON videos(recorded_at);
CREATE INDEX idx_videos_uploaded_at ON videos(uploaded_at);
CREATE INDEX idx_videos_deleted_at ON videos(deleted_at) WHERE deleted_at IS NULL;

-- GIN index for JSONB metadata search
CREATE INDEX idx_videos_metadata ON videos USING GIN(metadata);

-- Constraints
ALTER TABLE videos ADD CONSTRAINT check_status_valid 
    CHECK (processing_status IN ('pending', 'uploading', 'processing', 
                                  'completed', 'failed', 'archived'));
```

**Sample Data**:
```sql
INSERT INTO videos (
    filename, original_path, s3_key, duration_seconds, 
    resolution, fps, camera_id, location, uploaded_by
) VALUES
(
    'parking_lot_cam1_2024-02-09_14-30.mp4',
    '/uploads/parking_lot_cam1_2024-02-09_14-30.mp4',
    'raw-videos/a7f3b2c1-uuid.mp4',
    120,
    '1920x1080',
    30,
    'CAM-PARKING-01',
    'North Parking Lot',
    'uuid-of-analyst-user'
);
```

---

### Table: `video_segments`
**Purpose**: Store metadata about video segments (15-second chunks)

```sql
CREATE TABLE video_segments (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    video_id            UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    
    -- Segment Information
    segment_index       INTEGER NOT NULL,  -- 0-based index
    start_time          DECIMAL(10,3) NOT NULL,  -- Seconds with 3 decimal places
    end_time            DECIMAL(10,3) NOT NULL,
    duration            DECIMAL(10,3) GENERATED ALWAYS AS (end_time - start_time) STORED,
    
    -- File Paths
    segment_path        TEXT,  -- Path to segment file
    s3_key              TEXT,  -- S3 key for segment
    thumbnail_path      TEXT,  -- Path to thumbnail image
    thumbnail_s3_key    TEXT,
    audio_path          TEXT,  -- Extracted audio file
    
    -- Embedding Reference
    embedding_id        VARCHAR(255),  -- UUID in Qdrant vector database
    embedding_generated_at TIMESTAMP,
    
    -- Privacy & Detection
    has_faces           BOOLEAN DEFAULT false,
    face_count          INTEGER DEFAULT 0,
    has_vehicles        BOOLEAN DEFAULT false,
    vehicle_count       INTEGER DEFAULT 0,
    has_audio           BOOLEAN DEFAULT false,
    privacy_applied     BOOLEAN DEFAULT false,  -- Whether blur was applied
    
    -- Camera & Location
    camera_id           VARCHAR(100),
    location            VARCHAR(255),
    camera_angle        VARCHAR(50),  -- e.g., "front", "side", "overhead"
    
    -- Scene Analysis
    scene_type          VARCHAR(50),  -- e.g., "indoor", "outdoor", "parking"
    lighting_condition  VARCHAR(50),  -- e.g., "day", "night", "low-light"
    weather_condition   VARCHAR(50),  -- e.g., "clear", "rain", "snow"
    
    -- Motion & Activity
    motion_detected     BOOLEAN DEFAULT false,
    activity_level      VARCHAR(20),  -- "low", "medium", "high"
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "objects_detected": ["person", "car", "bicycle"],
    --   "dominant_colors": ["#FF5733", "#C70039"],
    --   "average_brightness": 0.65
    -- }
    
    -- Unique constraint
    CONSTRAINT unique_video_segment UNIQUE (video_id, segment_index)
);

-- Indexes
CREATE INDEX idx_segments_video_id ON video_segments(video_id);
CREATE INDEX idx_segments_camera_id ON video_segments(camera_id);
CREATE INDEX idx_segments_location ON video_segments(location);
CREATE INDEX idx_segments_embedding_id ON video_segments(embedding_id);
CREATE INDEX idx_segments_has_faces ON video_segments(has_faces);
CREATE INDEX idx_segments_start_time ON video_segments(start_time);
CREATE INDEX idx_segments_motion_detected ON video_segments(motion_detected);

-- Composite index for common queries
CREATE INDEX idx_segments_video_time ON video_segments(video_id, start_time);

-- GIN index for JSONB
CREATE INDEX idx_segments_metadata ON video_segments USING GIN(metadata);

-- Constraints
ALTER TABLE video_segments ADD CONSTRAINT check_time_order 
    CHECK (start_time < end_time);
ALTER TABLE video_segments ADD CONSTRAINT check_segment_index_positive 
    CHECK (segment_index >= 0);
```

**Sample Data**:
```sql
INSERT INTO video_segments (
    video_id, segment_index, start_time, end_time,
    segment_path, embedding_id, camera_id, has_faces, face_count
) VALUES
(
    'video-uuid-here',
    0,
    0.000,
    15.000,
    '/processed/segments/video_segment_000.mp4',
    'qdrant-vector-uuid-1',
    'CAM-PARKING-01',
    true,
    2
);
```

---

### Table: `searches`
**Purpose**: Log all search queries for analytics and debugging

```sql
CREATE TABLE searches (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Query Information
    query_text          TEXT NOT NULL,
    query_type          VARCHAR(50) DEFAULT 'text',  -- 'text', 'voice', 'image'
    
    -- Filters Applied
    filters             JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "camera_id": ["CAM-01", "CAM-02"],
    --   "start_time": "2024-02-09T00:00:00Z",
    --   "end_time": "2024-02-09T23:59:59Z",
    --   "min_confidence": 0.7
    -- }
    
    -- Results
    result_count        INTEGER,
    top_score           DECIMAL(5,4),  -- Highest similarity score
    
    -- Performance Metrics
    execution_time_ms   INTEGER,  -- Total query time
    nova_time_ms        INTEGER,  -- Time for embedding generation
    qdrant_time_ms      INTEGER,  -- Time for vector search
    db_time_ms          INTEGER,  -- Time for PostgreSQL queries
    
    -- Cache Status
    cache_hit           BOOLEAN DEFAULT false,
    
    -- Context
    session_id          VARCHAR(255),
    ip_address          INET,
    user_agent          TEXT,
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_searches_user_id ON searches(user_id);
CREATE INDEX idx_searches_created_at ON searches(created_at);
CREATE INDEX idx_searches_query_text ON searches USING GIN(to_tsvector('english', query_text));
CREATE INDEX idx_searches_cache_hit ON searches(cache_hit);

-- GIN index for filters
CREATE INDEX idx_searches_filters ON searches USING GIN(filters);

-- Performance analysis index
CREATE INDEX idx_searches_performance ON searches(execution_time_ms, created_at);
```

**Sample Data**:
```sql
INSERT INTO searches (
    user_id, query_text, result_count, execution_time_ms, 
    nova_time_ms, qdrant_time_ms, cache_hit
) VALUES
(
    'user-uuid',
    'person in red jacket',
    8,
    120,
    50,
    45,
    false
);
```

---

### Table: `anomalies`
**Purpose**: Store detected anomalies from video analysis

```sql
CREATE TABLE anomalies (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    segment_id          UUID NOT NULL REFERENCES video_segments(id) ON DELETE CASCADE,
    video_id            UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    
    -- Anomaly Type
    anomaly_type        VARCHAR(50) NOT NULL,
    -- Types: 'loitering', 'crowd_formation', 'object_abandonment',
    --        'unusual_movement', 'after_hours_access', 'fall_detection',
    --        'vehicle_stopped', 'perimeter_breach'
    
    -- Detection Details
    confidence          DECIMAL(5,4) NOT NULL,  -- 0.0000 to 1.0000
    severity            VARCHAR(20) DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    
    -- Description
    title               VARCHAR(255),
    description         TEXT,
    
    -- Location & Time
    camera_id           VARCHAR(100),
    location            VARCHAR(255),
    detected_at         TIMESTAMP NOT NULL,
    
    -- Status
    status              VARCHAR(50) DEFAULT 'new',
    -- Status: 'new', 'acknowledged', 'investigating', 'resolved', 'false_positive'
    
    resolved_at         TIMESTAMP,
    resolved_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    resolution_notes    TEXT,
    
    -- Alert Configuration
    alert_sent          BOOLEAN DEFAULT false,
    alert_sent_at       TIMESTAMP,
    alert_recipients    TEXT[],  -- Array of email addresses
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "duration_seconds": 900,  // For loitering
    --   "person_count": 15,       // For crowd formation
    --   "object_type": "bag",     // For abandonment
    --   "bounding_box": {"x": 100, "y": 200, "w": 50, "h": 80}
    -- }
);

-- Indexes
CREATE INDEX idx_anomalies_segment_id ON anomalies(segment_id);
CREATE INDEX idx_anomalies_video_id ON anomalies(video_id);
CREATE INDEX idx_anomalies_type ON anomalies(anomaly_type);
CREATE INDEX idx_anomalies_status ON anomalies(status);
CREATE INDEX idx_anomalies_severity ON anomalies(severity);
CREATE INDEX idx_anomalies_detected_at ON anomalies(detected_at);
CREATE INDEX idx_anomalies_camera_id ON anomalies(camera_id);
CREATE INDEX idx_anomalies_alert_sent ON anomalies(alert_sent) WHERE alert_sent = false;

-- Composite index for dashboard queries
CREATE INDEX idx_anomalies_status_detected ON anomalies(status, detected_at DESC);

-- GIN index for metadata
CREATE INDEX idx_anomalies_metadata ON anomalies USING GIN(metadata);

-- Constraints
ALTER TABLE anomalies ADD CONSTRAINT check_anomaly_type_valid 
    CHECK (anomaly_type IN ('loitering', 'crowd_formation', 'object_abandonment',
                            'unusual_movement', 'after_hours_access', 'fall_detection',
                            'vehicle_stopped', 'perimeter_breach'));
ALTER TABLE anomalies ADD CONSTRAINT check_severity_valid 
    CHECK (severity IN ('low', 'medium', 'high', 'critical'));
ALTER TABLE anomalies ADD CONSTRAINT check_confidence_range 
    CHECK (confidence >= 0.0 AND confidence <= 1.0);
```

**Sample Data**:
```sql
INSERT INTO anomalies (
    segment_id, video_id, anomaly_type, confidence, 
    severity, title, description, camera_id, detected_at
) VALUES
(
    'segment-uuid',
    'video-uuid',
    'loitering',
    0.8734,
    'medium',
    'Extended Loitering Detected',
    'Individual remained in north entrance area for 22 minutes',
    'CAM-ENTRANCE-NORTH',
    '2024-02-09 14:35:22'
);
```

---

### Table: `audit_log`
**Purpose**: Track all sensitive actions for compliance and security

```sql
CREATE TABLE audit_log (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Actor Information
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    username            VARCHAR(255),  -- Cached for deleted users
    
    -- Action Details
    action              VARCHAR(100) NOT NULL,
    -- Actions: 'user_login', 'user_logout', 'video_upload', 'search_query',
    --          'pii_reveal', 'anomaly_resolved', 'export_data', 'api_call'
    
    -- Resource Information
    resource_type       VARCHAR(50),  -- 'video', 'segment', 'user', 'anomaly'
    resource_id         UUID,
    
    -- Context
    justification       TEXT,  -- Required for PII reveal
    
    -- Request Details
    ip_address          INET,
    user_agent          TEXT,
    request_id          VARCHAR(255),
    
    -- Result
    success             BOOLEAN DEFAULT true,
    error_message       TEXT,
    
    -- Timestamp
    created_at          TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "case_id": "CASE-2024-0001",
    --   "before": {...},
    --   "after": {...}
    -- }
);

-- Indexes
CREATE INDEX idx_audit_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_ip_address ON audit_log(ip_address);

-- Composite index for compliance queries
CREATE INDEX idx_audit_user_action_time ON audit_log(user_id, action, created_at DESC);

-- GIN index for metadata
CREATE INDEX idx_audit_metadata ON audit_log USING GIN(metadata);

-- Partitioning by month for performance (optional)
-- CREATE TABLE audit_log_2024_02 PARTITION OF audit_log
--     FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

**Sample Data**:
```sql
INSERT INTO audit_log (
    user_id, username, action, resource_type, 
    resource_id, justification, ip_address
) VALUES
(
    'user-uuid',
    'detective@pd.gov',
    'pii_reveal',
    'segment',
    'segment-uuid',
    'Active investigation: CASE-2024-0001 - Robbery suspect identification',
    '192.168.1.100'
);
```

---

### Table: `api_keys`
**Purpose**: Manage API keys for external integrations

```sql
CREATE TABLE api_keys (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Key Information
    key_hash            VARCHAR(255) NOT NULL UNIQUE,  -- SHA256 hash of actual key
    key_prefix          VARCHAR(10) NOT NULL,  -- First 8 chars for identification
    name                VARCHAR(100),  -- User-friendly name
    description         TEXT,
    
    -- Permissions
    scopes              TEXT[] DEFAULT ARRAY['read:videos'],  -- Array of scopes
    -- Scopes: 'read:videos', 'write:videos', 'read:searches', 
    --         'write:searches', 'admin'
    
    -- Rate Limiting
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day  INTEGER DEFAULT 10000,
    
    -- Usage Tracking
    last_used_at        TIMESTAMP,
    request_count       INTEGER DEFAULT 0,
    
    -- Status
    is_active           BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    expires_at          TIMESTAMP,  -- Optional expiration
    revoked_at          TIMESTAMP,
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) 
    WHERE expires_at IS NOT NULL;

-- Constraints
ALTER TABLE api_keys ADD CONSTRAINT check_rate_limits_positive 
    CHECK (rate_limit_per_hour > 0 AND rate_limit_per_day > 0);
```

**Sample Data**:
```sql
INSERT INTO api_keys (
    user_id, key_hash, key_prefix, name, scopes, rate_limit_per_hour
) VALUES
(
    'user-uuid',
    'sha256-hash-of-actual-key',
    'ct_live_Ab',
    'Production API Key - VMS Integration',
    ARRAY['read:videos', 'write:searches'],
    5000
);
```

---

### Table: `exports`
**Purpose**: Track video/report export requests

```sql
CREATE TABLE exports (
    -- Primary Key
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Export Type
    export_type         VARCHAR(50) NOT NULL,
    -- Types: 'video_clip', 'pdf_report', 'csv_data', 'json_data'
    
    -- Content
    segment_ids         UUID[],  -- Array of segment IDs to export
    query_id            UUID,  -- Reference to original search
    
    -- File Information
    file_path           TEXT,
    s3_key              TEXT,
    file_size_bytes     BIGINT,
    format              VARCHAR(20),  -- 'mp4', 'pdf', 'csv', 'json'
    
    -- Processing Status
    status              VARCHAR(50) DEFAULT 'pending',
    -- Status: 'pending', 'processing', 'completed', 'failed', 'expired'
    
    -- Timestamps
    created_at          TIMESTAMP DEFAULT NOW(),
    completed_at        TIMESTAMP,
    expires_at          TIMESTAMP,  -- Download link expiration
    downloaded_at       TIMESTAMP,
    
    -- Metadata
    metadata            JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "include_metadata": true,
    --   "include_thumbnails": true,
    --   "watermark": "EVIDENCE - CASE-2024-0001"
    -- }
);

-- Indexes
CREATE INDEX idx_exports_user_id ON exports(user_id);
CREATE INDEX idx_exports_status ON exports(status);
CREATE INDEX idx_exports_created_at ON exports(created_at DESC);
CREATE INDEX idx_exports_expires_at ON exports(expires_at) 
    WHERE status = 'completed';
```

---

## Qdrant Vector Database

### Overview
- **Collection Name**: `video_segments`
- **Vector Dimension**: 1024 (float32)
- **Distance Metric**: Cosine Similarity
- **Index Type**: HNSW (Hierarchical Navigable Small World)
- **Storage**: On-disk with in-memory index

---

### Collection Configuration

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

client = QdrantClient(host="localhost", port=6333)

# Create collection
client.create_collection(
    collection_name="video_segments",
    vectors_config=VectorParams(
        size=1024,
        distance=Distance.COSINE,
        on_disk=False  # Keep vectors in RAM for speed
    ),
    # HNSW index parameters
    hnsw_config={
        "m": 16,  # Number of edges per node
        "ef_construct": 100,  # Size of candidate list during index construction
        "full_scan_threshold": 10000  # Use full scan for small datasets
    },
    # Optimize for search speed vs accuracy
    optimizers_config={
        "indexing_threshold": 20000,  # Start indexing after 20K vectors
    }
)
```

---

### Vector Point Structure

Each point in Qdrant contains:
1. **ID**: Unique identifier (UUID string)
2. **Vector**: 1024-dimensional float array (embedding from Nova)
3. **Payload**: JSON metadata about the segment

```python
# Example point structure
{
    "id": "qdrant-vector-uuid-12345",
    "vector": [0.123, -0.456, 0.789, ...],  # 1024 floats
    "payload": {
        # Core identifiers
        "segment_id": "segment-uuid-from-postgresql",
        "video_id": "video-uuid-from-postgresql",
        
        # Temporal information
        "start_time": 45.000,
        "end_time": 60.000,
        "duration": 15.000,
        "timestamp": "2024-02-09T14:30:45Z",
        
        # Location & Camera
        "camera_id": "CAM-PARKING-01",
        "location": "North Parking Lot",
        "camera_angle": "overhead",
        
        # Scene characteristics
        "scene_type": "outdoor",
        "lighting_condition": "day",
        "weather_condition": "clear",
        
        # Content flags
        "has_faces": true,
        "face_count": 2,
        "has_vehicles": true,
        "vehicle_count": 1,
        "has_audio": true,
        "privacy_applied": true,
        
        # Motion & Activity
        "motion_detected": true,
        "activity_level": "medium",
        
        # File references
        "thumbnail_url": "https://cdn.chronotrace.ai/thumbnails/abc123.jpg",
        "segment_url": "https://cdn.chronotrace.ai/segments/xyz789.mp4",
        
        # Detected objects (from CV pipeline)
        "objects_detected": ["person", "car", "bicycle"],
        
        # Embeddings metadata
        "embedding_model": "amazon.nova-embed-multimodal-v1",
        "embedding_version": "1.0",
        "embedding_generated_at": "2024-02-09T14:35:00Z",
        
        # Additional metadata
        "dominant_colors": ["#FF5733", "#C70039", "#900C3F"],
        "average_brightness": 0.65,
        "audio_level_db": -12.5
    }
}
```

---

### Payload Schema & Indexes

```python
# Create payload indexes for efficient filtering
client.create_payload_index(
    collection_name="video_segments",
    field_name="camera_id",
    field_schema=PayloadSchemaType.KEYWORD
)

client.create_payload_index(
    collection_name="video_segments",
    field_name="start_time",
    field_schema=PayloadSchemaType.FLOAT
)

client.create_payload_index(
    collection_name="video_segments",
    field_name="has_faces",
    field_schema=PayloadSchemaType.BOOL
)

client.create_payload_index(
    collection_name="video_segments",
    field_name="location",
    field_schema=PayloadSchemaType.KEYWORD
)

client.create_payload_index(
    collection_name="video_segments",
    field_name="timestamp",
    field_schema=PayloadSchemaType.DATETIME
)

client.create_payload_index(
    collection_name="video_segments",
    field_name="motion_detected",
    field_schema=PayloadSchemaType.BOOL
)
```

---

### Search Operations

#### 1. Basic Similarity Search
```python
# Search for similar segments
results = client.search(
    collection_name="video_segments",
    query_vector=[0.123, -0.456, ...],  # 1024-dim query vector from Nova
    limit=10,
    score_threshold=0.7  # Only return results with score > 0.7
)

# Results structure:
# [
#     ScoredPoint(
#         id="qdrant-uuid-1",
#         score=0.8734,
#         payload={...}
#     ),
#     ...
# ]
```

#### 2. Filtered Search
```python
from qdrant_client.models import Filter, FieldCondition, Range

# Search with filters
results = client.search(
    collection_name="video_segments",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            # Camera filter
            FieldCondition(
                key="camera_id",
                match={"value": "CAM-PARKING-01"}
            ),
            # Time range filter
            FieldCondition(
                key="start_time",
                range=Range(
                    gte=0.0,
                    lte=300.0  # First 5 minutes
                )
            ),
            # Has faces filter
            FieldCondition(
                key="has_faces",
                match={"value": True}
            )
        ]
    ),
    limit=20
)
```

#### 3. Multi-Camera Search
```python
from qdrant_client.models import Filter, FieldCondition

# Search across multiple cameras
results = client.search(
    collection_name="video_segments",
    query_vector=query_embedding,
    query_filter=Filter(
        should=[  # OR condition
            FieldCondition(
                key="camera_id",
                match={"any": ["CAM-01", "CAM-02", "CAM-03"]}
            )
        ]
    ),
    limit=50
)
```

#### 4. Batch Search
```python
# Search multiple queries at once
search_queries = [
    {
        "query_vector": query_vector_1,
        "limit": 10,
        "filter": filter_1
    },
    {
        "query_vector": query_vector_2,
        "limit": 10,
        "filter": filter_2
    }
]

results = client.search_batch(
    collection_name="video_segments",
    requests=search_queries
)
```

---

### Performance Characteristics

```yaml
Dataset Size: 1 Million vectors (1024-dim each)

Storage:
  - RAM usage: ~4 GB (vectors only)
  - Disk usage: ~10 GB (with payload)

Search Performance:
  - Cold search (first query): ~100-150ms
  - Warm search (cached): ~30-50ms
  - Batch search (10 queries): ~200ms total
  
Throughput:
  - Concurrent searches: 100-200 queries/sec
  - Insert rate: 5,000-10,000 vectors/sec
  
Scalability:
  - Horizontal scaling: Sharding support
  - Vertical scaling: Multi-core indexing
```

---

## Database Relationships

### Entity Relationship Diagram (ERD)

```
┌─────────────┐
│    users    │
└──────┬──────┘
       │
       │ 1:N (uploaded_by)
       ▼
┌─────────────┐
│   videos    │◄──────────┐
└──────┬──────┘           │
       │                  │
       │ 1:N              │ N:1 (video_id)
       ▼                  │
┌──────────────────┐      │
│ video_segments   │──────┘
└──────┬───────────┘
       │
       │ 1:N (segment_id)
       ▼
┌─────────────┐
│  anomalies  │
└─────────────┘

┌─────────────┐
│    users    │
└──────┬──────┘
       │
       │ 1:N (user_id)
       ├──────────────┐
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────┐
│  searches   │  │audit_log │
└─────────────┘  └──────────┘

┌─────────────┐
│    users    │
└──────┬──────┘
       │
       │ 1:N
       ▼
┌─────────────┐
│  api_keys   │
└─────────────┘

PostgreSQL Tables ◄─────────► Qdrant Collection
                 (via embedding_id)
                 
video_segments.embedding_id → video_segments[point.id]
```

---

### Cross-Database Queries

#### Example: Complete Search Flow

```python
# Step 1: Generate query embedding (AWS Nova)
query_embedding = nova_client.embed_text_query("person in red jacket")

# Step 2: Search Qdrant for similar vectors
qdrant_results = qdrant_client.search(
    collection_name="video_segments",
    query_vector=query_embedding,
    limit=20
)

# Step 3: Extract segment IDs
segment_ids = [result.payload['segment_id'] for result in qdrant_results]

# Step 4: Fetch full metadata from PostgreSQL
from sqlalchemy import select
query = select(VideoSegment, Video).join(Video).where(
    VideoSegment.id.in_(segment_ids)
)
segments = session.execute(query).all()

# Step 5: Combine results
final_results = []
for qdrant_result in qdrant_results:
    segment_id = qdrant_result.payload['segment_id']
    # Find matching PostgreSQL record
    pg_segment = next((s for s in segments if str(s.id) == segment_id), None)
    
    if pg_segment:
        final_results.append({
            'segment_id': segment_id,
            'similarity_score': qdrant_result.score,
            'start_time': pg_segment.start_time,
            'end_time': pg_segment.end_time,
            'video_filename': pg_segment.video.filename,
            'camera_id': pg_segment.camera_id,
            'thumbnail_url': pg_segment.thumbnail_path,
            'has_faces': pg_segment.has_faces,
            'privacy_applied': pg_segment.privacy_applied
        })

return final_results
```

---

## Indexes & Performance

### PostgreSQL Index Strategy

```sql
-- B-tree indexes for exact matches and ranges
CREATE INDEX idx_videos_uploaded_at_btree ON videos(uploaded_at);
CREATE INDEX idx_segments_start_time_btree ON video_segments(start_time);

-- Composite indexes for common query patterns
CREATE INDEX idx_segments_video_camera ON video_segments(video_id, camera_id);
CREATE INDEX idx_anomalies_status_severity ON anomalies(status, severity, detected_at DESC);

-- Partial indexes for filtered queries
CREATE INDEX idx_videos_active ON videos(id) 
    WHERE deleted_at IS NULL AND processing_status = 'completed';
CREATE INDEX idx_anomalies_unresolved ON anomalies(id, detected_at DESC) 
    WHERE status IN ('new', 'acknowledged');

-- GIN indexes for full-text search
CREATE INDEX idx_videos_metadata_gin ON videos USING GIN(metadata);
CREATE INDEX idx_segments_metadata_gin ON video_segments USING GIN(metadata);

-- GIN indexes for array operations
CREATE INDEX idx_exports_segments ON exports USING GIN(segment_ids);
```

### Query Performance Examples

```sql
-- Fast query: Uses idx_videos_uploaded_at_btree
EXPLAIN ANALYZE
SELECT * FROM videos 
WHERE uploaded_at >= '2024-02-01' 
  AND uploaded_at < '2024-03-01'
ORDER BY uploaded_at DESC
LIMIT 100;

-- Result: Index Scan, ~5ms for 100K rows

-- Fast query: Uses idx_segments_video_camera composite
EXPLAIN ANALYZE
SELECT * FROM video_segments
WHERE video_id = 'uuid-here'
  AND camera_id = 'CAM-01'
ORDER BY start_time;

-- Result: Index Scan, ~2ms

-- Fast query: Uses idx_anomalies_status_severity composite
EXPLAIN ANALYZE
SELECT * FROM anomalies
WHERE status = 'new'
  AND severity = 'high'
ORDER BY detected_at DESC
LIMIT 50;

-- Result: Index Scan, ~3ms
```

---

## Sample Data & Queries

### Insert Sample Dataset

```sql
-- Insert test user
INSERT INTO users (email, password_hash, full_name, role)
VALUES ('analyst@chronotrace.ai', '$2b$12$...', 'Test Analyst', 'analyst')
RETURNING id;
-- Returns: e.g., '123e4567-e89b-12d3-a456-426614174000'

-- Insert test video
INSERT INTO videos (
    filename, original_path, s3_key, duration_seconds,
    resolution, fps, camera_id, location, uploaded_by
)
VALUES (
    'mall_cam1_2024-02-09.mp4',
    '/uploads/mall_cam1.mp4',
    'raw-videos/mall_cam1.mp4',
    300,
    '1920x1080',
    30,
    'CAM-MALL-ENTRANCE',
    'Main Entrance',
    '123e4567-e89b-12d3-a456-426614174000'
)
RETURNING id;
-- Returns: e.g., 'video-uuid-123'

-- Insert video segments
INSERT INTO video_segments (
    video_id, segment_index, start_time, end_time,
    segment_path, embedding_id, camera_id, has_faces
)
SELECT 
    'video-uuid-123',
    generate_series(0, 19) as segment_index,
    generate_series(0, 19) * 15.0 as start_time,
    (generate_series(0, 19) + 1) * 15.0 as end_time,
    '/processed/segment_' || lpad(generate_series(0, 19)::text, 3, '0') || '.mp4',
    'qdrant-' || gen_random_uuid(),
    'CAM-MALL-ENTRANCE',
    random() > 0.5
;
-- Creates 20 segments (0-300 seconds)
```

### Common Queries

#### 1. Find all videos from specific camera in date range
```sql
SELECT 
    v.id,
    v.filename,
    v.duration_seconds,
    v.uploaded_at,
    COUNT(vs.id) as segment_count,
    COUNT(CASE WHEN vs.has_faces THEN 1 END) as segments_with_faces
FROM videos v
LEFT JOIN video_segments vs ON v.id = vs.video_id
WHERE v.camera_id = 'CAM-MALL-ENTRANCE'
  AND v.uploaded_at >= '2024-02-01'
  AND v.uploaded_at < '2024-03-01'
  AND v.deleted_at IS NULL
GROUP BY v.id
ORDER BY v.uploaded_at DESC;
```

#### 2. Get segments with anomalies
```sql
SELECT 
    vs.id as segment_id,
    vs.start_time,
    vs.end_time,
    v.filename,
    a.anomaly_type,
    a.confidence,
    a.severity,
    a.description
FROM video_segments vs
JOIN videos v ON vs.video_id = v.id
JOIN anomalies a ON vs.id = a.segment_id
WHERE a.status = 'new'
  AND a.severity IN ('high', 'critical')
ORDER BY a.detected_at DESC
LIMIT 50;
```

#### 3. User search analytics
```sql
SELECT 
    u.email,
    COUNT(s.id) as total_searches,
    AVG(s.execution_time_ms) as avg_response_time_ms,
    SUM(CASE WHEN s.cache_hit THEN 1 ELSE 0 END) as cache_hits,
    ROUND(100.0 * SUM(CASE WHEN s.cache_hit THEN 1 ELSE 0 END) / COUNT(*), 2) as cache_hit_rate
FROM searches s
JOIN users u ON s.user_id = u.id
WHERE s.created_at >= NOW() - INTERVAL '7 days'
GROUP BY u.id, u.email
ORDER BY total_searches DESC
LIMIT 10;
```

#### 4. Audit trail for PII access
```sql
SELECT 
    al.created_at,
    u.email,
    al.action,
    vs.camera_id,
    vs.start_time,
    al.justification,
    al.ip_address
FROM audit_log al
JOIN users u ON al.user_id = u.id
LEFT JOIN video_segments vs ON al.resource_id = vs.id
WHERE al.action = 'pii_reveal'
  AND al.created_at >= NOW() - INTERVAL '30 days'
ORDER BY al.created_at DESC;
```

---

## Database Maintenance

### Regular Tasks

```sql
-- Vacuum and analyze (weekly)
VACUUM ANALYZE videos;
VACUUM ANALYZE video_segments;
VACUUM ANALYZE searches;

-- Reindex (monthly)
REINDEX TABLE videos;
REINDEX TABLE video_segments;

-- Clean old searches (daily)
DELETE FROM searches 
WHERE created_at < NOW() - INTERVAL '90 days';

-- Archive old audit logs (monthly)
INSERT INTO audit_log_archive
SELECT * FROM audit_log
WHERE created_at < NOW() - INTERVAL '1 year';

DELETE FROM audit_log
WHERE created_at < NOW() - INTERVAL '1 year';
```

### Backup Strategy

```bash
# Daily backup
pg_dump -Fc chronotrace > chronotrace_$(date +%Y%m%d).dump

# Qdrant snapshot
curl -X POST 'http://localhost:6333/collections/video_segments/snapshots'

# Backup retention: 7 daily, 4 weekly, 12 monthly
```

---

## Summary

### Database Sizes (Estimated)

**PostgreSQL:**
- videos: ~1 KB/row × 10,000 videos = 10 MB
- video_segments: ~2 KB/row × 500,000 segments = 1 GB
- searches: ~0.5 KB/row × 1M searches = 500 MB
- anomalies: ~1 KB/row × 50,000 anomalies = 50 MB
- audit_log: ~1 KB/row × 5M entries = 5 GB
- **Total: ~6.5 GB**

**Qdrant:**
- 500,000 vectors × 1024 dimensions × 4 bytes = 2 GB (vectors)
- 500,000 payloads × ~1 KB each = 500 MB (metadata)
- **Total: ~2.5 GB**

**Grand Total: ~9 GB** for production dataset

This schema supports:
- ✅ Scalability to millions of videos
- ✅ Sub-second search performance
- ✅ Complete audit trail
- ✅ Privacy compliance
- ✅ Multi-tenant isolation
- ✅ Real-time analytics
