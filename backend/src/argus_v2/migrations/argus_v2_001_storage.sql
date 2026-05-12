CREATE TABLE IF NOT EXISTS argus_v2_provider_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT NOT NULL,
    provider_label TEXT,
    endpoint TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed', 'skipped')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    observed_count INTEGER NOT NULL DEFAULT 0,
    expected_count INTEGER,
    missing_fields_json TEXT,
    error TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_provider_runs_provider_started
    ON argus_v2_provider_runs(provider_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_argus_v2_provider_runs_status
    ON argus_v2_provider_runs(status, started_at DESC);

CREATE TABLE IF NOT EXISTS argus_v2_provider_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    sample_kind TEXT NOT NULL,
    source_url TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_provider_samples_run
    ON argus_v2_provider_samples(run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS argus_v2_derivatives_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    session_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    instrument_code TEXT NOT NULL,
    instrument_name TEXT,
    price REAL,
    price_change REAL,
    change_rate REAL,
    volume REAL,
    open_interest REAL,
    put_call_ratio REAL,
    implied_volatility REAL,
    additional_metrics_json TEXT,
    source_url TEXT,
    source_record_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_derivatives_snapshots_latest
    ON argus_v2_derivatives_snapshots(trade_date DESC, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_argus_v2_derivatives_snapshots_instrument
    ON argus_v2_derivatives_snapshots(instrument_code, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS argus_v2_option_chain_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    underlying_code TEXT NOT NULL DEFAULT 'KOSPI200',
    underlying_name TEXT,
    underlying_price REAL,
    expiry_date TEXT NOT NULL,
    contract_month TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    atm_strike REAL,
    expected_level_count INTEGER,
    observed_level_count INTEGER NOT NULL DEFAULT 0,
    freshness_state TEXT NOT NULL DEFAULT 'missing' CHECK (freshness_state IN ('fresh', 'partial', 'stale', 'missing')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_option_chain_snapshots_latest
    ON argus_v2_option_chain_snapshots(trade_date DESC, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_argus_v2_option_chain_snapshots_expiry
    ON argus_v2_option_chain_snapshots(expiry_date, underlying_code, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS argus_v2_option_chain_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    strike_price REAL NOT NULL,
    moneyness TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (moneyness IN ('ITM', 'ATM', 'OTM', 'UNKNOWN')),
    call_last_price REAL,
    call_change_rate REAL,
    call_volume REAL,
    call_open_interest REAL,
    call_open_interest_change REAL,
    call_implied_volatility REAL,
    put_last_price REAL,
    put_change_rate REAL,
    put_volume REAL,
    put_open_interest REAL,
    put_open_interest_change REAL,
    put_implied_volatility REAL,
    total_open_interest REAL,
    net_call_put_oi REAL,
    call_put_oi_ratio REAL,
    pressure_side TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (pressure_side IN ('CALL', 'PUT', 'BALANCED', 'UNKNOWN')),
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES argus_v2_option_chain_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_option_chain_levels_snapshot
    ON argus_v2_option_chain_levels(snapshot_id, strike_price);
CREATE INDEX IF NOT EXISTS idx_argus_v2_option_chain_levels_pressure
    ON argus_v2_option_chain_levels(snapshot_id, pressure_side, total_open_interest DESC);
