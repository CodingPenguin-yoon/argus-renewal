CREATE TABLE IF NOT EXISTS argus_v2_news_feed_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    raw_sample_id INTEGER,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL,
    published_at TEXT,
    freshness_state TEXT NOT NULL DEFAULT 'missing' CHECK (freshness_state IN ('fresh', 'partial', 'stale', 'missing')),
    source_url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES argus_v2_provider_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(raw_sample_id) REFERENCES argus_v2_provider_samples(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_news_feed_items_latest
    ON argus_v2_news_feed_items(published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_argus_v2_news_feed_items_external
    ON argus_v2_news_feed_items(source_name, external_id);

