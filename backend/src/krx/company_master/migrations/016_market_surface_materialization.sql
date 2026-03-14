CREATE TABLE IF NOT EXISTS news_batch_triage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_document_id INTEGER NOT NULL UNIQUE,
    batch_key TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    document_type TEXT NOT NULL,
    market_scope TEXT NOT NULL CHECK (market_scope IN ('kr_market', 'global_market', 'sector', 'company', 'ignore')),
    primary_region TEXT NOT NULL CHECK (primary_region IN ('KR', 'GLOBAL')),
    market_importance_prelim TEXT NOT NULL CHECK (market_importance_prelim IN ('high', 'medium', 'low')),
    impact_direction TEXT NOT NULL CHECK (impact_direction IN ('positive', 'negative', 'mixed', 'neutral')),
    reason_short TEXT,
    affected_companies_json TEXT,
    related_sectors_json TEXT,
    keyword_tags_json TEXT,
    triage_metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(raw_document_id) REFERENCES raw_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_news_batch_triage_cluster_key
    ON news_batch_triage(cluster_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_batch_triage_scope_region
    ON news_batch_triage(market_scope, primary_region, updated_at DESC);

CREATE TABLE IF NOT EXISTS market_surface_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_key TEXT NOT NULL UNIQUE,
    card_key TEXT NOT NULL UNIQUE,
    surface_key TEXT NOT NULL CHECK (surface_key IN ('KR', 'GLOBAL', 'DISCLOSURE')),
    cluster_key TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('news', 'disclosure')),
    source_document_ids_json TEXT,
    title TEXT NOT NULL,
    one_line_summary TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    market_impact TEXT NOT NULL,
    market_scope TEXT NOT NULL CHECK (market_scope IN ('kr_market', 'global_market', 'sector', 'company', 'ignore')),
    primary_region TEXT NOT NULL CHECK (primary_region IN ('KR', 'GLOBAL')),
    trust_score REAL NOT NULL DEFAULT 0,
    materiality_score REAL NOT NULL DEFAULT 0,
    novelty_score REAL NOT NULL DEFAULT 0,
    attention_score REAL NOT NULL DEFAULT 0,
    cross_source_score REAL NOT NULL DEFAULT 0,
    editorial_score REAL NOT NULL DEFAULT 0,
    ranking_score REAL NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_surface_candidates_surface_rank
    ON market_surface_candidates(surface_key, ranking_score DESC, published_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_market_surface_candidates_cluster
    ON market_surface_candidates(cluster_key, surface_key);

CREATE TABLE IF NOT EXISTS market_surface_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surface_key TEXT NOT NULL UNIQUE,
    active_candidate_key TEXT,
    state_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(active_candidate_key) REFERENCES market_surface_candidates(candidate_key) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_market_surface_state_updated_at
    ON market_surface_state(updated_at DESC);

CREATE TABLE IF NOT EXISTS market_surface_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surface_key TEXT NOT NULL,
    candidate_key TEXT,
    change_type TEXT NOT NULL,
    snapshot_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_surface_history_surface_created_at
    ON market_surface_history(surface_key, created_at DESC);
