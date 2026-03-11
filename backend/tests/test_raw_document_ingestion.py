from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.source_ingestion import cli as ingestion_cli
from src.krx.source_ingestion.cli import build_parser
from src.krx.source_ingestion.providers.bigkinds_provider import BigKindsNewsProvider
from src.krx.source_ingestion.providers.dart_provider import DartDisclosureProvider
from src.krx.source_ingestion.providers.naver_news_provider import NaverNewsProvider
from src.krx.source_ingestion.service import RawDocumentIngestionService


def _make_service(
    *,
    db_path: str,
    dart_provider: DartDisclosureProvider,
    bigkinds_provider: BigKindsNewsProvider,
    naver_provider: NaverNewsProvider,
) -> RawDocumentIngestionService:
    return RawDocumentIngestionService(
        db_path=db_path,
        dart_provider=dart_provider,
        bigkinds_provider=bigkinds_provider,
        naver_provider=naver_provider,
    )


def _window() -> tuple[datetime, datetime]:
    return (
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 3, 9, 23, 59, tzinfo=timezone.utc),
    )


def _make_disabled_dart_provider() -> DartDisclosureProvider:
    return DartDisclosureProvider(
        api_key="",
        list_url="https://opendart.fss.or.kr/api/list.json",
    )


def _make_disabled_bigkinds_provider() -> BigKindsNewsProvider:
    return BigKindsNewsProvider(
        enabled=False,
        api_key=None,
        base_url="https://tools.kinds.or.kr",
        search_path="/api/news/search",
    )


def _make_disabled_naver_provider() -> NaverNewsProvider:
    return NaverNewsProvider(
        enabled=False,
        client_id=None,
        client_secret=None,
        base_url="https://openapi.naver.com",
        search_path="/v1/search/news.json",
        company_query_template="{company_name}",
        theme_query_template="{keyword}",
    )


def test_dart_provider_success_path() -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "status": "000",
                "message": "OK",
                "total_page": 1,
                "list": [
                    {
                        "rcept_no": "20260308000123",
                        "report_nm": "사업보고서",
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "rcept_dt": "20260308",
                    },
                    {
                        "rcept_no": "20260309000456",
                        "report_nm": "분기보고서",
                        "corp_code": "00164742",
                        "corp_name": "SK하이닉스",
                        "rcept_dt": "20260309",
                    },
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    provider = DartDisclosureProvider(
        api_key="dummy",
        list_url="https://opendart.fss.or.kr/api/list.json",
        http_client=client,
    )

    try:
        start, end = _window()
        batch = provider.fetch_disclosures(window_start=start, window_end=end, cursor=None)
    finally:
        client.close()

    assert len(batch.records) == 2
    assert batch.records[0].provider == "DART"
    assert batch.records[0].provider_document_id == "20260308000123"
    assert batch.next_cursor == "20260309:20260309000456"


def test_bigkinds_provider_disabled_path() -> None:
    provider = BigKindsNewsProvider(
        enabled=True,
        api_key=None,
        base_url="https://tools.kinds.or.kr",
        search_path="/api/news/search",
    )
    start, end = _window()

    batch = provider.fetch_news(
        query="삼성전자",
        window_start=start,
        window_end=end,
        cursor=None,
    )

    assert batch.disabled_reason == "missing_bigkinds_api_key"
    assert batch.records == []


def test_bigkinds_variant_payload_and_safe_raw_snapshot(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/api/news/search"):
            return httpx.Response(
                status_code=200,
                json={
                    "return_object": {
                        "result": {
                            "documents": [
                                {
                                    "news_id": "BK-999",
                                    "title": "테마주 급등",
                                    "url": "https://example.com/a/999",
                                    "publisher": "테스트뉴스",
                                    "publish_date": "2026/03/09 10:30:00",
                                    "summary": "요약",
                                    "content": "본문 전체 텍스트는 저장되면 안 됨",
                                }
                            ]
                        }
                    }
                },
            )
        return httpx.Response(status_code=404)

    http_client = httpx.Client(transport=httpx.MockTransport(_handler))
    service = _make_service(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=BigKindsNewsProvider(
            enabled=True,
            api_key="dummy",
            base_url="https://tools.kinds.or.kr",
            search_path="/api/news/search",
            http_client=http_client,
            page_size=50,
            page_limit=1,
        ),
        naver_provider=_make_disabled_naver_provider(),
    )

    try:
        start, end = _window()
        results = service.sync_news_candidates_for_themes_window(
            keywords=["테마주"],
            window_start=start,
            window_end=end,
            backfill=False,
        )
    finally:
        http_client.close()

    result = next(item for item in results if item.provider == "BIGKINDS")
    assert result.status == "SUCCESS"
    assert result.inserted_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT publisher, provider_metadata_json, raw_payload_json FROM raw_documents WHERE provider = 'BIGKINDS'"
        ).fetchone()

    assert row is not None
    payload = json.loads(row["raw_payload_json"])
    assert "content" not in payload
    assert row["publisher"] == "테스트뉴스"


def test_naver_publisher_host_normalization_and_safe_snapshot(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/v1/search/news.json"):
            return httpx.Response(
                status_code=200,
                json={
                    "items": [
                        {
                            "title": "연합뉴스 기사",
                            "originallink": "https://www.yna.co.kr/view/AKR20260309000001",
                            "link": "https://n.news.naver.com/mnews/article/001/000000001",
                            "description": "요약",
                            "pubDate": "Mon, 09 Mar 2026 12:00:00 +0900",
                            "content": "이 필드는 저장되면 안 됨",
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404)

    http_client = httpx.Client(transport=httpx.MockTransport(_handler))
    service = _make_service(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=_make_disabled_bigkinds_provider(),
        naver_provider=NaverNewsProvider(
            enabled=True,
            client_id="id",
            client_secret="secret",
            base_url="https://openapi.naver.com",
            search_path="/v1/search/news.json",
            company_query_template="{company_name}",
            theme_query_template="{keyword}",
            http_client=http_client,
            display=50,
            page_limit=1,
        ),
    )

    try:
        start, end = _window()
        results = service.sync_news_candidates_for_themes_window(
            keywords=["증시"],
            window_start=start,
            window_end=end,
            backfill=False,
        )
    finally:
        http_client.close()

    result = next(item for item in results if item.provider == "NAVER_NEWS")
    assert result.status == "SUCCESS"
    assert result.inserted_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT publisher, raw_payload_json FROM raw_documents WHERE provider = 'NAVER_NEWS'"
        ).fetchone()

    assert row is not None
    assert row["publisher"] == "연합뉴스"
    payload = json.loads(row["raw_payload_json"])
    assert "content" not in payload


def test_duplicate_detection_across_news_providers(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/api/news/search"):
            return httpx.Response(
                status_code=200,
                json={
                    "documents": [
                        {
                            "id": "bk-1",
                            "title": "삼성전자 실적 발표",
                            "url": "https://news.example.com/articles/123?utm_source=test",
                            "publisher": "연합뉴스",
                            "published_at": "2026-03-08T01:00:00Z",
                            "summary": "요약",
                        }
                    ]
                },
            )

        if request.method == "GET" and request.url.path.endswith("/v1/search/news.json"):
            return httpx.Response(
                status_code=200,
                json={
                    "items": [
                        {
                            "title": "<b>삼성전자 실적 발표</b>",
                            "originallink": "https://news.example.com/articles/123",
                            "link": "https://n.news.naver.com/article/001/000000123",
                            "description": "요약",
                            "pubDate": "Mon, 08 Mar 2026 10:00:00 +0900",
                        }
                    ]
                },
            )

        return httpx.Response(status_code=404)

    http_client = httpx.Client(transport=httpx.MockTransport(_handler))

    service = _make_service(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=BigKindsNewsProvider(
            enabled=True,
            api_key="dummy",
            base_url="https://tools.kinds.or.kr",
            search_path="/api/news/search",
            http_client=http_client,
            page_size=50,
            page_limit=1,
        ),
        naver_provider=NaverNewsProvider(
            enabled=True,
            client_id="id",
            client_secret="secret",
            base_url="https://openapi.naver.com",
            search_path="/v1/search/news.json",
            company_query_template="{company_name}",
            theme_query_template="{keyword}",
            http_client=http_client,
            display=50,
            page_limit=1,
        ),
    )

    try:
        start, end = _window()
        results = service.sync_news_candidates_for_themes_window(
            keywords=["반도체"],
            window_start=start,
            window_end=end,
            backfill=False,
        )
    finally:
        http_client.close()

    assert all(result.status == "SUCCESS" for result in results)

    with get_connection(db_path) as connection:
        documents = connection.execute(
            "SELECT id, provider, is_duplicate, duplicate_of_document_id FROM raw_documents ORDER BY id"
        ).fetchall()
        dedup_rows = connection.execute(
            "SELECT dedup_type, dedup_key, document_id, primary_document_id, is_primary FROM raw_document_dedup_keys"
        ).fetchall()

    assert len(documents) == 2
    duplicate_rows = [dict(row) for row in documents if row["is_duplicate"] == 1]
    assert len(duplicate_rows) == 1
    assert duplicate_rows[0]["duplicate_of_document_id"] is not None

    dedup_payload = [dict(row) for row in dedup_rows if row["dedup_type"] == "NEWS_URL_TITLE"]
    assert len(dedup_payload) == 2
    assert any(row["is_primary"] == 1 for row in dedup_payload)
    assert any(row["is_primary"] == 0 for row in dedup_payload)


def test_incremental_sync_resume_for_dart(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")
    state = {
        "rows": [
            {
                "rcept_no": "20260308000001",
                "report_nm": "사업보고서",
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "rcept_dt": "20260308",
            },
            {
                "rcept_no": "20260308000002",
                "report_nm": "분기보고서",
                "corp_code": "00164742",
                "corp_name": "SK하이닉스",
                "rcept_dt": "20260308",
            },
        ]
    }

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "status": "000",
                "message": "OK",
                "total_page": 1,
                "list": state["rows"],
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(_handler))
    dart_provider = DartDisclosureProvider(
        api_key="dummy",
        list_url="https://opendart.fss.or.kr/api/list.json",
        http_client=http_client,
    )

    service = _make_service(
        db_path=db_path,
        dart_provider=dart_provider,
        bigkinds_provider=_make_disabled_bigkinds_provider(),
        naver_provider=_make_disabled_naver_provider(),
    )

    try:
        start, end = _window()
        first = service.sync_dart_disclosures_window(window_start=start, window_end=end, backfill=False)
        second = service.sync_dart_disclosures_window(window_start=start, window_end=end, backfill=False)

        state["rows"] = [
            *state["rows"],
            {
                "rcept_no": "20260309000003",
                "report_nm": "수시공시",
                "corp_code": "00333333",
                "corp_name": "테스트",
                "rcept_dt": "20260309",
            },
        ]

        third = service.sync_dart_disclosures_window(window_start=start, window_end=end, backfill=False)
    finally:
        http_client.close()

    assert first.inserted_count == 2
    assert second.inserted_count == 0
    assert second.processed_count == 0
    assert third.inserted_count == 1

    with get_connection(db_path) as connection:
        doc_count = connection.execute("SELECT COUNT(*) AS count FROM raw_documents").fetchone()["count"]
        source_row = connection.execute(
            "SELECT last_cursor FROM raw_document_sources WHERE provider = 'DART' AND source_kind = 'SYSTEM'"
        ).fetchone()

    assert doc_count == 3
    assert source_row is not None
    assert source_row["last_cursor"] == "20260309:20260309000003"


def test_malformed_payload_handling(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/api/news/search"):
            return httpx.Response(status_code=200, json={"unexpected": "payload"})
        return httpx.Response(status_code=404)

    http_client = httpx.Client(transport=httpx.MockTransport(_handler))

    service = _make_service(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=BigKindsNewsProvider(
            enabled=True,
            api_key="dummy",
            base_url="https://tools.kinds.or.kr",
            search_path="/api/news/search",
            http_client=http_client,
            page_limit=1,
        ),
        naver_provider=_make_disabled_naver_provider(),
    )

    try:
        start, end = _window()
        results = service.sync_news_candidates_for_themes_window(
            keywords=["금리"],
            window_start=start,
            window_end=end,
            backfill=False,
        )
    finally:
        http_client.close()

    bigkinds_result = next(result for result in results if result.provider == "BIGKINDS")
    assert bigkinds_result.status == "FAILED"
    assert bigkinds_result.error_message is not None


def test_happy_path_integration_ingests_dart_and_company_news(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _dart_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "status": "000",
                "message": "OK",
                "total_page": 1,
                "list": [
                    {
                        "rcept_no": "20260307000011",
                        "report_nm": "사업보고서",
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "rcept_dt": "20260307",
                    }
                ],
            },
        )

    def _news_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/api/news/search"):
            return httpx.Response(
                status_code=200,
                json={
                    "documents": [
                        {
                            "id": "bk-777",
                            "title": "삼성전자 투자 확대",
                            "url": "https://news.example.com/articles/777",
                            "publisher": "한국경제",
                            "published_at": "2026-03-07T02:00:00Z",
                            "summary": "투자 확대 소식",
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404)

    dart_client = httpx.Client(transport=httpx.MockTransport(_dart_handler))
    news_client = httpx.Client(transport=httpx.MockTransport(_news_handler))

    service = _make_service(
        db_path=db_path,
        dart_provider=DartDisclosureProvider(
            api_key="dummy",
            list_url="https://opendart.fss.or.kr/api/list.json",
            http_client=dart_client,
        ),
        bigkinds_provider=BigKindsNewsProvider(
            enabled=True,
            api_key="dummy",
            base_url="https://tools.kinds.or.kr",
            search_path="/api/news/search",
            http_client=news_client,
            page_limit=1,
        ),
        naver_provider=_make_disabled_naver_provider(),
    )

    with get_connection(db_path) as connection:
        now = utcnow_iso()
        connection.execute(
            """
            INSERT INTO companies (
                canonical_key,
                canonical_name,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("manual:samsung", "삼성전자", now, now),
        )
        company_id = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        connection.execute(
            """
            INSERT INTO company_source_mappings (
                source_system,
                source_record_id,
                source_name,
                company_id,
                mapping_status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("DART", "00126380", "삼성전자", company_id, "MAPPED", now, now),
        )

    try:
        start, end = _window()
        dart_result = service.sync_dart_disclosures_window(
            window_start=start,
            window_end=end,
            backfill=False,
        )
        news_results = service.sync_news_candidates_for_companies_window(
            company_ids=[company_id],
            company_names=None,
            window_start=start,
            window_end=end,
            backfill=False,
        )
    finally:
        dart_client.close()
        news_client.close()

    assert dart_result.status == "SUCCESS"
    assert any(result.provider == "BIGKINDS" and result.status == "SUCCESS" for result in news_results)

    with get_connection(db_path) as connection:
        dart_document = connection.execute(
            """
            SELECT provider, company_id, provider_document_id
            FROM raw_documents
            WHERE provider = 'DART'
            """
        ).fetchone()
        news_document = connection.execute(
            """
            SELECT provider, title, company_id
            FROM raw_documents
            WHERE provider = 'BIGKINDS'
            """
        ).fetchone()
        run_count = connection.execute(
            "SELECT COUNT(*) AS count FROM raw_document_fetch_runs"
        ).fetchone()["count"]

    assert dart_document is not None
    assert dart_document["company_id"] == company_id
    assert dart_document["provider_document_id"] == "20260307000011"
    assert news_document is not None
    assert news_document["company_id"] == company_id
    assert run_count >= 2


def test_cli_parser_supports_sync_scheduled_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync-scheduled"])
    assert args.command == "sync-scheduled"


def test_cli_parser_supports_normalize_events_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["normalize-events", "--limit", "10", "--no-llm"])
    assert args.command == "normalize-events"
    assert args.limit == 10
    assert args.no_llm is True


def test_sync_scheduled_returns_non_zero_when_any_run_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        raw_ingestion_schedule_days=1,
        raw_ingestion_schedule_company_ids=None,
        raw_ingestion_schedule_company_names=None,
        raw_ingestion_schedule_theme_keywords=None,
        raw_ingestion_schedule_include_dart=True,
        raw_ingestion_schedule_include_company_news=False,
        raw_ingestion_schedule_include_theme_news=False,
    )

    class _FakeService:
        def sync_dart_disclosures_last_days(self, *, days: int, backfill: bool):
            assert days == 1
            assert backfill is False
            return SimpleNamespace(
                run_id=1,
                status="FAILED",
                provider="DART",
                source_kind="SYSTEM",
                source_key="DISCLOSURES",
                processed_count=1,
                inserted_count=0,
                duplicate_count=0,
                failed_count=1,
                cursor_before=None,
                cursor_after=None,
                error_message="boom",
            )

    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(ingestion_cli, "create_raw_document_ingestion_service", lambda _settings: _FakeService())

    with pytest.raises(SystemExit) as error:
        ingestion_cli._sync_scheduled()

    assert error.value.code == 1
