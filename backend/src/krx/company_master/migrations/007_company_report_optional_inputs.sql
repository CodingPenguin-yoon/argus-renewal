CREATE TABLE IF NOT EXISTS company_daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    adjusted_close REAL,
    volume REAL,
    turnover REAL,
    change_rate REAL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, trade_date, source_name),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_daily_prices_company_trade_date
    ON company_daily_prices(company_id, trade_date DESC);

CREATE TABLE IF NOT EXISTS company_investor_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    foreign_net_buy REAL,
    institution_net_buy REAL,
    individual_net_buy REAL,
    program_net_buy REAL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, trade_date, source_name),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_investor_flows_company_trade_date
    ON company_investor_flows(company_id, trade_date DESC);

CREATE TABLE IF NOT EXISTS company_financial_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    fiscal_period TEXT,
    market_cap REAL,
    per REAL,
    pbr REAL,
    roe REAL,
    eps REAL,
    bps REAL,
    dividend_yield REAL,
    revenue REAL,
    operating_income REAL,
    net_income REAL,
    debt_ratio REAL,
    currency TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    raw_payload_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, snapshot_date, source_name),
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_company_financial_snapshots_company_date
    ON company_financial_snapshots(company_id, snapshot_date DESC);
