CREATE TABLE IF NOT EXISTS argus_v2_market_reaction_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    trade_date TEXT NOT NULL,
    snapshot_time TEXT NOT NULL,
    source_name TEXT NOT NULL,
    kospi_change_rate REAL,
    kosdaq_change_rate REAL,
    kospi200_futures_change_rate REAL,
    advancing_count INTEGER,
    declining_count INTEGER,
    summary TEXT NOT NULL DEFAULT '',
    freshness_state TEXT NOT NULL DEFAULT 'missing' CHECK (freshness_state IN ('fresh', 'partial', 'stale', 'missing')),
    source_url TEXT,
    source_record_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_market_reaction_latest
    ON argus_v2_market_reaction_snapshots(trade_date DESC, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS argus_v2_market_reaction_sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('strong', 'weak')),
    name TEXT NOT NULL,
    change_rate REAL,
    reason TEXT NOT NULL DEFAULT '',
    tone TEXT NOT NULL CHECK (tone IN ('positive', 'neutral', 'negative')),
    source_name TEXT NOT NULL,
    observed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES argus_v2_market_reaction_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_market_reaction_sectors_snapshot
    ON argus_v2_market_reaction_sectors(snapshot_id, role, change_rate DESC);

CREATE TABLE IF NOT EXISTS argus_v2_news_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    impact TEXT NOT NULL CHECK (impact IN ('positive', 'neutral', 'negative')),
    source_name TEXT NOT NULL,
    published_at TEXT,
    connection_strength TEXT NOT NULL CHECK (connection_strength IN ('strong', 'medium', 'weak', 'unclear')),
    freshness_state TEXT NOT NULL DEFAULT 'missing' CHECK (freshness_state IN ('fresh', 'partial', 'stale', 'missing')),
    source_url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_news_triggers_latest
    ON argus_v2_news_triggers(published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_argus_v2_news_triggers_external
    ON argus_v2_news_triggers(source_name, external_id);
