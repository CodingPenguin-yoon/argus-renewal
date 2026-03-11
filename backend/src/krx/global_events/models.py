from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class GlobalEventScheduleCandidate:
    event_key: str
    source_key: str
    source_event_id: str | None
    event_type: str
    title: str
    category: str
    country: str
    event_date_local: date
    event_datetime_local: datetime | None
    event_time_precision: str
    source_timezone: str
    reference_period: str | None
    status: str
    importance: str | None
    importance_source: str | None
    why_it_matters_ko: str
    source_name: str
    source_url: str | None
    source_updated_at: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class GlobalEventReleaseCandidate:
    event_key: str
    metric_code: str
    release_state: str
    unit: str | None = None
    previous_value: float | None = None
    previous_display: str | None = None
    forecast_value: float | None = None
    forecast_display: str | None = None
    actual_value: float | None = None
    actual_display: str | None = None
    surprise_value: float | None = None
    surprise_display: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_record_id: str | None = None
    actual_released_at: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GlobalEventImpactCandidate:
    event_key: str
    summary_ko: str
    tone: str
    impact_channels: list[str]
    generation_method: str
    provider_name: str | None = None
    model_name: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GlobalEventCoverageSnapshot:
    source_key: str
    source_name: str
    source_kind: str
    is_required: bool
    status: str
    available_count: int
    expected_count: int
    coverage_ratio: float
    event_types: list[str] = field(default_factory=list)
    last_synced_at: str | None = None
    last_success_at: str | None = None
    source_url: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GlobalEventVendorBatch:
    schedules: list[GlobalEventScheduleCandidate]
    releases: list[GlobalEventReleaseCandidate]
    coverage: GlobalEventCoverageSnapshot


@dataclass(frozen=True)
class GlobalEventsSyncResult:
    status: str
    started_at: str
    finished_at: str
    schedule_upserted: int
    release_upserted: int
    impacts_upserted: int
    provider_results: list[dict[str, Any]]
    error_message: str | None = None


class GlobalEventScheduleAdapter(Protocol):
    source_key: str
    source_name: str
    source_url: str | None
    is_required: bool

    def fetch(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[list[GlobalEventScheduleCandidate], GlobalEventCoverageSnapshot]:
        ...


class GlobalEventReleaseAdapter(Protocol):
    source_key: str
    source_name: str
    source_url: str | None
    is_required: bool

    def fetch(
        self,
        *,
        events: list[dict[str, Any]],
    ) -> tuple[list[GlobalEventReleaseCandidate], GlobalEventCoverageSnapshot]:
        ...


class GlobalEventVendorAdapter(Protocol):
    source_key: str
    source_name: str
    source_url: str | None
    is_required: bool

    def fetch(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> GlobalEventVendorBatch:
        ...
