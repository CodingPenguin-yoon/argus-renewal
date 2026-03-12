PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS provider_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    provider_family TEXT NOT NULL CHECK (
        provider_family IN (
            'DISCLOSURE',
            'CURATED_NEWS',
            'DISCOVERY_NEWS',
            'TREND_SIGNAL',
            'MARKET_DATA',
            'REFERENCE_DATA'
        )
    ),
    source_type TEXT CHECK (source_type IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_NEWS')),
    document_kind TEXT CHECK (document_kind IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_CANDIDATE')),
    storage_policy TEXT CHECK (storage_policy IN ('CANONICAL_EVENT', 'PERSISTENT_EVIDENCE', 'TRANSIENT_DISCOVERY')),
    trust_score REAL NOT NULL DEFAULT 0.6,
    priority INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provider_registry_family_priority
    ON provider_registry(provider_family, priority, provider_key);

INSERT OR IGNORE INTO provider_registry (
    provider_key,
    display_name,
    provider_family,
    source_type,
    document_kind,
    storage_policy,
    trust_score,
    priority,
    is_active,
    metadata_json,
    created_at,
    updated_at
) VALUES
    (
        'DART',
        'DART',
        'DISCLOSURE',
        'DISCLOSURE',
        'DISCLOSURE',
        'CANONICAL_EVENT',
        1.0,
        10,
        1,
        '{}',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        'BIGKINDS',
        'BigKinds',
        'CURATED_NEWS',
        'CURATED_NEWS',
        'CURATED_NEWS',
        'PERSISTENT_EVIDENCE',
        0.8,
        20,
        1,
        '{}',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        'NAVER_NEWS',
        'Naver News',
        'DISCOVERY_NEWS',
        'DISCOVERY_NEWS',
        'DISCOVERY_CANDIDATE',
        'TRANSIENT_DISCOVERY',
        0.6,
        30,
        1,
        '{}',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    ),
    (
        'NAVER_DATALAB',
        'Naver DataLab',
        'TREND_SIGNAL',
        NULL,
        NULL,
        NULL,
        0.0,
        40,
        1,
        '{}',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    );

ALTER TABLE raw_document_fetch_runs RENAME TO raw_document_fetch_runs_legacy_010;
CREATE TABLE raw_document_fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    provider TEXT NOT NULL,
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
INSERT INTO raw_document_fetch_runs
SELECT * FROM raw_document_fetch_runs_legacy_010;
DROP TABLE raw_document_fetch_runs_legacy_010;
CREATE INDEX IF NOT EXISTS idx_raw_document_fetch_runs_provider_started_at
    ON raw_document_fetch_runs(provider, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_document_fetch_runs_status
    ON raw_document_fetch_runs(status);

ALTER TABLE raw_document_sources RENAME TO raw_document_sources_legacy_010;
CREATE TABLE raw_document_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
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
INSERT INTO raw_document_sources
SELECT * FROM raw_document_sources_legacy_010;
DROP TABLE raw_document_sources_legacy_010;
CREATE INDEX IF NOT EXISTS idx_raw_document_sources_provider_kind
    ON raw_document_sources(provider, source_kind);

ALTER TABLE raw_documents RENAME TO raw_documents_legacy_010;
CREATE TABLE raw_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
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
INSERT INTO raw_documents
SELECT * FROM raw_documents_legacy_010;
DROP TABLE raw_documents_legacy_010;
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
CREATE INDEX IF NOT EXISTS idx_raw_documents_effective_published_at
    ON raw_documents(COALESCE(published_at, receipt_at, updated_at, created_at));

ALTER TABLE raw_document_dedup_keys RENAME TO raw_document_dedup_keys_legacy_010;
CREATE TABLE raw_document_dedup_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_type TEXT NOT NULL CHECK (dedup_type IN ('PROVIDER_ID', 'NEWS_URL_TITLE')),
    dedup_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    primary_document_id INTEGER NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(dedup_type, dedup_key, document_id),
    FOREIGN KEY(document_id) REFERENCES raw_documents(id),
    FOREIGN KEY(primary_document_id) REFERENCES raw_documents(id)
);
INSERT INTO raw_document_dedup_keys
SELECT * FROM raw_document_dedup_keys_legacy_010;
DROP TABLE raw_document_dedup_keys_legacy_010;
CREATE INDEX IF NOT EXISTS idx_raw_document_dedup_keys_lookup
    ON raw_document_dedup_keys(dedup_type, dedup_key, is_primary);

ALTER TABLE events RENAME TO events_legacy_010;
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    primary_document_id INTEGER NOT NULL UNIQUE,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'earnings',
            'guidance',
            'contract_order',
            'supply_customer',
            'capex_factory',
            'mna_investment',
            'shareholder_return',
            'financing',
            'regulation_policy',
            'product_launch',
            'management_change_of_control',
            'legal_dispute',
            'accident_outage_incident',
            'macro_theme'
        )
    ),
    event_type_label TEXT NOT NULL,
    summary TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
    source_type TEXT NOT NULL CHECK (source_type IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_NEWS')),
    source_provider TEXT NOT NULL,
    publisher TEXT,
    source_url TEXT,
    canonical_url TEXT,
    occurred_at TEXT,
    trust_score REAL NOT NULL,
    confidence REAL NOT NULL,
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (status IN ('AUTO_APPROVED', 'PENDING_REVIEW', 'APPROVED', 'REJECTED')) DEFAULT 'AUTO_APPROVED',
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(primary_document_id) REFERENCES raw_documents(id)
);
INSERT INTO events
SELECT * FROM events_legacy_010;
DROP TABLE events_legacy_010;
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_source_type ON events(source_type);
CREATE INDEX IF NOT EXISTS idx_events_effective_occurred_at
    ON events(COALESCE(occurred_at, updated_at, created_at));

ALTER TABLE source_documents RENAME TO source_documents_legacy_010;
CREATE TABLE source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_document_id INTEGER NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    provider_document_id TEXT,
    document_kind TEXT NOT NULL CHECK (document_kind IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_CANDIDATE')),
    storage_policy TEXT NOT NULL CHECK (storage_policy IN ('CANONICAL_EVENT', 'PERSISTENT_EVIDENCE', 'TRANSIENT_DISCOVERY')),
    title TEXT,
    snippet TEXT,
    publisher TEXT,
    source_url TEXT,
    canonical_url TEXT,
    published_at TEXT,
    receipt_at TEXT,
    company_id INTEGER,
    company_ref TEXT,
    query_text TEXT,
    source_metadata_json TEXT,
    provenance_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(raw_document_id) REFERENCES raw_documents(id) ON DELETE CASCADE,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);
INSERT INTO source_documents
SELECT * FROM source_documents_legacy_010;
DROP TABLE source_documents_legacy_010;
CREATE INDEX IF NOT EXISTS idx_source_documents_provider_published_at
    ON source_documents(provider, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_documents_company_id
    ON source_documents(company_id);

ALTER TABLE event_evidence RENAME TO event_evidence_legacy_010;
CREATE TABLE event_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_event_id INTEGER NOT NULL,
    source_document_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL CHECK (evidence_role IN ('PRIMARY', 'CONFIRMING', 'DISCOVERY')),
    provider TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    publisher TEXT,
    source_url TEXT,
    published_at TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(normalized_event_id, source_document_id),
    FOREIGN KEY(normalized_event_id) REFERENCES normalized_events(id) ON DELETE CASCADE,
    FOREIGN KEY(source_document_id) REFERENCES source_documents(id) ON DELETE CASCADE
);
INSERT INTO event_evidence
SELECT * FROM event_evidence_legacy_010;
DROP TABLE event_evidence_legacy_010;
CREATE INDEX IF NOT EXISTS idx_event_evidence_event_sort
    ON event_evidence(normalized_event_id, sort_order ASC, published_at DESC);

ALTER TABLE source_coverage RENAME TO source_coverage_legacy_010;
CREATE TABLE source_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surface_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('available', 'partial', 'missing')),
    document_count INTEGER NOT NULL DEFAULT 0,
    event_count INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    last_published_at TEXT,
    last_synced_at TEXT,
    note TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(surface_key, provider)
);
INSERT INTO source_coverage
SELECT * FROM source_coverage_legacy_010;
DROP TABLE source_coverage_legacy_010;
CREATE INDEX IF NOT EXISTS idx_source_coverage_surface
    ON source_coverage(surface_key, provider);

PRAGMA foreign_keys = ON;
