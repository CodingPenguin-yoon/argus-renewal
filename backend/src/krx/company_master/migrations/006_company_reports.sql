CREATE TABLE IF NOT EXISTS report_universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_key TEXT NOT NULL UNIQUE,
    universe_name TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    description TEXT,
    selection_mode TEXT NOT NULL DEFAULT 'MANUAL' CHECK (selection_mode IN ('MANUAL', 'FILTER', 'MIXED')),
    selection_config_json TEXT,
    target_size INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_universes_market_scope
    ON report_universes(market_scope, is_active);

CREATE TABLE IF NOT EXISTS report_universe_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    member_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (member_status IN ('ACTIVE', 'INACTIVE')),
    member_source TEXT NOT NULL DEFAULT 'MANUAL',
    weight REAL,
    note TEXT,
    added_at TEXT,
    removed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(universe_id, company_id),
    FOREIGN KEY(universe_id) REFERENCES report_universes(id) ON DELETE CASCADE,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_report_universe_members_universe
    ON report_universe_members(universe_id, member_status);
CREATE INDEX IF NOT EXISTS idx_report_universe_members_company
    ON report_universe_members(company_id, member_status);

CREATE TABLE IF NOT EXISTS company_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    run_mode TEXT NOT NULL CHECK (run_mode IN ('SCHEDULED', 'MANUAL', 'BACKFILL', 'RERUN_FAILED', 'RERUN_SINGLE')),
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'SKIPPED')),
    generation_method TEXT NOT NULL CHECK (generation_method IN ('LLM', 'RULE_BASED', 'HYBRID')),
    llm_provider TEXT,
    llm_model TEXT,
    input_payload_json TEXT NOT NULL,
    report_payload_json TEXT NOT NULL,
    markdown_body TEXT NOT NULL,
    source_coverage_json TEXT,
    confidence_score REAL,
    confidence_bucket TEXT CHECK (confidence_bucket IN ('low', 'medium', 'high')),
    feature_snapshot_json TEXT,
    source_event_count INTEGER NOT NULL DEFAULT 0,
    source_disclosure_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(universe_id, company_id, trade_date),
    FOREIGN KEY(universe_id) REFERENCES report_universes(id),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_reports_company_trade_date
    ON company_reports(company_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_company_reports_universe_trade_date
    ON company_reports(universe_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_company_reports_generated_at
    ON company_reports(generated_at DESC);

CREATE TABLE IF NOT EXISTS company_report_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    section_key TEXT NOT NULL,
    section_title TEXT NOT NULL,
    section_order INTEGER NOT NULL,
    content_markdown TEXT NOT NULL,
    content_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(report_id, section_key),
    FOREIGN KEY(report_id) REFERENCES company_reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_company_report_sections_report
    ON company_report_sections(report_id, section_order);

CREATE TABLE IF NOT EXISTS company_report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_run_key TEXT NOT NULL,
    universe_id INTEGER NOT NULL,
    company_id INTEGER,
    trade_date TEXT NOT NULL,
    run_mode TEXT NOT NULL CHECK (run_mode IN ('SCHEDULED', 'MANUAL', 'BACKFILL', 'RERUN_FAILED', 'RERUN_SINGLE')),
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'SKIPPED')),
    attempt_no INTEGER NOT NULL DEFAULT 1,
    rerun_of_run_id INTEGER,
    report_id INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    elapsed_ms INTEGER,
    source_coverage_json TEXT,
    error_message TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(universe_id) REFERENCES report_universes(id),
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(rerun_of_run_id) REFERENCES company_report_runs(id),
    FOREIGN KEY(report_id) REFERENCES company_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_company_report_runs_batch
    ON company_report_runs(batch_run_key, status);
CREATE INDEX IF NOT EXISTS idx_company_report_runs_universe_trade_date
    ON company_report_runs(universe_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_company_report_runs_company
    ON company_report_runs(company_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_company_report_runs_status
    ON company_report_runs(status, started_at DESC);
