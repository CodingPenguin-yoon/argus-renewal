from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.env import get_settings
from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.source_ingestion.company_report_service import CompanyReportService
from src.main import app


def _build_service(tmp_path: Path) -> tuple[CompanyReportService, str]:
    db_path = str(tmp_path / "company-report.db")
    service = CompanyReportService(
        db_path=db_path,
        pipeline_enabled=True,
        market_scope="KRX",
        default_universe_key="KRX_TEST_CORE",
        default_universe_name="KRX Test Core",
        default_universe_target_size=25,
        seed_stock_codes=[],
    )
    return service, db_path


def _insert_company(
    db_path: str,
    *,
    canonical_key: str,
    canonical_name: str,
    stock_code: str,
    market_classification: str | None = None,
) -> int:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO companies (
                canonical_key,
                canonical_name,
                primary_stock_code,
                market,
                listing_status,
                instrument_type,
                market_classification,
                is_listed,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, 'KR', 'LISTED', 'EQUITY', ?, 1, ?, ?)
            """,
            (canonical_key, canonical_name, stock_code, market_classification, now, now),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
    assert row is not None
    return int(row["id"])


def _insert_market_inputs(db_path: str, *, trade_date_iso: str, stock_code: str) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO market_intraday_snapshots (
                trade_date,
                snapshot_time,
                session_type,
                source_name,
                instrument_code,
                instrument_name,
                price,
                price_change,
                change_rate,
                volume,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, ?, 'INTRADAY', 'KIS_DOMESTIC_DERIVATIVES', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                f"{trade_date_iso}T02:00:00Z",
                stock_code,
                "테스트종목",
                100.0,
                1.1,
                1.1,
                100000,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/intraday",
                f"intraday-{stock_code}-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO market_daily_factors (
                trade_date,
                source_name,
                market_scope,
                investor_foreign_net_buy,
                investor_institution_net_buy,
                investor_individual_net_buy,
                program_net_total,
                additional_metrics_json,
                source_url,
                source_record_id,
                raw_payload_json,
                run_id,
                created_at,
                updated_at
            ) VALUES (?, 'KIS_MARKET_BREADTH', 'KRX', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                trade_date_iso,
                3200,
                -1100,
                -2100,
                450,
                json.dumps({}, ensure_ascii=False),
                "https://kis.mock/flow",
                f"flow-{trade_date_iso}",
                json.dumps({"trade_date": trade_date_iso}, ensure_ascii=False),
                now,
                now,
            ),
        )


def _insert_event_and_disclosure(db_path: str, *, company_id: int, trade_date_iso: str) -> None:
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
                provider_metadata_json,
                raw_payload_json,
                created_at,
                updated_at
            ) VALUES ('DART', ?, 'DISCLOSURE', ?, ?, 'DART', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"RCP-{company_id}-{trade_date_iso}",
                "분기 실적 공시",
                "실적 가이던스 업데이트",
                "https://dart.mock/disclosure",
                "https://dart.mock/disclosure",
                f"{trade_date_iso}T08:00:00+09:00",
                f"{trade_date_iso}T08:00:00+09:00",
                "분기보고서",
                company_id,
                json.dumps({"corp_code": "00126380"}, ensure_ascii=False),
                json.dumps({"title": "분기 실적 공시"}, ensure_ascii=False),
                now,
                now,
            ),
        )
        disclosure_row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        assert disclosure_row is not None
        primary_document_id = int(disclosure_row["id"])

        connection.execute(
            """
            INSERT INTO events (
                dedup_key,
                primary_document_id,
                event_type,
                event_type_label,
                summary,
                sentiment,
                source_type,
                source_provider,
                publisher,
                source_url,
                canonical_url,
                occurred_at,
                trust_score,
                confidence,
                risk_flags_json,
                status,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, 'guidance', 'Guidance', ?, 'positive', 'DISCLOSURE', 'DART', 'DART', ?, ?, ?, 0.95, 0.88, '[]', 'AUTO_APPROVED', '{}', ?, ?)
            """,
            (
                f"event-guidance-{company_id}-{trade_date_iso}",
                primary_document_id,
                "실적 가이던스 상향",
                "https://dart.mock/disclosure",
                "https://dart.mock/disclosure",
                f"{trade_date_iso}T08:00:00+09:00",
                now,
                now,
            ),
        )
        event_row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        assert event_row is not None
        event_id = int(event_row["id"])

        connection.execute(
            """
            INSERT INTO event_company_edges (
                event_id,
                company_id,
                impact_tier,
                reason,
                evidence_text,
                mapping_rule_source,
                confidence,
                created_at,
                updated_at
            ) VALUES (?, ?, 'direct', 'guidance', '실적 가이던스 상향', 'UNIT_TEST', 0.9, ?, ?)
            """,
            (event_id, company_id, now, now),
        )


def _insert_kis_mapping_metadata(db_path: str, *, company_id: int, market_cap: float, per: float) -> None:
    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO company_source_mappings (
                source_system,
                source_record_id,
                source_name,
                source_stock_code,
                source_market,
                listing_status,
                source_url,
                source_metadata_json,
                source_snippet,
                company_id,
                mapping_status,
                created_at,
                updated_at
            ) VALUES ('KIS', ?, ?, ?, 'KR', 'LISTED', ?, ?, ?, ?, 'MAPPED', ?, ?)
            """,
            (
                f"KIS-{company_id}",
                "테스트회사",
                "000000",
                "https://kis.mock/mapping",
                json.dumps({"market_cap": market_cap, "per": per}, ensure_ascii=False),
                "kis-mapping",
                company_id,
                now,
                now,
            ),
        )


def test_input_assembly_with_sparse_data(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-a",
        canonical_name="테스트A",
        stock_code="005930",
    )

    service.ensure_universe(universe_key="KRX_TEST_CORE", universe_name="KRX Test Core", target_size=25)
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    run = service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )
    assert run.status == "SUCCESS"

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    assert latest is not None
    assert latest["source_coverage"]["coverage_ratio"] <= 0.4
    assert len(latest["sections"]) == 7


def test_llm_disabled_fallback(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-b",
        canonical_name="테스트B",
        stock_code="000660",
    )
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    _insert_market_inputs(db_path, trade_date_iso="2026-03-09", stock_code="000660")
    _insert_event_and_disclosure(db_path, company_id=company_id, trade_date_iso="2026-03-09")

    run = service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )
    assert run.status == "SUCCESS"

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    assert latest is not None
    assert latest["generation_method"] == "RULE_BASED"
    assert "## 한줄 상태" in latest["markdown_body"]


def test_report_persistence_and_retrieval(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-c",
        canonical_name="테스트C",
        stock_code="035420",
    )
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    _insert_market_inputs(db_path, trade_date_iso="2026-03-08", stock_code="035420")
    _insert_market_inputs(db_path, trade_date_iso="2026-03-09", stock_code="035420")
    _insert_event_and_disclosure(db_path, company_id=company_id, trade_date_iso="2026-03-09")

    service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 8),
        universe_key="KRX_TEST_CORE",
    )
    service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    history = service.list_report_history_for_company(
        company_id=company_id,
        universe_key="KRX_TEST_CORE",
        limit=10,
    )

    assert latest is not None
    assert latest["trade_date"] == "2026-03-09"
    assert len(history) == 2
    assert history[0]["trade_date"] == "2026-03-09"
    assert history[1]["trade_date"] == "2026-03-08"


def test_universe_filtering(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_a = _insert_company(
        db_path,
        canonical_key="krx:test-d1",
        canonical_name="테스트D1",
        stock_code="005380",
    )
    _insert_company(
        db_path,
        canonical_key="krx:test-d2",
        canonical_name="테스트D2",
        stock_code="012330",
    )

    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_a], replace=True)

    result = service.generate_nightly_reports(
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
        mode="SCHEDULED",
    )

    assert result.total_count == 1
    assert result.success_count + result.partial_success_count == 1

    with get_connection(db_path) as connection:
        report_count = connection.execute("SELECT COUNT(*) AS count FROM company_reports").fetchone()["count"]
    assert report_count == 1


def test_rerun_failed_subset_only(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_a = _insert_company(
        db_path,
        canonical_key="krx:test-e1",
        canonical_name="테스트E1",
        stock_code="051910",
    )
    company_b = _insert_company(
        db_path,
        canonical_key="krx:test-e2",
        canonical_name="테스트E2",
        stock_code="006400",
    )

    universe = service.ensure_universe(universe_key="KRX_TEST_CORE", universe_name="KRX Test Core", target_size=25)
    service.sync_universe_members(
        universe_key="KRX_TEST_CORE",
        company_ids=[company_a, company_b],
        replace=True,
    )

    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO company_report_runs (
                batch_run_key,
                universe_id,
                company_id,
                trade_date,
                run_mode,
                status,
                attempt_no,
                rerun_of_run_id,
                report_id,
                started_at,
                finished_at,
                elapsed_ms,
                source_coverage_json,
                error_message,
                metadata_json,
                created_at,
                updated_at
            ) VALUES ('batch-failed-seed', ?, ?, '2026-03-09', 'SCHEDULED', 'FAILED', 1, NULL, NULL, ?, ?, 100, '{}', 'synthetic_fail', '{}', ?, ?)
            """,
            (universe["id"], company_b, now, now, now, now),
        )
        failed_seed_row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        assert failed_seed_row is not None
        failed_seed_run_id = int(failed_seed_row["id"])

        connection.execute(
            """
            INSERT INTO company_report_runs (
                batch_run_key,
                universe_id,
                company_id,
                trade_date,
                run_mode,
                status,
                attempt_no,
                rerun_of_run_id,
                report_id,
                started_at,
                finished_at,
                elapsed_ms,
                source_coverage_json,
                error_message,
                metadata_json,
                created_at,
                updated_at
            ) VALUES ('batch-failed-seed', ?, ?, '2026-03-09', 'SCHEDULED', 'SUCCESS', 1, NULL, NULL, ?, ?, 90, '{}', NULL, '{}', ?, ?)
            """,
            (universe["id"], company_a, now, now, now, now),
        )

    rerun = service.rerun_failed_subset(
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
        reference_batch_run_key="batch-failed-seed",
    )

    assert rerun.total_count == 1
    assert rerun.items[0]["company_id"] == company_b

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT rerun_of_run_id
            FROM company_report_runs
            WHERE batch_run_key = ?
              AND company_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (rerun.batch_run_key, company_b),
        ).fetchone()
    assert row is not None
    assert int(row["rerun_of_run_id"]) == failed_seed_run_id


def test_company_daily_price_preferred_over_intraday_fallback(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-f1",
        canonical_name="테스트F1",
        stock_code="005930",
    )
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    _insert_market_inputs(db_path, trade_date_iso="2026-03-08", stock_code="005930")
    _insert_market_inputs(db_path, trade_date_iso="2026-03-09", stock_code="005930")

    service.import_company_daily_prices(
        company_id=company_id,
        source_name="MANUAL_IMPORT",
        items=[
            {
                "trade_date": "2026-03-08",
                "open": 100,
                "high": 106,
                "low": 99,
                "close": 105,
                "change_rate": 5.0,
                "volume": 1200000,
            },
            {
                "trade_date": "2026-03-09",
                "open": 105,
                "high": 109,
                "low": 104,
                "close": 108,
                "change_rate": 2.85,
                "volume": 1300000,
            },
        ],
    )

    run = service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )
    assert run.status in {"SUCCESS", "PARTIAL_SUCCESS"}

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    assert latest is not None
    assert latest["source_coverage"]["price_context"]["source_table"] == "company_daily_prices"
    assert latest["input_payload"]["price_context"]["summary"]["source_table"] == "company_daily_prices"


def test_company_investor_flow_preferred_over_market_level_flow(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-f2",
        canonical_name="테스트F2",
        stock_code="000660",
    )
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    _insert_market_inputs(db_path, trade_date_iso="2026-03-09", stock_code="000660")
    service.import_company_investor_flows(
        company_id=company_id,
        source_name="MANUAL_IMPORT",
        items=[
            {
                "trade_date": "2026-03-09",
                "foreign_net_buy": -750,
                "institution_net_buy": 210,
                "individual_net_buy": 540,
                "program_net_buy": -40,
            }
        ],
    )

    run = service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )
    assert run.status in {"SUCCESS", "PARTIAL_SUCCESS"}

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    assert latest is not None
    summary = latest["input_payload"]["investor_flow_context"]["summary"]
    assert summary["flow_scope"] == "COMPANY_LEVEL"
    assert summary["source_table"] == "company_investor_flows"
    assert summary["foreign_net_buy_latest"] == -750.0


def test_company_financial_snapshot_table_preferred_over_mapping(tmp_path: Path) -> None:
    service, db_path = _build_service(tmp_path)
    company_id = _insert_company(
        db_path,
        canonical_key="krx:test-f3",
        canonical_name="테스트F3",
        stock_code="035420",
    )
    service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

    _insert_kis_mapping_metadata(db_path, company_id=company_id, market_cap=1000000000, per=18.5)
    service.import_company_financial_snapshots(
        company_id=company_id,
        source_name="MANUAL_IMPORT",
        items=[
            {
                "snapshot_date": "2026-03-09",
                "fiscal_period": "2025Q4",
                "market_cap": 1200000000,
                "per": 12.3,
                "pbr": 1.9,
                "roe": 14.5,
            }
        ],
    )

    run = service.generate_single_company_report(
        company_id=company_id,
        trade_date=date(2026, 3, 9),
        universe_key="KRX_TEST_CORE",
    )
    assert run.status in {"SUCCESS", "PARTIAL_SUCCESS"}

    latest = service.get_latest_report_for_company(company_id=company_id, universe_key="KRX_TEST_CORE")
    assert latest is not None
    financial = latest["input_payload"]["financial_snapshot"]
    assert financial is not None
    assert financial["source_table"] == "company_financial_snapshots"
    assert financial["per"] == 12.3


def test_company_report_admin_api_happy_path(tmp_path: Path, monkeypatch) -> None:
    db_path = str(tmp_path / "company-report-api.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("COMPANY_REPORT_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("COMPANY_REPORT_UNIVERSE_KEY", "KRX_TEST_CORE")
    monkeypatch.setenv("COMPANY_REPORT_SEED_STOCK_CODES", "")
    get_settings.cache_clear()

    try:
        service = CompanyReportService(
            db_path=db_path,
            pipeline_enabled=True,
            default_universe_key="KRX_TEST_CORE",
            default_universe_name="KRX Test Core",
            seed_stock_codes=[],
        )
        company_id = _insert_company(
            db_path,
            canonical_key="krx:test-api",
            canonical_name="테스트API",
            stock_code="005930",
        )
        service.sync_universe_members(universe_key="KRX_TEST_CORE", company_ids=[company_id], replace=True)

        client = TestClient(app)
        generate_response = client.post(
            "/api/krx/admin/company-reports/generate-company",
            params={
                "company_id": company_id,
                "trade_date": "2026-03-09",
                "universe_key": "KRX_TEST_CORE",
            },
        )
        assert generate_response.status_code == 200
        payload = generate_response.json()["item"]
        assert payload["status"] in {"SUCCESS", "PARTIAL_SUCCESS"}

        latest_response = client.get(
            f"/api/krx/admin/company-reports/company/{company_id}/latest",
            params={"universe_key": "KRX_TEST_CORE"},
        )
        assert latest_response.status_code == 200
        latest_payload = latest_response.json()["item"]
        assert latest_payload is not None
        assert latest_payload["trade_date"] == "2026-03-09"
    finally:
        get_settings.cache_clear()
