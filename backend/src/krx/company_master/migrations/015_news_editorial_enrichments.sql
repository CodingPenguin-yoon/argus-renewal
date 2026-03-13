CREATE TABLE IF NOT EXISTS news_editorial_enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_key TEXT NOT NULL UNIQUE,
    input_hash TEXT NOT NULL,
    story_state TEXT NOT NULL CHECK (story_state IN ('NEW', 'ONGOING', 'DISCLOSURE_CONFIRMED')),
    importance_label TEXT NOT NULL CHECK (importance_label IN ('high', 'medium', 'low')),
    editorial_reason TEXT,
    editorial_boost REAL NOT NULL DEFAULT 0,
    ai_confidence REAL NOT NULL DEFAULT 0,
    provider_name TEXT,
    model_name TEXT,
    raw_output_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_editorial_enrichments_updated_at
    ON news_editorial_enrichments(updated_at DESC);
