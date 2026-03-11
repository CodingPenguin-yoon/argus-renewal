CREATE TABLE IF NOT EXISTS market_briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    run_mode TEXT NOT NULL CHECK (run_mode IN ('SCHEDULED', 'MANUAL', 'BACKFILL')),
    directional_bias TEXT NOT NULL CHECK (directional_bias IN ('bullish', 'bearish', 'neutral')),
    gap_bias TEXT NOT NULL CHECK (gap_bias IN ('gap_up', 'gap_down', 'flat')),
    volatility_bias TEXT NOT NULL CHECK (volatility_bias IN ('rising', 'stable', 'falling')),
    confidence_bucket TEXT NOT NULL CHECK (confidence_bucket IN ('low', 'medium', 'high')),
    total_score REAL NOT NULL,
    volatility_score REAL NOT NULL DEFAULT 0,
    explanation_ko TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    markdown_summary TEXT NOT NULL,
    notification_payload_json TEXT,
    rule_config_json TEXT,
    input_snapshot_json TEXT,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(trade_date, market_scope)
);

CREATE INDEX IF NOT EXISTS idx_market_briefings_trade_date
    ON market_briefings(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_briefings_confidence
    ON market_briefings(confidence_bucket);

CREATE TABLE IF NOT EXISTS market_signal_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    component_key TEXT NOT NULL,
    component_label TEXT NOT NULL,
    component_group TEXT NOT NULL CHECK (component_group IN ('directional', 'volatility', 'gap', 'optional')),
    raw_value REAL,
    reference_value REAL,
    delta_value REAL,
    score REAL NOT NULL,
    volatility_score REAL NOT NULL DEFAULT 0,
    weight REAL NOT NULL,
    data_available INTEGER NOT NULL DEFAULT 0,
    source_table TEXT,
    source_name TEXT,
    source_url TEXT,
    source_record_id TEXT,
    source_metric_key TEXT,
    threshold_json TEXT,
    metadata_json TEXT,
    explanation_ko TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(briefing_id, component_key),
    FOREIGN KEY(briefing_id) REFERENCES market_briefings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_signal_components_trade_date
    ON market_signal_components(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_signal_components_component_key
    ON market_signal_components(component_key);

CREATE TABLE IF NOT EXISTS market_signal_backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    evaluation_date TEXT NOT NULL,
    market_scope TEXT NOT NULL DEFAULT 'KRX',
    predicted_directional_bias TEXT NOT NULL CHECK (predicted_directional_bias IN ('bullish', 'bearish', 'neutral')),
    actual_directional_bias TEXT NOT NULL CHECK (actual_directional_bias IN ('bullish', 'bearish', 'neutral', 'unknown')),
    predicted_gap_bias TEXT NOT NULL CHECK (predicted_gap_bias IN ('gap_up', 'gap_down', 'flat')),
    actual_gap_bias TEXT NOT NULL CHECK (actual_gap_bias IN ('gap_up', 'gap_down', 'flat', 'unknown')),
    predicted_volatility_bias TEXT NOT NULL CHECK (predicted_volatility_bias IN ('rising', 'stable', 'falling')),
    actual_volatility_bias TEXT NOT NULL CHECK (actual_volatility_bias IN ('rising', 'stable', 'falling', 'unknown')),
    directional_hit INTEGER,
    gap_hit INTEGER,
    volatility_hit INTEGER,
    hit_rate REAL,
    confusion_summary_json TEXT,
    score_distribution_json TEXT,
    metrics_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(briefing_id, evaluation_date),
    FOREIGN KEY(briefing_id) REFERENCES market_briefings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_signal_backtests_trade_date
    ON market_signal_backtests(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_signal_backtests_evaluation_date
    ON market_signal_backtests(evaluation_date DESC);
