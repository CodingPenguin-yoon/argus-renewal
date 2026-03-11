CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_document_id INTEGER NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    provider_document_id TEXT,
    document_kind TEXT NOT NULL CHECK (document_kind IN ('DISCLOSURE', 'CURATED_NEWS', 'DISCOVERY_CANDIDATE')),
    storage_policy TEXT NOT NULL CHECK (storage_policy IN ('CANONICAL_EVENT', 'PERSISTENT_EVIDENCE', 'TRANSIENT_DISCOVERY')),
    title TEXT,
    snippet TEXT,
    publisher TEXT,
    source_url TEXT,
    canonical_url TEXT,
    published_at TEXT,
    receipt_at TEXT,
    company_id INTEGER,
    company_ref TEXT,
    query_text TEXT,
    source_metadata_json TEXT,
    provenance_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(raw_document_id) REFERENCES raw_documents(id) ON DELETE CASCADE,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_source_documents_provider_published_at
    ON source_documents(provider, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_documents_company_id
    ON source_documents(company_id);

CREATE TABLE IF NOT EXISTS normalized_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    cluster_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    one_line_summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    market_impact TEXT NOT NULL,
    market_scope TEXT NOT NULL CHECK (market_scope IN ('kr_market', 'global_market', 'sector', 'company', 'ignore')),
    primary_region TEXT NOT NULL CHECK (primary_region IN ('KR', 'GLOBAL')),
    trust_score REAL NOT NULL,
    novelty_score REAL NOT NULL,
    attention_score REAL NOT NULL DEFAULT 0,
    cross_source_score REAL NOT NULL DEFAULT 0,
    ranking_score REAL NOT NULL DEFAULT 0,
    published_at TEXT,
    source_count INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    provenance_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_normalized_events_region_rank
    ON normalized_events(primary_region, ranking_score DESC, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_normalized_events_scope
    ON normalized_events(market_scope);

CREATE TABLE IF NOT EXISTS event_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_event_id INTEGER NOT NULL,
    source_document_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL CHECK (evidence_role IN ('PRIMARY', 'CONFIRMING', 'DISCOVERY')),
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS')),
    title TEXT,
    snippet TEXT,
    publisher TEXT,
    source_url TEXT,
    published_at TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(normalized_event_id, source_document_id),
    FOREIGN KEY(normalized_event_id) REFERENCES normalized_events(id) ON DELETE CASCADE,
    FOREIGN KEY(source_document_id) REFERENCES source_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_evidence_event_sort
    ON event_evidence(normalized_event_id, sort_order ASC, published_at DESC);

CREATE TABLE IF NOT EXISTS event_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_event_id INTEGER NOT NULL,
    tag_type TEXT NOT NULL CHECK (tag_type IN ('sector', 'theme', 'company', 'region', 'scope', 'keyword', 'quality', 'event_type')),
    tag_value TEXT NOT NULL,
    tag_score REAL,
    created_at TEXT NOT NULL,
    UNIQUE(normalized_event_id, tag_type, tag_value),
    FOREIGN KEY(normalized_event_id) REFERENCES normalized_events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_event_tags_lookup
    ON event_tags(tag_type, tag_value);

CREATE TABLE IF NOT EXISTS news_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_key TEXT NOT NULL UNIQUE,
    normalized_event_id INTEGER NOT NULL UNIQUE,
    column_key TEXT NOT NULL CHECK (column_key IN ('KR', 'GLOBAL')),
    title TEXT NOT NULL,
    one_line_summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    market_impact TEXT NOT NULL,
    market_scope TEXT NOT NULL CHECK (market_scope IN ('kr_market', 'global_market', 'sector', 'company', 'ignore')),
    primary_region TEXT NOT NULL CHECK (primary_region IN ('KR', 'GLOBAL')),
    trust_score REAL NOT NULL,
    novelty_score REAL NOT NULL,
    attention_score REAL NOT NULL DEFAULT 0,
    ranking_score REAL NOT NULL DEFAULT 0,
    representative_evidence_id INTEGER,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(normalized_event_id) REFERENCES normalized_events(id) ON DELETE CASCADE,
    FOREIGN KEY(representative_evidence_id) REFERENCES event_evidence(id)
);

CREATE INDEX IF NOT EXISTS idx_news_cards_column_rank
    ON news_cards(column_key, ranking_score DESC, published_at DESC);

CREATE TABLE IF NOT EXISTS source_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surface_key TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('DART', 'BIGKINDS', 'NAVER_NEWS', 'NAVER_DATALAB')),
    status TEXT NOT NULL CHECK (status IN ('available', 'partial', 'missing')),
    document_count INTEGER NOT NULL DEFAULT 0,
    event_count INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    last_published_at TEXT,
    last_synced_at TEXT,
    note TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(surface_key, provider)
);

CREATE INDEX IF NOT EXISTS idx_source_coverage_surface
    ON source_coverage(surface_key, provider);
