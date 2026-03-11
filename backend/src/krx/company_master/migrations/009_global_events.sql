CREATE TABLE IF NOT EXISTS global_event_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL,
    source_event_id TEXT,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    country TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    event_date_kst TEXT NOT NULL,
    event_time_kst TEXT,
    event_time_utc TEXT,
    event_time_precision TEXT NOT NULL CHECK (event_time_precision IN ('time', 'date')),
    sort_at_kst TEXT NOT NULL,
    source_timezone TEXT NOT NULL,
    reference_period TEXT,
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'revised', 'released', 'cancelled', 'tentative')),
    importance TEXT CHECK (importance IN ('high', 'medium', 'low')),
    importance_source TEXT,
    why_it_matters_ko TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    revision_note TEXT,
    previous_event_time_kst TEXT,
    source_updated_at TEXT,
    last_seen_at TEXT NOT NULL,
    provenance_json TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_global_event_schedule_sort
    ON global_event_schedule(sort_at_kst ASC, status);
CREATE INDEX IF NOT EXISTS idx_global_event_schedule_type
    ON global_event_schedule(event_type, event_date_kst);
CREATE INDEX IF NOT EXISTS idx_global_event_schedule_source
    ON global_event_schedule(source_key, event_date_kst);

CREATE TABLE IF NOT EXISTS global_event_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL UNIQUE,
    metric_code TEXT NOT NULL,
    unit TEXT,
    release_state TEXT NOT NULL CHECK (release_state IN ('scheduled', 'forecast_pending', 'actual_pending', 'released', 'partial', 'revised')),
    previous_value REAL,
    previous_display TEXT,
    forecast_value REAL,
    forecast_display TEXT,
    actual_value REAL,
    actual_display TEXT,
    surprise_value REAL,
    surprise_display TEXT,
    source_name TEXT,
    source_url TEXT,
    source_record_id TEXT,
    actual_released_at TEXT,
    provenance_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(schedule_id) REFERENCES global_event_schedule(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_global_event_releases_state
    ON global_event_releases(release_state, actual_released_at DESC);

CREATE TABLE IF NOT EXISTS global_event_impacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL UNIQUE,
    event_key TEXT NOT NULL,
    summary_ko TEXT NOT NULL,
    tone TEXT NOT NULL CHECK (tone IN ('risk_on', 'risk_off', 'hawkish', 'dovish', 'neutral', 'mixed')),
    impact_channels_json TEXT,
    generation_method TEXT NOT NULL CHECK (generation_method IN ('rule_based', 'llm')),
    provider_name TEXT,
    model_name TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stale')),
    provenance_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(schedule_id) REFERENCES global_event_schedule(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_global_event_impacts_event_key
    ON global_event_impacts(event_key, status);

CREATE TABLE IF NOT EXISTS global_event_source_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('schedule', 'release', 'vendor')),
    is_required INTEGER NOT NULL DEFAULT 1 CHECK (is_required IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('available', 'partial', 'missing')),
    available_count INTEGER NOT NULL DEFAULT 0,
    expected_count INTEGER NOT NULL DEFAULT 0,
    coverage_ratio REAL NOT NULL DEFAULT 0,
    event_types_json TEXT,
    last_synced_at TEXT,
    last_success_at TEXT,
    source_url TEXT,
    note TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_global_event_source_coverage_kind
    ON global_event_source_coverage(source_kind, status);
