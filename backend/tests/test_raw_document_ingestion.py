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
import src.krx.source_ingestion.factory as ingestion_factory_module
from src.krx.source_ingestion.factory_extensions import (
    RawIngestionFactoryExtension,
    coerce_raw_ingestion_factory_extension,
    load_raw_ingestion_factory_extensions,
)
from src.krx.source_ingestion.models import ProviderFetchBatch, RawDocumentCandidate
from src.krx.source_ingestion.provider_descriptors import DocumentSyncRequest, NewsProviderDescriptor
from src.krx.source_ingestion.providers.bigkinds_provider import BigKindsNewsProvider
from src.krx.source_ingestion.providers.dart_provider import DartDisclosureProvider
from src.krx.source_ingestion.providers.naver_datalab_provider import TrendKeywordGroup, TrendScore, TrendScoreBatch
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


def _build_custom_factory_extension(_settings) -> RawIngestionFactoryExtension:
    custom_descriptor = NewsProviderDescriptor(
        provider="CUSTOM_FACTORY_RSS",
        fetch_batch=lambda request, window_start, window_end, cursor: ProviderFetchBatch(
            records=[],
            next_cursor=cursor,
            metadata={
                "query": request.query_text,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            },
        ),
        build_company_requests=lambda _target: [],
        build_theme_requests=lambda keyword: [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="CUSTOM_FACTORY_RSS",
                source_kind="THEME",
                source_key=keyword,
                source_label=keyword,
                query_template="rss:{keyword}",
                query_text=f"rss:{keyword}",
                company_id=None,
            )
        ],
    )
    return RawIngestionFactoryExtension(news_provider_descriptors=(custom_descriptor,))


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


def test_custom_news_provider_descriptor_can_be_injected(tmp_path: Path) -> None:
    db_path = str(tmp_path / "raw-ingestion.db")

    def _fetch_custom_news(
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ) -> ProviderFetchBatch:
        assert request.provider == "CUSTOM_RSS"
        assert request.query_text == "rss:금리"
        assert cursor is None
        assert window_start < window_end
        return ProviderFetchBatch(
            records=[
                RawDocumentCandidate(
                    provider="CUSTOM_RSS",
                    provider_document_id="RSS-001",
                    document_type="NEWS_CANDIDATE",
                    title="금리 경계감에 국내 증시 변동성 확대",
                    summary="커스텀 RSS provider에서 수집한 기사다.",
                    publisher="Custom RSS",
                    source_url="https://rss.example.com/articles/1",
                    canonical_url="https://rss.example.com/articles/1",
                    published_at="2026-03-08T01:00:00Z",
                    receipt_at=None,
                    report_type=None,
                    company_ref=None,
                    company_id=None,
                    query_text=request.query_text,
                    dedup_type="NEWS_URL_TITLE",
                    dedup_key="custom-rss:1",
                    provider_metadata={"query": request.query_text},
                    raw_payload={"id": "RSS-001", "query": request.query_text},
                )
            ],
            next_cursor="2026-03-08T01:00:00Z",
            metadata={"query": request.query_text},
        )

    custom_descriptor = NewsProviderDescriptor(
        provider="CUSTOM_RSS",
        fetch_batch=_fetch_custom_news,
        build_company_requests=lambda _target: [],
        build_theme_requests=lambda keyword: [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="CUSTOM_RSS",
                source_kind="THEME",
                source_key=keyword,
                source_label=keyword,
                query_template="rss:{keyword}",
                query_text=f"rss:{keyword}",
                company_id=None,
            )
        ],
    )

    service = RawDocumentIngestionService(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=_make_disabled_bigkinds_provider(),
        naver_provider=_make_disabled_naver_provider(),
        extra_news_provider_descriptors=(custom_descriptor,),
    )

    start, end = _window()
    results = service.sync_news_candidates_for_themes_window(
        keywords=["금리"],
        window_start=start,
        window_end=end,
        backfill=False,
    )

    custom_result = next(item for item in results if item.provider == "CUSTOM_RSS")
    assert custom_result.status == "SUCCESS"
    assert custom_result.inserted_count == 1

    with get_connection(db_path) as connection:
        document_row = connection.execute(
            """
            SELECT provider, query_text, raw_payload_json, publisher_key
            FROM raw_documents
            WHERE provider = 'CUSTOM_RSS'
            """
        ).fetchone()
        publisher_row = connection.execute(
            """
            SELECT publisher_key, display_name
            FROM publisher_registry
            WHERE publisher_key = 'CUSTOM_RSS'
            """
        ).fetchone()

    assert document_row is not None
    assert document_row["query_text"] == "rss:금리"
    assert document_row["publisher_key"] == "CUSTOM_RSS"
    assert json.loads(document_row["raw_payload_json"])["id"] == "RSS-001"
    assert publisher_row is not None
    assert publisher_row["display_name"] == "Custom RSS"


def test_backfill_publisher_registry_updates_missing_keys(tmp_path: Path) -> None:
    db_path = str(tmp_path / "publisher-registry.db")
    service = _make_service(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=_make_disabled_bigkinds_provider(),
        naver_provider=_make_disabled_naver_provider(),
    )

    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO raw_documents (
                provider,
                provider_document_id,
                document_type,
                title,
                summary,
                publisher,
                source_url,
                canonical_url,
                published_at,
                receipt_at,
                report_type,
                company_id,
                company_ref,
                query_text,
                normalized_title_hash,
                first_seen_run_id,
                last_seen_run_id,
                provider_metadata_json,
                raw_payload_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CUSTOM_RSS",
                "doc-001",
                "NEWS_CANDIDATE",
                "매경 RSS 테스트 기사",
                "publisher key backfill 검증",
                "매경",
                "https://example.com/rss/doc-001",
                "https://example.com/rss/doc-001",
                "2026-03-08T00:00:00Z",
                None,
                None,
                None,
                None,
                "rss:테스트",
                "hash-001",
                None,
                None,
                "{}",
                "{}",
                now,
                now,
            ),
        )

    payload = service.backfill_publisher_registry()

    assert payload["processed_count"] == 1
    assert payload["publisher_count"] == 1
    assert payload["updated_raw_documents"] == 1

    with get_connection(db_path) as connection:
        document_row = connection.execute(
            """
            SELECT publisher, publisher_key
            FROM raw_documents
            WHERE provider = 'CUSTOM_RSS'
            """
        ).fetchone()
        publisher_row = connection.execute(
            """
            SELECT publisher_key, display_name
            FROM publisher_registry
            WHERE publisher_key = '매일경제'
            """
        ).fetchone()

    assert document_row is not None
    assert document_row["publisher"] == "매경"
    assert document_row["publisher_key"] == "매일경제"
    assert publisher_row is not None
    assert publisher_row["display_name"] == "매일경제"


def test_news_without_published_at_uses_observed_at(tmp_path: Path) -> None:
    db_path = str(tmp_path / "observed-at.db")

    def _fetch_custom_news(
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ) -> ProviderFetchBatch:
        return ProviderFetchBatch(
            records=[
                RawDocumentCandidate(
                    provider="MK_RSS",
                    provider_document_id="MK-001",
                    document_type="NEWS_CANDIDATE",
                    title="매일경제 RSS 기사",
                    summary="발행시각이 없는 테스트 기사",
                    publisher="매일경제",
                    source_url="https://www.mk.co.kr/news/economy/11985698",
                    canonical_url="https://www.mk.co.kr/news/economy/11985698",
                    published_at=None,
                    receipt_at=None,
                    report_type=None,
                    company_ref=None,
                    company_id=None,
                    query_text=request.query_text,
                    dedup_type="NEWS_URL_TITLE",
                    dedup_key="mk-rss:1",
                    provider_metadata={"query": request.query_text},
                    raw_payload={"id": "MK-001"},
                )
            ],
            next_cursor=None,
            metadata={"query": request.query_text},
        )

    service = RawDocumentIngestionService(
        db_path=db_path,
        dart_provider=_make_disabled_dart_provider(),
        bigkinds_provider=_make_disabled_bigkinds_provider(),
        naver_provider=_make_disabled_naver_provider(),
        extra_news_provider_descriptors=(
            NewsProviderDescriptor(
                provider="MK_RSS",
                fetch_batch=_fetch_custom_news,
                build_company_requests=lambda _target: [],
                build_theme_requests=lambda keyword: [
                    DocumentSyncRequest(
                        job_name="raw_documents_sync_news",
                        provider="MK_RSS",
                        source_kind="THEME",
                        source_key=keyword,
                        source_label=keyword,
                        query_template="rss:{keyword}",
                        query_text=f"rss:{keyword}",
                        company_id=None,
                    )
                ],
            ),
        ),
    )

    start, end = _window()
    results = service.sync_news_candidates_for_themes_window(
        keywords=["금리"],
        window_start=start,
        window_end=end,
        backfill=False,
    )

    result = next(item for item in results if item.provider == "MK_RSS")
    assert result.status == "SUCCESS"
    assert result.inserted_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT published_at, observed_at, published_at_source
            FROM raw_documents
            WHERE provider = 'MK_RSS'
            """
        ).fetchone()

    assert row is not None
    assert row["published_at"] is None
    assert row["observed_at"] is not None
    assert row["published_at_source"] == "OBSERVED_AT"


def test_factory_extension_loader_accepts_dict_payload() -> None:
    extension = coerce_raw_ingestion_factory_extension(
        {
            "news": (
                NewsProviderDescriptor(
                    provider="CUSTOM_DICT_RSS",
                    fetch_batch=lambda request, window_start, window_end, cursor: ProviderFetchBatch(
                        records=[],
                        next_cursor=cursor,
                    ),
                    build_company_requests=lambda _target: [],
                    build_theme_requests=lambda _keyword: [],
                ),
            )
        }
    )

    assert [item.provider for item in extension.news_provider_descriptors] == ["CUSTOM_DICT_RSS"]


def test_load_raw_ingestion_factory_extensions_merges_configured_factories() -> None:
    settings = SimpleNamespace(
        raw_ingestion_descriptor_factory_paths="custom.first,custom.second"
    )
    seen_paths: list[str] = []

    from src.krx.source_ingestion import factory_extensions as factory_extensions_module

    def _fake_load_descriptor_factory(path: str):
        seen_paths.append(path)
        return _build_custom_factory_extension

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(factory_extensions_module, "load_descriptor_factory", _fake_load_descriptor_factory)
    try:
        extension = load_raw_ingestion_factory_extensions(settings)
    finally:
        monkeypatch.undo()

    assert seen_paths == ["custom.first", "custom.second"]
    assert [item.provider for item in extension.news_provider_descriptors] == [
        "CUSTOM_FACTORY_RSS",
        "CUSTOM_FACTORY_RSS",
    ]


def test_create_raw_document_ingestion_service_includes_factory_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        db_path="data/test-raw-ingestion-factory.db",
        dart_api_key=None,
        dart_disclosure_list_url="https://opendart.fss.or.kr/api/list.json",
        dart_disclosure_page_count=100,
        raw_ingestion_timeout_seconds=20.0,
        raw_ingestion_max_retries=3,
        raw_ingestion_backoff_seconds=1.0,
        bigkinds_news_enabled=False,
        bigkinds_api_key=None,
        bigkinds_base_url="https://tools.kinds.or.kr",
        bigkinds_search_path="/api/news/search",
        bigkinds_page_size=100,
        bigkinds_page_limit=5,
        naver_news_enabled=False,
        naver_news_client_id=None,
        naver_news_client_secret=None,
        naver_news_base_url="https://openapi.naver.com",
        naver_news_search_path="/v1/search/news.json",
        naver_news_company_query_template="{company_name}",
        naver_news_theme_query_template="{keyword}",
        naver_news_display=50,
        naver_news_page_limit=5,
        raw_ingestion_descriptor_factory_paths="ignored.by.monkeypatch",
    )

    monkeypatch.setattr(
        ingestion_factory_module,
        "load_raw_ingestion_factory_extensions",
        lambda _settings: _build_custom_factory_extension(_settings),
    )

    service = ingestion_factory_module.create_raw_document_ingestion_service(settings)
    supported = service.list_supported_ingestion_providers()

    assert any(item["provider"] == "CUSTOM_FACTORY_RSS" for item in supported["news"])


def test_cli_parser_supports_sync_scheduled_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync-scheduled"])
    assert args.command == "sync-scheduled"


def test_cli_parser_supports_backfill_publishers_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["backfill-publishers", "--limit", "25", "--all"])
    assert args.command == "backfill-publishers"
    assert args.limit == 25
    assert args.all is True


def test_cli_parser_supports_sync_disclosures_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync-disclosures", "--provider", "DART", "--days", "3"])
    assert args.command == "sync-disclosures"
    assert args.provider == "DART"
    assert args.days == 3


def test_cli_parser_supports_sync_news_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "sync-news",
            "--provider",
            "CUSTOM_RSS",
            "--scope",
            "themes",
            "--keyword",
            "금리",
        ]
    )
    assert args.command == "sync-news"
    assert args.provider == ["CUSTOM_RSS"]
    assert args.scope == "themes"
    assert args.keyword == ["금리"]


def test_cli_parser_supports_probe_news_provider_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "probe-news-provider",
            "--provider",
            "BIGKINDS",
            "--query",
            "반도체",
            "--sample-limit",
            "5",
        ]
    )
    assert args.command == "probe-news-provider"
    assert args.provider == "BIGKINDS"
    assert args.query == "반도체"
    assert args.sample_limit == 5


def test_cli_parser_supports_probe_trend_provider_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "probe-trend-provider",
            "--provider",
            "NAVER_DATALAB",
            "--group",
            "반도체=반도체,삼성전자",
            "--sample-limit",
            "3",
        ]
    )
    assert args.command == "probe-trend-provider"
    assert args.provider == "NAVER_DATALAB"
    assert args.group == ["반도체=반도체,삼성전자"]
    assert args.sample_limit == 3


def test_cli_parser_supports_normalize_events_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["normalize-events", "--limit", "10", "--no-llm"])
    assert args.command == "normalize-events"
    assert args.limit == 10
    assert args.no_llm is True


def test_probe_news_provider_returns_limited_samples_without_sync_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []

    class _FakeNewsProvider:
        def fetch_news(self, *, query, window_start, window_end, cursor):
            assert query == "반도체"
            assert cursor is None
            assert window_start < window_end
            return ProviderFetchBatch(
                records=[
                    RawDocumentCandidate(
                        provider="BIGKINDS",
                        provider_document_id=f"BK-{index}",
                        document_type="NEWS_CANDIDATE",
                        title=f"기사 {index}",
                        summary=f"요약 {index}",
                        publisher="테스트경제",
                        source_url=f"https://example.com/{index}",
                        canonical_url=f"https://example.com/{index}",
                        published_at=f"2026-03-0{index}T00:00:00Z",
                        receipt_at=None,
                        report_type=None,
                        company_ref=None,
                        company_id=None,
                        query_text=query,
                        dedup_type="NEWS_URL_TITLE",
                        dedup_key=f"dedup-{index}",
                    )
                    for index in range(1, 4)
                ],
                next_cursor="2026-03-03T00:00:00Z",
                metadata={"query": query},
            )

    fake_service = SimpleNamespace(
        bigkinds_provider=_FakeNewsProvider(),
        naver_provider=None,
    )

    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(ingestion_cli, "create_raw_document_ingestion_service", lambda _settings: fake_service)
    monkeypatch.setattr(ingestion_cli, "_print_json", lambda payload: captured.append(payload))

    ingestion_cli._probe_news_provider(
        provider="BIGKINDS",
        query="반도체",
        days=2,
        sample_limit=2,
    )

    assert len(captured) == 1
    payload = captured[0]
    assert payload["status"] == "SUCCESS"
    assert payload["record_count"] == 3
    assert payload["sample_limit"] == 2
    assert len(payload["samples"]) == 2
    assert payload["samples"][0]["title"] == "기사 1"


def test_probe_news_provider_surfaces_disabled_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []

    class _DisabledNewsProvider:
        def fetch_news(self, *, query, window_start, window_end, cursor):
            return ProviderFetchBatch(
                records=[],
                next_cursor=None,
                disabled_reason="missing_bigkinds_api_key",
            )

    fake_service = SimpleNamespace(
        bigkinds_provider=_DisabledNewsProvider(),
        naver_provider=None,
    )

    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(ingestion_cli, "create_raw_document_ingestion_service", lambda _settings: fake_service)
    monkeypatch.setattr(ingestion_cli, "_print_json", lambda payload: captured.append(payload))

    ingestion_cli._probe_news_provider(
        provider="BIGKINDS",
        query="반도체",
        days=1,
        sample_limit=10,
    )

    assert captured[0]["status"] == "SKIPPED_DISABLED"
    assert captured[0]["disabled_reason"] == "missing_bigkinds_api_key"


def test_probe_trend_provider_returns_score_samples(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []

    class _FakeTrendProvider:
        def fetch_interest_scores(self, *, start_date, end_date, groups):
            assert start_date <= end_date
            assert groups == [TrendKeywordGroup(group_name="반도체", keywords=["반도체", "삼성전자"])]
            return TrendScoreBatch(
                scores={
                    "반도체": TrendScore(
                        group_name="반도체",
                        latest_ratio=77.0,
                        average_ratio=61.5,
                        latest_period=end_date.isoformat(),
                        datapoint_count=7,
                    )
                }
            )

    fake_service = SimpleNamespace(datalab_provider=_FakeTrendProvider())

    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(ingestion_cli, "create_news_product_service", lambda _settings: fake_service)
    monkeypatch.setattr(ingestion_cli, "_print_json", lambda payload: captured.append(payload))

    ingestion_cli._probe_trend_provider(
        provider="NAVER_DATALAB",
        groups=["반도체=반도체,삼성전자"],
        days=7,
        sample_limit=10,
    )

    assert len(captured) == 1
    payload = captured[0]
    assert payload["status"] == "SUCCESS"
    assert payload["score_count"] == 1
    assert payload["samples"][0]["group_name"] == "반도체"
    assert "latest_ratio" in payload["samples"][0]


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


def test_sync_scheduled_uses_configured_provider_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        raw_ingestion_schedule_days=2,
        raw_ingestion_schedule_disclosure_providers="DART,CUSTOM_DISCLOSURE",
        raw_ingestion_schedule_company_news_providers="CUSTOM_RSS",
        raw_ingestion_schedule_theme_news_providers="CUSTOM_RSS,NAVER_NEWS",
        raw_ingestion_schedule_company_ids="101",
        raw_ingestion_schedule_company_names=None,
        raw_ingestion_schedule_theme_keywords="금리",
        raw_ingestion_schedule_include_dart=False,
        raw_ingestion_schedule_include_company_news=False,
        raw_ingestion_schedule_include_theme_news=False,
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def _result(provider: str, source_kind: str, source_key: str | None):
        return SimpleNamespace(
            run_id=1,
            status="SUCCESS",
            provider=provider,
            source_kind=source_kind,
            source_key=source_key,
            processed_count=1,
            inserted_count=1,
            duplicate_count=0,
            failed_count=0,
            cursor_before=None,
            cursor_after=None,
            error_message=None,
        )

    class _FakeService:
        def sync_disclosures_last_days(self, *, provider: str, days: int, backfill: bool):
            calls.append(
                (
                    "sync_disclosures_last_days",
                    {"provider": provider, "days": days, "backfill": backfill},
                )
            )
            return _result(provider, "SYSTEM", "DISCLOSURES")

        def sync_news_candidates_for_companies_last_days(
            self,
            *,
            company_ids: list[int],
            company_names: list[str] | None,
            days: int,
            backfill: bool,
            providers: list[str] | None = None,
        ):
            calls.append(
                (
                    "sync_news_candidates_for_companies_last_days",
                    {
                        "company_ids": company_ids,
                        "company_names": company_names,
                        "days": days,
                        "backfill": backfill,
                        "providers": providers,
                    },
                )
            )
            return [_result("CUSTOM_RSS", "COMPANY", "id:101:company")]

        def sync_news_candidates_for_themes_last_days(
            self,
            *,
            keywords: list[str],
            days: int,
            backfill: bool,
            providers: list[str] | None = None,
        ):
            calls.append(
                (
                    "sync_news_candidates_for_themes_last_days",
                    {
                        "keywords": keywords,
                        "days": days,
                        "backfill": backfill,
                        "providers": providers,
                    },
                )
            )
            return [_result("CUSTOM_RSS", "THEME", "금리")]

    monkeypatch.setattr(ingestion_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(ingestion_cli, "create_raw_document_ingestion_service", lambda _settings: _FakeService())

    ingestion_cli._sync_scheduled()

    assert calls == [
        (
            "sync_disclosures_last_days",
            {"provider": "DART", "days": 2, "backfill": False},
        ),
        (
            "sync_disclosures_last_days",
            {"provider": "CUSTOM_DISCLOSURE", "days": 2, "backfill": False},
        ),
        (
            "sync_news_candidates_for_companies_last_days",
            {
                "company_ids": [101],
                "company_names": [],
                "days": 2,
                "backfill": False,
                "providers": ["CUSTOM_RSS"],
            },
        ),
        (
            "sync_news_candidates_for_themes_last_days",
            {
                "keywords": ["금리"],
                "days": 2,
                "backfill": False,
                "providers": ["CUSTOM_RSS", "NAVER_NEWS"],
            },
        ),
    ]
