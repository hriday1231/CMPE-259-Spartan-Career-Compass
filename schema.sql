-- Spartan Career Compass - PostgreSQL schema
-- Run after creating database: createdb career_compass

CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    start_datetime TIMESTAMPTZ,
    end_datetime TIMESTAMPTZ,
    location TEXT,
    category TEXT,
    audience TEXT,
    description TEXT,
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS guides (
    guide_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    section TEXT,
    chunk_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    source_pdf TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (title, chunk_id)
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT,
    college TEXT,
    email TEXT,
    phone TEXT,
    office_location TEXT,
    office_hours TEXT,
    profile_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs_cache (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    is_remote BOOLEAN,
    min_pay NUMERIC,
    max_pay NUMERIC,
    currency TEXT,
    job_type TEXT,
    description TEXT,
    source_api TEXT,
    api_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_start ON events (start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_guides_title ON guides (title);
CREATE INDEX IF NOT EXISTS idx_staff_college ON staff (college);
