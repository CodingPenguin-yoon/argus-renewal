CREATE TABLE IF NOT EXISTS raw_document_fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    mode TEXT NOT NULL CHECK (mode IN ('INCREMENTAL', 'BACKFILL')),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('SYSTEM', 'COMPANY', 'THEME')),
    source_key TEXT,
    query_text TEXT,
    window_start TEXT,
    window_end TEXT,
    cursor_before TEXT,
    cursor_after TEXT,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED_DISABLED')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    processed_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_document_fetch_runs_provider_started_at
    ON raw_document_fetch_runs(provider, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_document_fetch_runs_status
    ON raw_document_fetch_runs(status);

CREATE TABLE IF NOT EXISTS raw_document_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('SYSTEM', 'COMPANY', 'THEME')),
    source_key TEXT NOT NULL,
    source_label TEXT,
    query_template TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    last_cursor TEXT,
    last_success_run_id INTEGER,
    last_success_at TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider, source_kind, source_key),
    FOREIGN KEY(last_success_run_id) REFERENCES raw_document_fetch_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_raw_document_sources_provider_kind
    ON raw_document_sources(provider, source_kind);

CREATE TABLE IF NOT EXISTS raw_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    provider_document_id TEXT,
    document_type TEXT NOT NULL CHECK (document_type IN ('DISCLOSURE', 'NEWS_CANDIDATE')),
    title TEXT,
    summary TEXT,
    publisher TEXT,
    source_url TEXT,
    canonical_url TEXT,
    published_at TEXT,
    receipt_at TEXT,
    report_type TEXT,
    company_id INTEGER,
    company_ref TEXT,
    query_text TEXT,
    normalized_title_hash TEXT,
    is_duplicate INTEGER NOT NULL DEFAULT 0,
    duplicate_of_document_id INTEGER,
    first_seen_run_id INTEGER,
    last_seen_run_id INTEGER,
    provider_metadata_json TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(duplicate_of_document_id) REFERENCES raw_documents(id),
    FOREIGN KEY(first_seen_run_id) REFERENCES raw_document_fetch_runs(id),
    FOREIGN KEY(last_seen_run_id) REFERENCES raw_document_fetch_runs(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_documents_provider_document_id
    ON raw_documents(provider, provider_document_id)
    WHERE provider_document_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_documents_provider_news_identity
    ON raw_documents(provider, canonical_url, normalized_title_hash)
    WHERE provider_document_id IS NULL
      AND canonical_url IS NOT NULL
      AND normalized_title_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_raw_documents_provider_published_at
    ON raw_documents(provider, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_documents_company_id
    ON raw_documents(company_id);
CREATE INDEX IF NOT EXISTS idx_raw_documents_duplicate_of
    ON raw_documents(duplicate_of_document_id);
CREATE INDEX IF NOT EXISTS idx_raw_documents_canonical_url
    ON raw_documents(canonical_url);

CREATE TABLE IF NOT EXISTS raw_document_dedup_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_type TEXT NOT NULL CHECK (dedup_type IN ('PROVIDER_ID', 'NEWS_URL_TITLE')),
    dedup_key TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    document_id INTEGER NOT NULL,
    primary_document_id INTEGER NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(dedup_type, dedup_key, document_id),
    FOREIGN KEY(document_id) REFERENCES raw_documents(id),
    FOREIGN KEY(primary_document_id) REFERENCES raw_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_raw_document_dedup_keys_lookup
    ON raw_document_dedup_keys(dedup_type, dedup_key, is_primary);
