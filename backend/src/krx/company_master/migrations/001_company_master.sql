CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    source_system TEXT,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    processed_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_job_name ON sync_runs(job_name);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started_at ON sync_runs(started_at);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    canonical_name_en TEXT,
    normalized_name TEXT,
    primary_stock_code TEXT,
    market TEXT,
    listing_status TEXT,
    instrument_type TEXT NOT NULL DEFAULT 'EQUITY',
    market_classification TEXT,
    is_listed INTEGER NOT NULL DEFAULT 1,
    needs_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    last_mapping_source TEXT,
    last_mapping_confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_companies_primary_stock_code ON companies(primary_stock_code);
CREATE INDEX IF NOT EXISTS idx_companies_normalized_name ON companies(normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_primary_stock_code
    ON companies(primary_stock_code)
    WHERE primary_stock_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS company_source_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL CHECK (source_system IN ('DART', 'KIS')),
    source_record_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_name_en TEXT,
    source_stock_code TEXT,
    source_market TEXT,
    listing_status TEXT,
    market_classification TEXT,
    modify_date TEXT,
    source_url TEXT,
    source_metadata_json TEXT,
    source_snippet TEXT,
    last_seen_run_id INTEGER,
    company_id INTEGER,
    mapping_status TEXT NOT NULL DEFAULT 'UNMAPPED' CHECK (mapping_status IN ('MAPPED', 'UNMAPPED', 'CONFLICT', 'SKIPPED')),
    mapping_source TEXT,
    mapping_confidence REAL,
    needs_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    mapped_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_system, source_record_id),
    FOREIGN KEY(last_seen_run_id) REFERENCES sync_runs(id),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_source_mappings_stock_code ON company_source_mappings(source_stock_code);
CREATE INDEX IF NOT EXISTS idx_company_source_mappings_name ON company_source_mappings(source_name);
CREATE INDEX IF NOT EXISTS idx_company_source_mappings_mapping_status ON company_source_mappings(mapping_status);

CREATE TABLE IF NOT EXISTS company_manual_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL CHECK (source_system IN ('DART', 'KIS')),
    source_record_id TEXT NOT NULL,
    target_company_id INTEGER,
    force_canonical_key TEXT,
    force_canonical_name TEXT,
    action TEXT NOT NULL CHECK (action IN ('MAP', 'SKIP', 'REVIEW')),
    note TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_system, source_record_id),
    FOREIGN KEY(target_company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_manual_overrides_action ON company_manual_overrides(action);
