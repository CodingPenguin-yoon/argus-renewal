from __future__ import annotations


def determine_published_at_source(
    *,
    document_type: str | None,
    published_at: str | None,
    receipt_at: str | None,
    observed_at: str | None,
) -> str:
    if published_at:
        return "PROVIDER"
    if receipt_at:
        return "RECEIPT_AT"
    if observed_at:
        return "OBSERVED_AT"
    return "UNKNOWN"


def effective_document_time(
    *,
    document_type: str | None,
    published_at: str | None,
    observed_at: str | None,
    receipt_at: str | None,
    updated_at: str | None = None,
    created_at: str | None = None,
    fallback: str | None = None,
) -> str | None:
    normalized_document_type = str(document_type or "").strip().upper()
    if normalized_document_type == "NEWS_CANDIDATE":
        return published_at or observed_at or receipt_at or updated_at or created_at or fallback
    return published_at or receipt_at or observed_at or updated_at or created_at or fallback


def effective_document_time_sql(*, alias: str) -> str:
    return f"""
    CASE
        WHEN {alias}.document_type = 'NEWS_CANDIDATE'
            THEN COALESCE({alias}.published_at, {alias}.observed_at, {alias}.receipt_at, {alias}.updated_at, {alias}.created_at)
        ELSE COALESCE({alias}.published_at, {alias}.receipt_at, {alias}.observed_at, {alias}.updated_at, {alias}.created_at)
    END
    """.strip()
