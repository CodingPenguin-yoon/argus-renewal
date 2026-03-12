ALTER TABLE raw_documents ADD COLUMN observed_at TEXT;
ALTER TABLE raw_documents ADD COLUMN published_at_source TEXT CHECK (
    published_at_source IN ('PROVIDER', 'RECEIPT_AT', 'OBSERVED_AT', 'UNKNOWN')
);

UPDATE raw_documents
SET observed_at = COALESCE(observed_at, created_at, updated_at)
WHERE observed_at IS NULL;

UPDATE raw_documents
SET published_at_source = CASE
    WHEN published_at IS NOT NULL THEN 'PROVIDER'
    WHEN receipt_at IS NOT NULL THEN 'RECEIPT_AT'
    WHEN observed_at IS NOT NULL THEN 'OBSERVED_AT'
    ELSE 'UNKNOWN'
END
WHERE published_at_source IS NULL;

CREATE INDEX IF NOT EXISTS idx_raw_documents_provider_observed_at
    ON raw_documents(provider, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_documents_effective_document_time
    ON raw_documents(
        CASE
            WHEN document_type = 'NEWS_CANDIDATE'
                THEN COALESCE(published_at, observed_at, receipt_at, updated_at, created_at)
            ELSE COALESCE(published_at, receipt_at, observed_at, updated_at, created_at)
        END
    );

ALTER TABLE source_documents ADD COLUMN observed_at TEXT;
ALTER TABLE source_documents ADD COLUMN published_at_source TEXT CHECK (
    published_at_source IN ('PROVIDER', 'RECEIPT_AT', 'OBSERVED_AT', 'UNKNOWN')
);

UPDATE source_documents
SET
    observed_at = (
        SELECT rd.observed_at
        FROM raw_documents rd
        WHERE rd.id = source_documents.raw_document_id
    ),
    published_at_source = (
        SELECT rd.published_at_source
        FROM raw_documents rd
        WHERE rd.id = source_documents.raw_document_id
    )
WHERE raw_document_id IN (
    SELECT id
    FROM raw_documents
);

CREATE INDEX IF NOT EXISTS idx_source_documents_effective_document_time
    ON source_documents(
        CASE
            WHEN document_kind IN ('CURATED_NEWS', 'DISCOVERY_CANDIDATE')
                THEN COALESCE(published_at, observed_at, receipt_at, updated_at, created_at)
            ELSE COALESCE(published_at, receipt_at, observed_at, updated_at, created_at)
        END
    );

ALTER TABLE event_evidence ADD COLUMN observed_at TEXT;

UPDATE event_evidence
SET observed_at = (
    SELECT sd.observed_at
    FROM source_documents sd
    WHERE sd.id = event_evidence.source_document_id
)
WHERE source_document_id IN (
    SELECT id
    FROM source_documents
);

CREATE INDEX IF NOT EXISTS idx_event_evidence_effective_document_time
    ON event_evidence(COALESCE(published_at, observed_at, updated_at, created_at));
