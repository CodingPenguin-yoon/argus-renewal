from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

from ...config.env import get_settings
from .providers import DartClient, create_kis_master_client
from .service import CompanyMasterService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _build_service() -> CompanyMasterService:
    settings = get_settings()
    return CompanyMasterService(db_path=settings.db_path)


def _sync_dart() -> None:
    settings = get_settings()
    if not settings.dart_sync_enabled:
        raise SystemExit("DART sync is disabled. Set DART_SYNC_ENABLED=true")
    if not settings.dart_api_key:
        raise SystemExit("DART_API_KEY is required")

    service = _build_service()
    client = DartClient(
        api_key=settings.dart_api_key,
        corp_code_url=settings.dart_corp_code_url,
    )
    records = client.fetch_company_master()
    result = service.sync_dart(records)
    _print_json(
        {
            "run_id": result.run_id,
            "status": result.status,
            "processed_count": result.processed_count,
            "inserted_count": result.inserted_count,
            "updated_count": result.updated_count,
            "failed_count": result.failed_count,
        }
    )


def _sync_kis() -> None:
    settings = get_settings()
    if settings.kis_master_provider.strip().lower() == "disabled":
        raise SystemExit("KIS sync is disabled. Set KIS_MASTER_PROVIDER=file or api")

    service = _build_service()
    client = create_kis_master_client(
        provider=settings.kis_master_provider,
        file_path=settings.kis_master_file_path,
        base_url=settings.kis_base_url,
        symbol_master_path=settings.kis_symbol_master_path,
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        access_token=settings.kis_access_token,
        response_paths=settings.kis_symbol_master_response_paths,
        query_params_json=settings.kis_symbol_master_query_params_json,
        tr_id=settings.kis_symbol_master_tr_id,
    )
    records = client.fetch_company_master()
    result = service.sync_kis(records)
    _print_json(
        {
            "run_id": result.run_id,
            "status": result.status,
            "processed_count": result.processed_count,
            "inserted_count": result.inserted_count,
            "updated_count": result.updated_count,
            "failed_count": result.failed_count,
        }
    )


def _build_mapping() -> None:
    service = _build_service()
    result = service.build_mapping()
    _print_json(
        {
            "run_id": result.run_id,
            "status": result.status,
            "processed_count": result.processed_count,
            "mapped_count": result.mapped_count,
            "unresolved_count": result.unresolved_count,
            "conflict_count": result.conflict_count,
            "created_company_count": result.created_company_count,
        }
    )


def _export_unresolved(output_path: str) -> None:
    service = _build_service()
    row_count = service.export_unresolved_mappings(output_path)
    _print_json({"output_path": output_path, "row_count": row_count})


def _summary(recent_limit: int) -> None:
    service = _build_service()
    _print_json(service.get_mapping_summary(recent_limit=recent_limit))


def _list_unresolved(limit: int) -> None:
    service = _build_service()
    rows = service.get_unresolved_mappings(limit=limit)
    _print_json({"count": len(rows), "items": rows})


def _add_manual_override(args: argparse.Namespace) -> None:
    service = _build_service()
    row = service.upsert_manual_override(
        source_system=args.source_system,
        source_record_id=args.source_record_id,
        action=args.action,
        target_company_id=args.target_company_id,
        force_canonical_key=args.force_canonical_key,
        force_canonical_name=args.force_canonical_name,
        note=args.note,
        created_by=args.created_by,
    )
    _print_json({"updated": True, "item": row})


def _list_manual_overrides(limit: int) -> None:
    service = _build_service()
    rows = service.list_manual_overrides(limit=limit)
    _print_json({"count": len(rows), "items": rows})


def _remove_manual_override(source_system: str, source_record_id: str) -> None:
    service = _build_service()
    deleted = service.delete_manual_override(
        source_system=source_system,
        source_record_id=source_record_id,
    )
    _print_json(
        {
            "deleted": deleted,
            "source_system": source_system.upper().strip(),
            "source_record_id": source_record_id,
        }
    )


def _import_manual_overrides(input_path: str, created_by: str) -> None:
    source = Path(input_path)
    if not source.exists():
        raise SystemExit(f"Override CSV not found: {source}")

    service = _build_service()
    inserted_or_updated = 0
    skipped = 0
    failures: list[dict[str, Any]] = []

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"source_system", "source_record_id", "action"}
        if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
            raise SystemExit(
                "CSV must include columns: source_system, source_record_id, action"
            )

        for row in reader:
            source_system = (row.get("source_system") or "").strip()
            source_record_id = (row.get("source_record_id") or "").strip()
            action = (row.get("action") or "").strip()
            if not source_system or not source_record_id or not action:
                skipped += 1
                continue

            target_company_id: int | None = None
            raw_target_company_id = (row.get("target_company_id") or "").strip()
            if raw_target_company_id:
                try:
                    target_company_id = int(raw_target_company_id)
                except ValueError:
                    failures.append(
                        {
                            "source_system": source_system,
                            "source_record_id": source_record_id,
                            "error": f"invalid target_company_id: {raw_target_company_id}",
                        }
                    )
                    continue

            try:
                service.upsert_manual_override(
                    source_system=source_system,
                    source_record_id=source_record_id,
                    action=action,
                    target_company_id=target_company_id,
                    force_canonical_key=(row.get("force_canonical_key") or "").strip() or None,
                    force_canonical_name=(row.get("force_canonical_name") or "").strip() or None,
                    note=(row.get("note") or "").strip() or None,
                    created_by=(row.get("created_by") or "").strip() or created_by,
                )
                inserted_or_updated += 1
            except Exception as error:  # noqa: BLE001
                failures.append(
                    {
                        "source_system": source_system,
                        "source_record_id": source_record_id,
                        "error": str(error),
                    }
                )

    _print_json(
        {
            "input_path": str(source),
            "inserted_or_updated": inserted_or_updated,
            "skipped": skipped,
            "failed": len(failures),
            "failures": failures,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Argus KRX company master jobs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync-dart", help="Sync company master from DART")
    subparsers.add_parser("sync-kis", help="Sync company master from KIS")
    subparsers.add_parser("build-mapping", help="Build canonical company mappings")

    export_parser = subparsers.add_parser(
        "export-unresolved",
        help="Export unresolved/conflicting mappings to CSV",
    )
    export_parser.add_argument("--output", required=True, help="CSV output path")

    summary_parser = subparsers.add_parser("summary", help="Show mapping summary")
    summary_parser.add_argument(
        "--recent-limit",
        type=int,
        default=20,
        help="Number of recent mapping rows to include",
    )

    unresolved_parser = subparsers.add_parser(
        "list-unresolved",
        help="Print unresolved/conflicting mappings as JSON",
    )
    unresolved_parser.add_argument("--limit", type=int, default=200)

    override_parser = subparsers.add_parser(
        "add-manual-override",
        help="Insert or update a manual override row",
    )
    override_parser.add_argument("--source-system", required=True, help="DART or KIS")
    override_parser.add_argument("--source-record-id", required=True, help="corp_code or symbol")
    override_parser.add_argument("--action", required=True, help="MAP, SKIP, REVIEW")
    override_parser.add_argument("--target-company-id", type=int)
    override_parser.add_argument("--force-canonical-key")
    override_parser.add_argument("--force-canonical-name")
    override_parser.add_argument("--note")
    override_parser.add_argument("--created-by", default="operator")

    list_override_parser = subparsers.add_parser(
        "list-manual-overrides",
        help="List existing manual overrides",
    )
    list_override_parser.add_argument("--limit", type=int, default=200)

    remove_override_parser = subparsers.add_parser(
        "remove-manual-override",
        help="Delete a manual override",
    )
    remove_override_parser.add_argument("--source-system", required=True, help="DART or KIS")
    remove_override_parser.add_argument("--source-record-id", required=True, help="corp_code or symbol")

    import_override_parser = subparsers.add_parser(
        "import-manual-overrides",
        help="Bulk import manual overrides from CSV",
    )
    import_override_parser.add_argument("--input", required=True, help="CSV path")
    import_override_parser.add_argument("--created-by", default="operator")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sync-dart":
        _sync_dart()
        return

    if args.command == "sync-kis":
        _sync_kis()
        return

    if args.command == "build-mapping":
        _build_mapping()
        return

    if args.command == "export-unresolved":
        _export_unresolved(args.output)
        return

    if args.command == "summary":
        _summary(args.recent_limit)
        return

    if args.command == "list-unresolved":
        _list_unresolved(args.limit)
        return

    if args.command == "add-manual-override":
        _add_manual_override(args)
        return

    if args.command == "list-manual-overrides":
        _list_manual_overrides(args.limit)
        return

    if args.command == "remove-manual-override":
        _remove_manual_override(args.source_system, args.source_record_id)
        return

    if args.command == "import-manual-overrides":
        _import_manual_overrides(args.input, args.created_by)
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
