CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT NOT NULL UNIQUE,
    primary_document_id INTEGER NOT NULL UNIQUE,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'earnings',
            'guidance',
            'contract_order',
            'supply_customer',
            'capex_factory',
            'mna_investment',
            'shareholder_return',
            'financing',
            'regulation_policy',
            'product_launch',
            'management_change_of_control',
            'legal_dispute',
            'accident_outage_incident',
            'macro_theme'
        )
    ),
    event_type_label TEXT NOT NULL,
    summary TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral', 'mixed')),
    source_type TEXT NOT NULL CHECK (source_type IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_NEWS')),
    source_provider TEXT NOT NULL CHECK (source_provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    publisher TEXT,
    source_url TEXT,
    canonical_url TEXT,
    occurred_at TEXT,
    trust_score REAL NOT NULL,
    confidence REAL NOT NULL,
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (status IN ('AUTO_APPROVED', 'PENDING_REVIEW', 'APPROVED', 'REJECTED')) DEFAULT 'AUTO_APPROVED',
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(primary_document_id) REFERENCES raw_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_source_type ON events(source_type);

CREATE TABLE IF NOT EXISTS event_company_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    impact_tier TEXT NOT NULL CHECK (impact_tier IN ('direct', 'indirect', 'theme')),
    reason TEXT,
    evidence_text TEXT,
    mapping_rule_source TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, company_id, impact_tier),
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_event_company_edges_company_id ON event_company_edges(company_id);
CREATE INDEX IF NOT EXISTS idx_event_company_edges_tier ON event_company_edges(impact_tier);

CREATE TABLE IF NOT EXISTS event_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_document_id INTEGER NOT NULL UNIQUE,
    event_id INTEGER,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN ('LLM', 'FALLBACK_RULE', 'DETERMINISTIC_DART')),
    llm_provider TEXT,
    llm_model TEXT,
    parse_status TEXT NOT NULL CHECK (parse_status IN ('SUCCESS', 'FAILED', 'SKIPPED')),
    input_hash TEXT,
    output_json TEXT,
    error_message TEXT,
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(raw_document_id) REFERENCES raw_documents(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_event_extractions_event_id ON event_extractions(event_id);
CREATE INDEX IF NOT EXISTS idx_event_extractions_method_status ON event_extractions(extraction_method, parse_status);

CREATE TABLE IF NOT EXISTS event_review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL UNIQUE,
    queue_status TEXT NOT NULL CHECK (queue_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    review_reason TEXT NOT NULL,
    review_score REAL,
    review_threshold REAL,
    reviewer TEXT,
    review_note TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_review_queue_status ON event_review_queue(queue_status);
CREATE INDEX IF NOT EXISTS idx_event_review_queue_created_at ON event_review_queue(created_at DESC);
