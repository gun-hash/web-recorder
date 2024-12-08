CREATE TABLE IF NOT EXISTS recordings (
    request_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    video_url TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);