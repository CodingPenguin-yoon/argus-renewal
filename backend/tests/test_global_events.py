from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection
from src.krx.global_events.adapters import BlsScheduleAdapter, candidate_to_payload
from src.krx.global_events.impact_llm import DisabledGlobalEventImpactProvider
from src.krx.global_events.models import (
    GlobalEventCoverageSnapshot,
    GlobalEventReleaseCandidate,
    GlobalEventScheduleCandidate,
    GlobalEventVendorBatch,
)
from src.krx.global_events.service import GlobalEventsService
from src.main import app


def _schedule_candidate(
    *,
    event_key: str,
    event_type: str,
    title: str,
    event_date_local: date,
    event_datetime_local: datetime | None,
    source_key: str = "BLS_SCHEDULE",
    source_name: str = "BLS Release Calendar",
    source_url: str | None = "https://www.bls.gov/schedule/news_release/bls.ics",
    source_timezone: str = "America/New_York",
    reference_period: str | None = "2026-02",
) -> GlobalEventScheduleCandidate:
    return GlobalEventScheduleCandidate(
        event_key=event_key,
        source_key=source_key,
        source_event_id=event_key,
        event_type=event_type,
        title=title,
        category={
            "CPI": "inflation",
            "FOMC": "central_bank",
            "EARNINGS": "earnings",
        }.get(event_type, "macro"),
        country="US",
        event_date_local=event_date_local,
        event_datetime_local=event_datetime_local,
        event_time_precision="time" if event_datetime_local is not None else "date",
        source_timezone=source_timezone,
        reference_period=reference_period if event_type in {"CPI"} else None,
        status="scheduled",
        importance="high",
        importance_source="rule_based",
        why_it_matters_ko="한국 증시 민감 업종과 환율에 영향을 줄 수 있습니다.",
        source_name=source_name,
        source_url=source_url,
        provenance={"event_type": event_type},
    )


@dataclass
class FakeScheduleAdapter:
    source_key: str
    source_name: str
    items: list[GlobalEventScheduleCandidate]
    source_url: str | None = None
    is_required: bool = True

    def fetch(self, *, start_date: date, end_date: date):
        filtered = [item for item in self.items if start_date <= item.event_date_local <= end_date]
        return (
            filtered,
            GlobalEventCoverageSnapshot(
                source_key=self.source_key,
                source_name=self.source_name,
                source_kind="schedule",
                is_required=self.is_required,
                status="available" if filtered else "partial",
                available_count=len(filtered),
                expected_count=max(len(filtered), 1),
                coverage_ratio=1.0 if filtered else 0.0,
                event_types=sorted({item.event_type for item in filtered}),
                last_synced_at="2026-03-10T00:00:00Z",
                last_success_at="2026-03-10T00:00:00Z" if filtered else None,
                source_url=self.source_url,
                note=None if filtered else "no_items",
                metadata={},
            ),
        )


@dataclass
class FakeReleaseAdapter:
    source_key: str
    source_name: str
    items: list[GlobalEventReleaseCandidate]
    source_url: str | None = None
    is_required: bool = True

    def fetch(self, *, events: list[dict]):
        event_keys = {item["event_key"] for item in events}
        filtered = [item for item in self.items if item.event_key in event_keys]
        return (
            filtered,
            GlobalEventCoverageSnapshot(
                source_key=self.source_key,
                source_name=self.source_name,
                source_kind="release",
                is_required=self.is_required,
                status="available" if filtered else "partial",
                available_count=len(filtered),
                expected_count=max(len(filtered), 1) if event_keys else 0,
                coverage_ratio=1.0 if filtered else 0.0,
                event_types=[],
                last_synced_at="2026-03-10T00:00:00Z",
                last_success_at="2026-03-10T00:00:00Z" if filtered else None,
                source_url=self.source_url,
                note=None if filtered else "no_release_items",
                metadata={},
            ),
        )


@dataclass
class FakeVendorAdapter:
    source_key: str = "VENDOR_GLOBAL_EVENTS"
    source_name: str = "Configured Global Events Vendor"
    source_url: str | None = "https://vendor.example.com/calendar"
    is_required: bool = False
    schedules: list[GlobalEventScheduleCandidate] | None = None
    releases: list[GlobalEventReleaseCandidate] | None = None
    status: str = "available"
    note: str | None = None

    def fetch(self, *, start_date: date, end_date: date):
        schedules = [item for item in (self.schedules or []) if start_date <= item.event_date_local <= end_date]
        releases = list(self.releases or [])
        return GlobalEventVendorBatch(
            schedules=schedules,
            releases=releases,
            coverage=GlobalEventCoverageSnapshot(
                source_key=self.source_key,
                source_name=self.source_name,
                source_kind="vendor",
                is_required=self.is_required,
                status=self.status,
                available_count=len(schedules) + len(releases),
                expected_count=max(len(schedules) + len(releases), 1) if self.status != "missing" else 0,
                coverage_ratio=1.0 if schedules or releases else 0.0,
                event_types=sorted({item.event_type for item in schedules}),
                last_synced_at="2026-03-10T00:00:00Z",
                last_success_at="2026-03-10T00:00:00Z" if schedules or releases else None,
                source_url=self.source_url,
                note=self.note,
                metadata={},
            ),
        )


def _make_service(
    tmp_path: Path,
    *,
    schedule_adapters,
    release_adapters=None,
    vendor_adapter=None,
) -> tuple[GlobalEventsService, str]:
    db_path = str(tmp_path / "global-events.db")
    service = GlobalEventsService(
        db_path=db_path,
        schedule_adapters=schedule_adapters,
        release_adapters=release_adapters or [],
        vendor_adapter=vendor_adapter,
        impact_provider=DisabledGlobalEventImpactProvider(),
        sync_enabled=True,
        release_lookback_days=120,
    )
    return service, db_path


def test_schedule_sync_persists_events_and_coverage(tmp_path: Path) -> None:
    et = ZoneInfo("America/New_York")
    service, db_path = _make_service(
        tmp_path,
        schedule_adapters=[
            FakeScheduleAdapter(
                source_key="BLS_SCHEDULE",
                source_name="BLS Release Calendar",
                items=[
                    _schedule_candidate(
                        event_key="BLS:CPI:2026-02",
                        event_type="CPI",
                        title="미국 CPI",
                        event_date_local=date(2026, 3, 11),
                        event_datetime_local=datetime(2026, 3, 11, 8, 30, tzinfo=et),
                    ),
                    _schedule_candidate(
                        event_key="FED:FOMC:2026-03-18",
                        event_type="FOMC",
                        title="FOMC 정례회의",
                        event_date_local=date(2026, 3, 18),
                        event_datetime_local=None,
                        source_key="FED_CALENDAR",
                        source_name="Federal Reserve FOMC Calendar",
                        source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                        reference_period=None,
                    ),
                ],
            )
        ],
    )

    result = service.sync(start_date=date(2026, 3, 9), end_date=date(2026, 3, 21))

    assert result.status == "SUCCESS"
    with get_connection(db_path) as connection:
        schedule_rows = connection.execute(
            "SELECT event_key, event_time_kst, event_time_precision, status FROM global_event_schedule ORDER BY event_key"
        ).fetchall()
        impact_rows = connection.execute("SELECT COUNT(*) AS count FROM global_event_impacts").fetchone()
        coverage_rows = connection.execute(
            "SELECT source_key, status FROM global_event_source_coverage ORDER BY source_key"
        ).fetchall()

    assert len(schedule_rows) == 2
    assert schedule_rows[0]["event_key"] == "BLS:CPI:2026-02"
    assert schedule_rows[0]["event_time_kst"] == "2026-03-11T21:30:00+09:00"
    assert schedule_rows[0]["event_time_precision"] == "time"
    assert schedule_rows[1]["status"] == "scheduled"
    assert impact_rows is not None and impact_rows["count"] == 2
    assert len(coverage_rows) == 1


def test_release_update_merge_preserves_vendor_forecast_and_adds_actual(tmp_path: Path) -> None:
    et = ZoneInfo("America/New_York")
    schedule = _schedule_candidate(
        event_key="BLS:CPI:2026-02",
        event_type="CPI",
        title="미국 CPI",
        event_date_local=date(2026, 3, 11),
        event_datetime_local=datetime(2026, 3, 11, 8, 30, tzinfo=et),
    )
    service, db_path = _make_service(
        tmp_path,
        schedule_adapters=[FakeScheduleAdapter(source_key="BLS_SCHEDULE", source_name="BLS Release Calendar", items=[schedule])],
        vendor_adapter=FakeVendorAdapter(
            schedules=[],
            releases=[
                GlobalEventReleaseCandidate(
                    event_key="BLS:CPI:2026-02",
                    metric_code="headline_cpi_yoy",
                    release_state="forecast_pending",
                    unit="pct",
                    forecast_value=2.8,
                    forecast_display="2.80%",
                    source_name="Configured Global Events Vendor",
                    source_url="https://vendor.example.com/cpi",
                )
            ],
        ),
    )

    service.sync(start_date=date(2026, 3, 9), end_date=date(2026, 3, 21))

    service_with_actual, _ = _make_service(
        tmp_path,
        schedule_adapters=[FakeScheduleAdapter(source_key="BLS_SCHEDULE", source_name="BLS Release Calendar", items=[schedule])],
        release_adapters=[
            FakeReleaseAdapter(
                source_key="BLS_ACTUAL",
                source_name="BLS Public Data API",
                items=[
                    GlobalEventReleaseCandidate(
                        event_key="BLS:CPI:2026-02",
                        metric_code="headline_cpi_yoy",
                        release_state="released",
                        unit="pct",
                        previous_value=2.7,
                        previous_display="2.70%",
                        actual_value=3.1,
                        actual_display="3.10%",
                        source_name="BLS Public Data API",
                        source_url="https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0",
                    )
                ],
            )
        ],
        vendor_adapter=FakeVendorAdapter(),
    )

    service_with_actual.sync(start_date=date(2026, 3, 9), end_date=date(2026, 3, 21))

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT forecast_display, actual_display, surprise_display, release_state
            FROM global_event_releases
            """
        ).fetchone()
        schedule_row = connection.execute(
            "SELECT status FROM global_event_schedule WHERE event_key = 'BLS:CPI:2026-02'"
        ).fetchone()

    assert row is not None
    assert row["forecast_display"] == "2.80%"
    assert row["actual_display"] == "3.10%"
    assert row["surprise_display"] == "+0.30%"
    assert row["release_state"] == "released"
    assert schedule_row is not None
    assert schedule_row["status"] == "released"


def test_vendor_optional_path_adds_big_tech_earnings_schedule(tmp_path: Path) -> None:
    earnings_schedule = _schedule_candidate(
        event_key="VENDOR:EARNINGS:NVDA:2026-05-28",
        event_type="EARNINGS",
        title="NVIDIA 실적",
        event_date_local=date(2026, 5, 28),
        event_datetime_local=datetime(2026, 5, 28, 16, 20, tzinfo=ZoneInfo("America/New_York")),
        source_key="VENDOR_GLOBAL_EVENTS",
        source_name="Configured Global Events Vendor",
        source_url="https://vendor.example.com/earnings",
        reference_period=None,
    )
    service, db_path = _make_service(
        tmp_path,
        schedule_adapters=[],
        vendor_adapter=FakeVendorAdapter(
            schedules=[earnings_schedule],
            releases=[
                GlobalEventReleaseCandidate(
                    event_key="VENDOR:EARNINGS:NVDA:2026-05-28",
                    metric_code="earnings_eps",
                    release_state="forecast_pending",
                    unit="usd",
                    forecast_value=0.81,
                    forecast_display="EPS $0.81",
                    source_name="Configured Global Events Vendor",
                    source_url="https://vendor.example.com/earnings",
                )
            ],
        ),
    )

    service.sync(start_date=date(2026, 5, 1), end_date=date(2026, 5, 31))

    with get_connection(db_path) as connection:
        schedule_row = connection.execute(
            "SELECT event_type, importance, source_key FROM global_event_schedule WHERE event_key = ?",
            ("VENDOR:EARNINGS:NVDA:2026-05-28",),
        ).fetchone()
        coverage_row = connection.execute(
            "SELECT status, source_kind FROM global_event_source_coverage WHERE source_key = 'VENDOR_GLOBAL_EVENTS'"
        ).fetchone()

    assert schedule_row is not None
    assert schedule_row["event_type"] == "EARNINGS"
    assert schedule_row["importance"] == "high"
    assert schedule_row["source_key"] == "VENDOR_GLOBAL_EVENTS"
    assert coverage_row is not None
    assert coverage_row["status"] == "available"
    assert coverage_row["source_kind"] == "vendor"


def test_missing_forecast_path_keeps_null_in_api_payload(tmp_path: Path) -> None:
    service, _ = _make_service(
        tmp_path,
        schedule_adapters=[
            FakeScheduleAdapter(
                source_key="FED_CALENDAR",
                source_name="Federal Reserve FOMC Calendar",
                items=[
                    _schedule_candidate(
                        event_key="FED:FOMC:2026-03-18",
                        event_type="FOMC",
                        title="FOMC 정례회의",
                        event_date_local=date(2026, 3, 18),
                        event_datetime_local=None,
                        source_key="FED_CALENDAR",
                        source_name="Federal Reserve FOMC Calendar",
                        source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                        reference_period=None,
                    )
                ],
            )
        ],
    )

    service.sync(start_date=date(2026, 3, 9), end_date=date(2026, 3, 21))
    payload = service.get_week(anchor=date(2026, 3, 16))

    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["release"]["forecast"] is None
    assert item["release"]["actual"] is None
    assert item["impact"] is not None
    assert item["impact"]["summary_ko"]


def test_kst_conversion_correctness_for_bls_schedule(tmp_path: Path) -> None:
    ics_path = tmp_path / "bls.ics"
    ics_path.write_text(
        "\n".join(
            [
                "BEGIN:VCALENDAR",
                "BEGIN:VEVENT",
                "UID:cpi-2026-02",
                "SUMMARY:Consumer Price Index - February 2026",
                "DTSTART;TZID=America/New_York:20260311T083000",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        ),
        encoding="utf-8",
    )

    adapter = BlsScheduleAdapter(url="https://www.bls.gov/schedule/news_release/bls.ics", file_path=str(ics_path))
    items, _ = adapter.fetch(start_date=date(2026, 3, 1), end_date=date(2026, 3, 31))

    assert len(items) == 1
    payload = candidate_to_payload(items[0])
    assert payload["event_time_kst"] == "2026-03-11T21:30:00+09:00"


def test_global_events_endpoint_reads_seeded_db(tmp_path: Path, monkeypatch) -> None:
    et = ZoneInfo("America/New_York")
    db_path = str(tmp_path / "api-global-events.db")
    service = GlobalEventsService(
        db_path=db_path,
        schedule_adapters=[
            FakeScheduleAdapter(
                source_key="BLS_SCHEDULE",
                source_name="BLS Release Calendar",
                items=[
                    _schedule_candidate(
                        event_key="BLS:CPI:2026-02",
                        event_type="CPI",
                        title="미국 CPI",
                        event_date_local=date(2026, 3, 11),
                        event_datetime_local=datetime(2026, 3, 11, 8, 30, tzinfo=et),
                    )
                ],
            )
        ],
        release_adapters=[],
        impact_provider=DisabledGlobalEventImpactProvider(),
        sync_enabled=True,
    )
    service.sync(start_date=date(2026, 3, 9), end_date=date(2026, 3, 21))

    monkeypatch.setenv("DB_PATH", db_path)
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.get("/api/global-events/highlight")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"]
        assert payload["items"][0]["event_key"] == "BLS:CPI:2026-02"
        assert payload["items"][0]["impact"]["summary_ko"]
    finally:
        get_settings.cache_clear()
