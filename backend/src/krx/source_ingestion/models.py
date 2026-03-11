from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawDocumentCandidate:
    provider: str
    provider_document_id: str | None
    document_type: str
    title: str | None
    summary: str | None
    publisher: str | None
    source_url: str | None
    canonical_url: str | None
    published_at: str | None
    receipt_at: str | None
    report_type: str | None
    company_ref: str | None
    company_id: int | None
    query_text: str | None
    dedup_type: str | None
    dedup_key: str | None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderFetchBatch:
    records: list[RawDocumentCandidate]
    next_cursor: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    disabled_reason: str | None = None
