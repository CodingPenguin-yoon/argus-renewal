CREATE TABLE IF NOT EXISTS publisher_registry (
    publisher_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publisher_registry_display_name
    ON publisher_registry(display_name);

ALTER TABLE raw_documents ADD COLUMN publisher_key TEXT;
CREATE INDEX IF NOT EXISTS idx_raw_documents_publisher_key_published_at
    ON raw_documents(publisher_key, published_at DESC);

ALTER TABLE events ADD COLUMN publisher_key TEXT;
CREATE INDEX IF NOT EXISTS idx_events_publisher_key_occurred_at
    ON events(publisher_key, occurred_at DESC);

ALTER TABLE source_documents ADD COLUMN publisher_key TEXT;
CREATE INDEX IF NOT EXISTS idx_source_documents_publisher_key_published_at
    ON source_documents(publisher_key, published_at DESC);

ALTER TABLE event_evidence ADD COLUMN publisher_key TEXT;
CREATE INDEX IF NOT EXISTS idx_event_evidence_publisher_key
    ON event_evidence(publisher_key, published_at DESC);
