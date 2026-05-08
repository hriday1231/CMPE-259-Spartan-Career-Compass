-- Spartan Career Compass - SQLite schema
-- Applied by scripts/init_db.py to data/career_compass.db

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    start_datetime TEXT,  -- ISO 8601
    end_datetime TEXT,    -- ISO 8601
    location TEXT,
    category TEXT,
    audience TEXT,
    description TEXT,
    source_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS guides (
    guide_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    section TEXT,
    chunk_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    source_pdf TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (title, chunk_id)
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT,
    college TEXT,
    email TEXT,
    phone TEXT,
    office_location TEXT,
    office_hours TEXT,
    profile_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs_cache (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    is_remote INTEGER,
    min_pay NUMERIC,
    max_pay NUMERIC,
    currency TEXT,
    job_type TEXT,
    description TEXT,
    source_api TEXT,
    api_raw TEXT,  -- JSON serialized as TEXT
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_start ON events (start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_guides_title ON guides (title);
CREATE INDEX IF NOT EXISTS idx_staff_college ON staff (college);
