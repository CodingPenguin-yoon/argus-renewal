CREATE TABLE IF NOT EXISTS briefing_input_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('SCHEDULED', 'MANUAL', 'BACKFILL')),
    trade_date TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'SKIPPED_DISABLED')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    processed_provider_count INTEGER NOT NULL DEFAULT 0,
    success_provider_count INTEGER NOT NULL DEFAULT 0,
    failed_provider_count INTEGER NOT NULL DEFAULT 0,
    skipped_provider_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_briefing_input_runs_job_name_started_at
    ON briefing_input_runs(job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_briefing_input_runs_status
    ON briefing_input_runs(status);

CREATE TABLE IF NOT EXISTS market_daily_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    source_name TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    investor_individual_net_buy REAL,
    investor_foreign_net_buy REAL,
    investor_institution_net_buy REAL,
    investor_other_net_buy REAL,
    investor_bank_net_buy REAL,
    investor_pension_net_buy REAL,
    program_buy_total REAL,
    program_sell_total REAL,
    program_net_total REAL,
    credit_balance_total REAL,
    margin_loan_balance REAL,
    stock_financing_balance REAL,
    securities_lending_balance REAL,
    additional_metrics_json TEXT,
    source_url TEXT,
    source_record_id TEXT,
    raw_payload_json TEXT,
    run_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(trade_date, source_name, market_scope),
    FOREIGN KEY(run_id) REFERENCES briefing_input_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_market_daily_factors_trade_date
    ON market_daily_factors(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_daily_factors_source_name
    ON market_daily_factors(source_name);

CREATE TABLE IF NOT EXISTS market_intraday_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    session_type TEXT NOT NULL CHECK (session_type IN ('PRE_OPEN', 'NIGHT_SESSION', 'INTRADAY')),
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
    raw_payload_json TEXT,
    run_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(trade_date, snapshot_time, session_type, source_name, instrument_code),
    FOREIGN KEY(run_id) REFERENCES briefing_input_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_market_intraday_snapshots_trade_date
    ON market_intraday_snapshots(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_intraday_snapshots_source_session
    ON market_intraday_snapshots(source_name, session_type);

CREATE TABLE IF NOT EXISTS derivatives_daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    source_name TEXT NOT NULL,
    metric_scope TEXT NOT NULL DEFAULT 'KRX_DERIVATIVES',
    put_call_ratio REAL,
    implied_volatility REAL,
    open_interest_total REAL,
    call_open_interest REAL,
    put_open_interest REAL,
    futures_investor_foreign_net_buy REAL,
    futures_investor_institution_net_buy REAL,
    futures_investor_individual_net_buy REAL,
    options_investor_foreign_net_buy REAL,
    options_investor_institution_net_buy REAL,
    options_investor_individual_net_buy REAL,
    futures_volume_total REAL,
    options_volume_total REAL,
    additional_metrics_json TEXT,
    source_url TEXT,
    source_record_id TEXT,
    raw_payload_json TEXT,
    run_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(trade_date, source_name, metric_scope),
    FOREIGN KEY(run_id) REFERENCES briefing_input_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_derivatives_daily_metrics_trade_date
    ON derivatives_daily_metrics(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_derivatives_daily_metrics_source_name
    ON derivatives_daily_metrics(source_name);

CREATE TABLE IF NOT EXISTS provider_health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    provider_name TEXT NOT NULL,
    provider_scope TEXT NOT NULL CHECK (
        provider_scope IN (
            'MARKET_DAILY_FACTORS',
            'MARKET_INTRADAY_SNAPSHOTS',
            'DERIVATIVES_DAILY_METRICS',
            'MANUAL_IMPORT'
        )
    ),
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'SKIPPED_DISABLED')),
    checked_at TEXT NOT NULL,
    latency_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    error_message TEXT,
    UNIQUE(run_id, provider_name, provider_scope),
    FOREIGN KEY(run_id) REFERENCES briefing_input_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_provider_health_checks_provider_name
    ON provider_health_checks(provider_name, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_provider_health_checks_status
    ON provider_health_checks(status);
