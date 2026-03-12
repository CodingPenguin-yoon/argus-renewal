from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from .models import ProviderFetchBatch, RawDocumentCandidate

BatchFetchCallable = Callable[["DocumentSyncRequest", datetime, datetime, Optional[str]], ProviderFetchBatch]
CandidateResolveCallable = Callable[[Any, RawDocumentCandidate], RawDocumentCandidate]
RequestBuildCallable = Callable[[Any], list["DocumentSyncRequest"]]


@dataclass(frozen=True)
class DocumentSyncRequest:
    job_name: str
    provider: str
    source_kind: str
    source_key: str
    source_label: str | None
    query_template: str | None
    query_text: str | None
    company_id: int | None = None


@dataclass(frozen=True)
class DisclosureProviderDescriptor:
    provider: str
    request: DocumentSyncRequest
    fetch_batch: BatchFetchCallable
    resolve_candidate: CandidateResolveCallable | None = None


@dataclass(frozen=True)
class NewsProviderDescriptor:
    provider: str
    fetch_batch: BatchFetchCallable
    build_company_requests: RequestBuildCallable
    build_theme_requests: RequestBuildCallable
