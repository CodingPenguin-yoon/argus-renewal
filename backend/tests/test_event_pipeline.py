from __future__ import annotations

import json
from pathlib import Path

from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.provider_registry import build_provider_definition, ensure_provider_definition
from src.krx.source_ingestion.event_service import EventNormalizationService
from src.krx.source_ingestion.llm import DisabledLLMExtractionProvider


def _make_service(
    tmp_path: Path,
    *,
    low_confidence_threshold: float = 0.55,
) -> tuple[EventNormalizationService, str]:
    db_path = str(tmp_path / "event-pipeline.db")
    return (
        EventNormalizationService(
            db_path=db_path,
            llm_provider=DisabledLLMExtractionProvider(),
            low_confidence_threshold=low_confidence_threshold,
        ),
        db_path,
    )


def _insert_company(
    db_path: str,
    *,
    canonical_key: str,
    canonical_name: str,
    primary_stock_code: str | None = None,
) -> int:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO companies (
                canonical_key,
                canonical_name,
                primary_stock_code,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (canonical_key, canonical_name, primary_stock_code, now, now),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])


def _insert_dart_mapping(db_path: str, *, corp_code: str, corp_name: str, company_id: int) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
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
            ("DART", corp_code, corp_name, company_id, "MAPPED", now, now),
        )


def _insert_raw_document(
    db_path: str,
    *,
    provider: str,
    document_type: str,
    title: str,
    summary: str | None,
    publisher: str | None,
    company_id: int | None,
    provider_document_id: str | None,
    source_url: str,
    canonical_url: str | None,
    provider_metadata: dict[str, object] | None = None,
    is_duplicate: int = 0,
    duplicate_of_document_id: int | None = None,
) -> int:
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
                is_duplicate,
                duplicate_of_document_id,
                provider_metadata_json,
                raw_payload_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider,
                provider_document_id,
                document_type,
                title,
                summary,
                publisher,
                source_url,
                canonical_url,
                now,
                now,
                title,
                company_id,
                None,
                None,
                None,
                is_duplicate,
                duplicate_of_document_id,
                json.dumps(provider_metadata or {}, ensure_ascii=False, sort_keys=True),
                json.dumps({"title": title}, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])


def _register_provider(
    db_path: str,
    *,
    provider_key: str,
    provider_family: str,
    trust_score: float,
    priority: int,
) -> None:
    with get_connection(db_path) as connection:
        ensure_provider_definition(
            connection,
            build_provider_definition(
                provider_key=provider_key,
                provider_family=provider_family,
                trust_score=trust_score,
                priority=priority,
            ),
        )


def test_direct_mapping_from_dart(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    company_id = _insert_company(
        db_path,
        canonical_key="manual:samsung",
        canonical_name="삼성전자",
        primary_stock_code="005930",
    )
    _insert_dart_mapping(db_path, corp_code="00126380", corp_name="삼성전자", company_id=company_id)

    raw_document_id = _insert_raw_document(
        db_path,
        provider="DART",
        document_type="DISCLOSURE",
        provider_document_id="20260309000111",
        title="삼성전자 사업보고서",
        summary="사업보고서 제출",
        publisher="DART",
        company_id=company_id,
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260309000111",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260309000111",
        provider_metadata={"corp_code": "00126380", "corp_name": "삼성전자"},
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)

    assert result.status == "SUCCESS"
    assert result.processed_count == 1

    with get_connection(db_path) as connection:
        edge = connection.execute(
            """
            SELECT e.impact_tier, e.mapping_rule_source, x.extraction_method,
                   ev.event_type, ev.sentiment, ev.summary, ev.metadata_json
            FROM event_company_edges e
            JOIN events ev ON ev.id = e.event_id
            JOIN event_extractions x ON x.event_id = ev.id
            WHERE ev.primary_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert edge is not None
    assert edge["impact_tier"] == "direct"
    assert edge["mapping_rule_source"] == "DART_FILER_MATCH"
    assert edge["extraction_method"] == "DETERMINISTIC_DART"
    assert edge["event_type"] == "earnings"
    assert edge["sentiment"] == "neutral"
    assert "삼성전자" in edge["summary"]

    metadata = json.loads(edge["metadata_json"])
    assert metadata["normalized_report_type"] == "삼성전자 사업보고서"
    assert metadata["event_subtype"] == "periodic_report"
    assert metadata["impact_horizon"] == "short"


def test_dart_direct_classification_uses_report_name_semantics(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    company_id = _insert_company(
        db_path,
        canonical_key="manual:testco",
        canonical_name="테스트회사",
        primary_stock_code="000001",
    )
    _insert_dart_mapping(db_path, corp_code="00999999", corp_name="테스트회사", company_id=company_id)

    raw_document_id = _insert_raw_document(
        db_path,
        provider="DART",
        document_type="DISCLOSURE",
        provider_document_id="20260309000999",
        title="[기재정정]현금ㆍ현물배당결정",
        summary=None,
        publisher="DART",
        company_id=company_id,
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260309000999",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260309000999",
        provider_metadata={"corp_code": "00999999", "corp_name": "테스트회사"},
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)

    assert result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT event_type, sentiment, summary, risk_flags_json, metadata_json
            FROM events
            WHERE primary_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert row is not None
    assert row["event_type"] == "shareholder_return"
    assert row["sentiment"] == "positive"
    assert "테스트회사 현금ㆍ현물배당결정" == row["summary"]
    assert "amended_disclosure" in (json.loads(row["risk_flags_json"]) or [])

    metadata = json.loads(row["metadata_json"])
    assert metadata["normalized_report_type"] == "현금ㆍ현물배당결정"
    assert metadata["event_subtype"] == "capital_return"
    assert metadata["impact_direction"] == "positive"


def test_duplicate_news_collapses_to_single_event(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    primary_id = _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-101",
        title="반도체 업황 개선",
        summary="반도체 업황 개선 소식",
        publisher="한국경제",
        company_id=None,
        source_url="https://news.example.com/101",
        canonical_url="https://news.example.com/101",
    )

    _ = _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        provider_document_id=None,
        title="반도체 업황 개선",
        summary="같은 기사 중복 수집",
        publisher="네이버",
        company_id=None,
        source_url="https://news.example.com/101?utm_source=naver",
        canonical_url="https://news.example.com/101",
        is_duplicate=1,
        duplicate_of_document_id=primary_id,
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)

    assert result.status == "SUCCESS"
    assert result.processed_count == 1

    with get_connection(db_path) as connection:
        event_count = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]

    assert event_count == 1


def test_direct_indirect_theme_classification(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    direct_company_id = _insert_company(db_path, canonical_key="manual:samsung", canonical_name="삼성전자")
    indirect_company_id = _insert_company(db_path, canonical_key="manual:hynix", canonical_name="SK하이닉스")
    theme_company_id = _insert_company(db_path, canonical_key="manual:robot", canonical_name="두산로보틱스")

    _insert_raw_document(
        db_path,
        provider="BIGKINDS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="BK-202",
        title="삼성전자, SK하이닉스와 공급 계약 확대",
        summary="두산로보틱스는 정부 정책 테마 수혜 기대",
        publisher="연합뉴스",
        company_id=direct_company_id,
        source_url="https://news.example.com/202",
        canonical_url="https://news.example.com/202",
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT company_id, impact_tier
            FROM event_company_edges
            ORDER BY company_id
            """
        ).fetchall()

    tier_by_company = {int(row["company_id"]): row["impact_tier"] for row in rows}
    assert tier_by_company[direct_company_id] == "direct"
    assert tier_by_company[indirect_company_id] == "indirect"
    assert tier_by_company[theme_company_id] == "theme"


def test_fallback_path_without_llm(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    _insert_company(db_path, canonical_key="manual:naver", canonical_name="NAVER")
    raw_document_id = _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        provider_document_id=None,
        title="NAVER 신규 서비스 출시",
        summary="생성형 AI 기능 확대",
        publisher="연합뉴스",
        company_id=None,
        source_url="https://news.example.com/303",
        canonical_url="https://news.example.com/303",
    )

    result = service.normalize_pending_documents(limit=50, include_llm=True)
    assert result.status == "SUCCESS"

    with get_connection(db_path) as connection:
        extraction = connection.execute(
            """
            SELECT extraction_method, parse_status
            FROM event_extractions
            WHERE raw_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert extraction is not None
    assert extraction["extraction_method"] == "FALLBACK_RULE"
    assert extraction["parse_status"] == "SUCCESS"


def test_registered_custom_provider_uses_registry_source_type_and_trust_score(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)
    _register_provider(
        db_path,
        provider_key="CUSTOM_RSS",
        provider_family="CURATED_NEWS",
        trust_score=0.91,
        priority=15,
    )

    raw_document_id = _insert_raw_document(
        db_path,
        provider="CUSTOM_RSS",
        document_type="NEWS_CANDIDATE",
        provider_document_id="RSS-101",
        title="코스피 반도체 업황 개선",
        summary="외국인 순매수와 업황 회복 기대가 동시에 커졌다.",
        publisher="사용자 RSS",
        company_id=None,
        source_url="https://rss.example.com/101",
        canonical_url="https://rss.example.com/101",
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"
    assert result.processed_count == 1

    with get_connection(db_path) as connection:
        event_row = connection.execute(
            """
            SELECT source_type, source_provider, trust_score
            FROM events
            WHERE primary_document_id = ?
            """,
            (raw_document_id,),
        ).fetchone()

    assert event_row is not None
    assert event_row["source_type"] == "CURATED_NEWS"
    assert event_row["source_provider"] == "CUSTOM_RSS"
    assert abs(float(event_row["trust_score"]) - 0.91) < 1e-6


def test_low_confidence_event_inserted_to_review_queue(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path, low_confidence_threshold=0.9)

    _insert_raw_document(
        db_path,
        provider="NAVER_NEWS",
        document_type="NEWS_CANDIDATE",
        provider_document_id=None,
        title="국내 증시 변동성 확대",
        summary="테마 중심 수급 순환",
        publisher="블로그",
        company_id=None,
        source_url="https://news.example.com/404",
        canonical_url="https://news.example.com/404",
    )

    result = service.normalize_pending_documents(limit=50, include_llm=False)
    assert result.status == "SUCCESS"
    assert result.review_enqueued_count == 1

    with get_connection(db_path) as connection:
        queue_row = connection.execute(
            "SELECT queue_status FROM event_review_queue ORDER BY id DESC LIMIT 1"
        ).fetchone()
        event_row = connection.execute(
            "SELECT status FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert queue_row is not None
    assert queue_row["queue_status"] == "PENDING"
    assert event_row is not None
    assert event_row["status"] == "PENDING_REVIEW"
