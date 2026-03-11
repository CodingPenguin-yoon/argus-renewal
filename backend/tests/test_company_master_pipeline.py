from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import zipfile

import httpx

from src.krx.company_master.db import get_connection, utcnow_iso
from src.krx.company_master.providers.dart import DartClient
from src.krx.company_master.providers.kis import KisApiMasterClient, KisFileMasterClient
from src.krx.company_master.service import CompanyMasterService


@dataclass(frozen=True)
class _DartRecord:
    corp_code: str
    corp_name: str
    corp_eng_name: str | None
    stock_code: str | None
    modify_date: str | None
    source_url: str


@dataclass(frozen=True)
class _KisRecord:
    symbol: str
    name: str
    market: str | None
    listing_status: str | None
    market_classification: str | None
    source_url: str


def _make_service(tmp_path: Path) -> tuple[CompanyMasterService, str]:
    db_path = str(tmp_path / "company-master.db")
    return CompanyMasterService(db_path=db_path), db_path


def _fetch_source_row(db_path: str, source_system: str, source_record_id: str) -> dict:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM company_source_mappings
            WHERE source_system = ? AND source_record_id = ?
            """,
            (source_system, source_record_id),
        ).fetchone()
    assert row is not None
    return dict(row)


def test_exact_stock_code_match(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    dart_records = [
        _DartRecord(
            corp_code="00126380",
            corp_name="삼성전자",
            corp_eng_name="Samsung Electronics",
            stock_code="005930",
            modify_date="20260101",
            source_url="https://opendart.fss.or.kr/api/corpCode.xml",
        )
    ]
    kis_records = [
        _KisRecord(
            symbol="005930",
            name="삼성전자",
            market="KOSPI",
            listing_status="LISTED",
            market_classification="ST",
            source_url="/tmp/kis.csv",
        )
    ]

    service.sync_dart(dart_records)
    service.sync_kis(kis_records)
    result = service.build_mapping()

    assert result.mapped_count == 2
    dart_row = _fetch_source_row(db_path, "DART", "00126380")
    kis_row = _fetch_source_row(db_path, "KIS", "005930")

    assert dart_row["company_id"] == kis_row["company_id"]
    assert dart_row["mapping_source"] == "STOCK_CODE_EXACT"
    assert kis_row["mapping_source"] == "STOCK_CODE_EXACT"


def test_normalized_name_match(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    service.sync_dart(
        [
            _DartRecord(
                corp_code="00999999",
                corp_name="주식회사 카카오",
                corp_eng_name="Kakao Corp",
                stock_code=None,
                modify_date="20260101",
                source_url="https://opendart.fss.or.kr/api/corpCode.xml",
            )
        ]
    )
    service.sync_kis(
        [
            _KisRecord(
                symbol="035720",
                name="카카오",
                market="KOSPI",
                listing_status="LISTED",
                market_classification="ST",
                source_url="/tmp/kis.csv",
            )
        ]
    )
    service.build_mapping()

    dart_row = _fetch_source_row(db_path, "DART", "00999999")
    kis_row = _fetch_source_row(db_path, "KIS", "035720")

    assert dart_row["company_id"] == kis_row["company_id"]
    assert dart_row["mapping_source"] == "NORMALIZED_NAME"


def test_ambiguous_name_collision(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    service.sync_dart(
        [
            _DartRecord(
                corp_code="00888888",
                corp_name="에코",
                corp_eng_name=None,
                stock_code=None,
                modify_date="20260101",
                source_url="https://opendart.fss.or.kr/api/corpCode.xml",
            )
        ]
    )
    service.sync_kis(
        [
            _KisRecord(
                symbol="111111",
                name="에코",
                market="KOSDAQ",
                listing_status="LISTED",
                market_classification="KSQ",
                source_url="/tmp/kis.csv",
            ),
            _KisRecord(
                symbol="222222",
                name="에코",
                market="KOSDAQ",
                listing_status="LISTED",
                market_classification="KSQ",
                source_url="/tmp/kis.csv",
            ),
        ]
    )
    service.build_mapping()

    dart_row = _fetch_source_row(db_path, "DART", "00888888")
    kis_row_a = _fetch_source_row(db_path, "KIS", "111111")
    kis_row_b = _fetch_source_row(db_path, "KIS", "222222")

    assert dart_row["mapping_status"] == "CONFLICT"
    assert kis_row_a["mapping_status"] == "CONFLICT"
    assert kis_row_b["mapping_status"] == "CONFLICT"
    assert dart_row["needs_review"] == 1


def test_manual_override_precedence(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    service.sync_dart(
        [
            _DartRecord(
                corp_code="00777777",
                corp_name="에코",
                corp_eng_name=None,
                stock_code=None,
                modify_date="20260101",
                source_url="https://opendart.fss.or.kr/api/corpCode.xml",
            )
        ]
    )
    service.sync_kis(
        [
            _KisRecord(
                symbol="333333",
                name="에코",
                market="KOSDAQ",
                listing_status="LISTED",
                market_classification="KSQ",
                source_url="/tmp/kis.csv",
            ),
            _KisRecord(
                symbol="444444",
                name="에코",
                market="KOSDAQ",
                listing_status="LISTED",
                market_classification="KSQ",
                source_url="/tmp/kis.csv",
            ),
        ]
    )

    now = utcnow_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO company_manual_overrides (
                source_system,
                source_record_id,
                force_canonical_key,
                force_canonical_name,
                action,
                note,
                created_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DART",
                "00777777",
                "manual:eco-picked",
                "에코(수동)",
                "MAP",
                "pick canonical",
                "tester",
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO company_manual_overrides (
                source_system,
                source_record_id,
                force_canonical_key,
                force_canonical_name,
                action,
                note,
                created_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "KIS",
                "333333",
                "manual:eco-picked",
                "에코(수동)",
                "MAP",
                "pick same canonical",
                "tester",
                now,
                now,
            ),
        )

    service.build_mapping()

    dart_row = _fetch_source_row(db_path, "DART", "00777777")
    kis_row_selected = _fetch_source_row(db_path, "KIS", "333333")
    kis_row_other = _fetch_source_row(db_path, "KIS", "444444")

    assert dart_row["mapping_source"] == "MANUAL_OVERRIDE"
    assert kis_row_selected["mapping_source"] == "MANUAL_OVERRIDE"
    assert dart_row["company_id"] == kis_row_selected["company_id"]
    assert kis_row_other["company_id"] != kis_row_selected["company_id"]


def test_idempotent_rerun(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    dart_records = [
        _DartRecord(
            corp_code="00666666",
            corp_name="네이버",
            corp_eng_name="NAVER",
            stock_code="035420",
            modify_date="20260101",
            source_url="https://opendart.fss.or.kr/api/corpCode.xml",
        )
    ]
    kis_records = [
        _KisRecord(
            symbol="035420",
            name="NAVER",
            market="KOSPI",
            listing_status="LISTED",
            market_classification="ST",
            source_url="/tmp/kis.csv",
        )
    ]

    service.sync_dart(dart_records)
    service.sync_kis(kis_records)
    service.build_mapping()

    with get_connection(db_path) as connection:
        first_company_count = connection.execute(
            "SELECT COUNT(*) AS count FROM companies"
        ).fetchone()["count"]
        first_mapping_count = connection.execute(
            "SELECT COUNT(*) AS count FROM company_source_mappings"
        ).fetchone()["count"]

    service.sync_dart(dart_records)
    service.sync_kis(kis_records)
    service.build_mapping()

    with get_connection(db_path) as connection:
        second_company_count = connection.execute(
            "SELECT COUNT(*) AS count FROM companies"
        ).fetchone()["count"]
        second_mapping_count = connection.execute(
            "SELECT COUNT(*) AS count FROM company_source_mappings"
        ).fetchone()["count"]

    assert first_company_count == second_company_count == 1
    assert first_mapping_count == second_mapping_count == 2


def test_happy_path_integration_with_providers(tmp_path: Path) -> None:
    service, db_path = _make_service(tmp_path)

    xml_payload = """
    <result>
      <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <corp_eng_name>Samsung Electronics</corp_eng_name>
        <stock_code>005930</stock_code>
        <modify_date>20260101</modify_date>
      </list>
      <list>
        <corp_code>00164742</corp_code>
        <corp_name>SK하이닉스</corp_name>
        <corp_eng_name>SK hynix</corp_eng_name>
        <stock_code>000660</stock_code>
        <modify_date>20260101</modify_date>
      </list>
    </result>
    """.strip()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("CORPCODE.xml", xml_payload)

    def _dart_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, content=buffer.getvalue())

    dart_http_client = httpx.Client(transport=httpx.MockTransport(_dart_handler))
    dart_client = DartClient(
        api_key="dummy",
        corp_code_url="https://opendart.fss.or.kr/api/corpCode.xml",
        http_client=dart_http_client,
    )

    kis_csv_path = tmp_path / "kis_master.csv"
    kis_csv_path.write_text(
        "symbol,name,market,listing_status,market_classification\n"
        "005930,삼성전자,KOSPI,LISTED,ST\n"
        "000660,SK하이닉스,KOSPI,LISTED,ST\n",
        encoding="utf-8",
    )
    kis_client = KisFileMasterClient(file_path=str(kis_csv_path))

    try:
        service.sync_dart(dart_client.fetch_company_master())
        service.sync_kis(kis_client.fetch_company_master())
        merge_result = service.build_mapping()
    finally:
        dart_http_client.close()

    assert merge_result.mapped_count == 4
    assert merge_result.unresolved_count == 0

    summary = service.get_mapping_summary(recent_limit=5)
    assert summary["total_mapped"] == 4
    assert summary["unresolved"] == 0

    with get_connection(db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) AS count FROM sync_runs").fetchone()["count"]

    assert run_count >= 3


def test_kis_api_payload_variant_output1(tmp_path: Path) -> None:
    _service, _db_path = _make_service(tmp_path)

    payload = {
        "rt_cd": "0",
        "output1": [
            {
                "pdno": "005930",
                "hts_kor_isnm": "삼성전자",
                "rprs_mrkt_kor_name": "KOSPI",
                "list_yn": "Y",
                "scty_grp_cls_code": "ST",
            }
        ],
    }

    def _kis_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    kis_http_client = httpx.Client(transport=httpx.MockTransport(_kis_handler))
    client = KisApiMasterClient(
        base_url="https://openapi.koreainvestment.com:9443",
        symbol_master_path="/master",
        app_key="key",
        app_secret="secret",
        access_token="token",
        http_client=kis_http_client,
    )
    try:
        records = client.fetch_company_master()
    finally:
        kis_http_client.close()

    assert len(records) == 1
    assert records[0].symbol == "005930"
    assert records[0].name == "삼성전자"
    assert records[0].listing_status == "LISTED"


def test_kis_api_payload_variant_nested_data_items(tmp_path: Path) -> None:
    _service, _db_path = _make_service(tmp_path)

    payload = {
        "data": {
            "items": [
                {
                    "srtn_cd": "000660",
                    "isu_abbrv": "SK하이닉스",
                    "exchange": "KOSPI",
                    "status": "delisted",
                    "classification": "ST",
                }
            ]
        }
    }

    def _kis_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    kis_http_client = httpx.Client(transport=httpx.MockTransport(_kis_handler))
    client = KisApiMasterClient(
        base_url="https://openapi.koreainvestment.com:9443",
        symbol_master_path="/master",
        app_key="key",
        app_secret="secret",
        access_token="token",
        http_client=kis_http_client,
    )
    try:
        records = client.fetch_company_master()
    finally:
        kis_http_client.close()

    assert len(records) == 1
    assert records[0].symbol == "000660"
    assert records[0].name == "SK하이닉스"
    assert records[0].listing_status == "DELISTED"


def test_manual_override_crud_methods(tmp_path: Path) -> None:
    service, _db_path = _make_service(tmp_path)

    inserted = service.upsert_manual_override(
        source_system="DART",
        source_record_id="00126380",
        action="MAP",
        force_canonical_key="manual:samsung",
        force_canonical_name="삼성전자",
        note="ops",
        created_by="tester",
    )
    assert inserted["source_system"] == "DART"
    assert inserted["action"] == "MAP"

    overrides = service.list_manual_overrides(limit=10)
    assert any(row["source_record_id"] == "00126380" for row in overrides)

    deleted = service.delete_manual_override(
        source_system="DART",
        source_record_id="00126380",
    )
    assert deleted is True
    assert service.delete_manual_override(source_system="DART", source_record_id="00126380") is False
