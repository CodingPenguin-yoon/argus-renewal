CREATE TABLE IF NOT EXISTS argus_v2_futures_investor_flow_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    source_name TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KOSPI200_FUTURES',
    foreign_net_buy REAL,
    institution_net_buy REAL,
    individual_net_buy REAL,
    source_url TEXT,
    source_record_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_futures_investor_flow_latest
    ON argus_v2_futures_investor_flow_snapshots(trade_date DESC, snapshot_time DESC);
