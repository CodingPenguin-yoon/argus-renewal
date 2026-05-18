CREATE TABLE IF NOT EXISTS argus_v2_collector_leases (
    collector_key TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_argus_v2_collector_leases_expires
    ON argus_v2_collector_leases(expires_at);

