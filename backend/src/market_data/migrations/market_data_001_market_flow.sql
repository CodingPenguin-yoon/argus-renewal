CREATE TABLE IF NOT EXISTS market_data_market_flow_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    data_mode TEXT NOT NULL CHECK (data_mode IN ('mock', 'live')),
    market_scope TEXT NOT NULL CHECK (market_scope IN ('KRX')),
    segment TEXT NOT NULL CHECK (
        segment IN ('kospi_spot', 'kospi200_futures', 'kospi200_call', 'kospi200_put')
    ),
    quality TEXT NOT NULL CHECK (quality IN ('estimate', 'confirmed')),
    trade_date TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('KRW')),
    individual_net INTEGER NOT NULL,
    foreign_net INTEGER NOT NULL,
    institution_net INTEGER NOT NULL,
    UNIQUE (source, data_mode, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_market_flow_latest
ON market_data_market_flow_facts (
    data_mode,
    market_scope,
    segment,
    quality,
    observed_at DESC,
    id DESC
);

