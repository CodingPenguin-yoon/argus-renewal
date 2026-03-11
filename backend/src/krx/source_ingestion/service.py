from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import json
import logging
from typing import Any

from ..company_master.db import get_connection, utcnow_iso
from .models import RawDocumentCandidate
from .normalize import canonicalize_url, dart_dedup_key, news_dedup_key, title_hash
from .providers import BigKindsNewsProvider, DartDisclosureProvider, NaverNewsProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionRunResult:
    run_id: int
    status: str
    provider: str
    source_kind: str
    source_key: str | None
    processed_count: int
    inserted_count: int
    duplicate_count: int
    failed_count: int
    cursor_before: str | None
    cursor_after: str | None
    error_message: str | None = None


class RawDocumentIngestionService:
    def __init__(
        self,
        *,
        db_path: str,
        dart_provider: DartDisclosureProvider,
        bigkinds_provider: BigKindsNewsProvider,
        naver_provider: NaverNewsProvider,
    ) -> None:
        self.db_path = db_path
        self.dart_provider = dart_provider
        self.bigkinds_provider = bigkinds_provider
        self.naver_provider = naver_provider

    def sync_dart_disclosures_last_days(self, *, days: int, backfill: bool = False) -> IngestionRunResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_dart_disclosures_window(
            window_start=window_start,
            window_end=now,
            backfill=backfill,
        )

    def sync_dart_disclosures_window(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
    ) -> IngestionRunResult:
        mode = "BACKFILL" if backfill else "INCREMENTAL"

        with get_connection(self.db_path) as connection:
            source = self._ensure_source(
                connection,
                provider="DART",
                source_kind="SYSTEM",
                source_key="DISCLOSURES",
                source_label="DART disclosures",
                query_template=None,
            )

            cursor_before = None if backfill else source.get("last_cursor")
            run_id = self._start_fetch_run(
                connection,
                job_name="raw_documents_sync_dart",
                provider="DART",
                mode=mode,
                source_kind="SYSTEM",
                source_key="DISCLOSURES",
                query_text=None,
                window_start=window_start,
                window_end=window_end,
                cursor_before=cursor_before,
                metadata={"source_id": source["id"]},
            )

            processed_count = 0
            inserted_count = 0
            duplicate_count = 0
            failed_count = 0
            cursor_after = cursor_before

            try:
                batch = self.dart_provider.fetch_disclosures(
                    window_start=window_start,
                    window_end=window_end,
                    cursor=cursor_before,
                )

                if batch.disabled_reason:
                    self._finish_fetch_run(
                        connection,
                        run_id=run_id,
                        status="SKIPPED_DISABLED",
                        processed_count=0,
                        inserted_count=0,
                        duplicate_count=0,
                        failed_count=0,
                        cursor_after=cursor_before,
                        metadata={"disabled_reason": batch.disabled_reason},
                        error_message=None,
                    )
                    return IngestionRunResult(
                        run_id=run_id,
                        status="SKIPPED_DISABLED",
                        provider="DART",
                        source_kind="SYSTEM",
                        source_key="DISCLOSURES",
                        processed_count=0,
                        inserted_count=0,
                        duplicate_count=0,
                        failed_count=0,
                        cursor_before=cursor_before,
                        cursor_after=cursor_before,
                    )

                for record in batch.records:
                    processed_count += 1
                    try:
                        resolved = self._resolve_dart_company_reference(connection, record)
                        inserted, is_duplicate = self._upsert_raw_document(
                            connection,
                            candidate=resolved,
                            run_id=run_id,
                        )
                        inserted_count += int(inserted)
                        duplicate_count += int(is_duplicate)
                    except Exception as error:  # noqa: BLE001
                        failed_count += 1
                        logger.exception(
                            "dart_ingestion_record_failed",
                            extra={
                                "run_id": run_id,
                                "provider_document_id": record.provider_document_id,
                                "error": str(error),
                            },
                        )

                cursor_after = batch.next_cursor or cursor_before
                self._finish_fetch_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_after=cursor_after,
                    metadata=batch.metadata,
                    error_message=None,
                )

                if not backfill and cursor_after is not None:
                    self._update_source_success_cursor(
                        connection,
                        source_id=source["id"],
                        cursor=cursor_after,
                        run_id=run_id,
                    )

                return IngestionRunResult(
                    run_id=run_id,
                    status="SUCCESS",
                    provider="DART",
                    source_kind="SYSTEM",
                    source_key="DISCLOSURES",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_before=cursor_before,
                    cursor_after=cursor_after,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_fetch_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_after=cursor_after,
                    metadata=None,
                    error_message=str(error),
                )
                return IngestionRunResult(
                    run_id=run_id,
                    status="FAILED",
                    provider="DART",
                    source_kind="SYSTEM",
                    source_key="DISCLOSURES",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_before=cursor_before,
                    cursor_after=cursor_after,
                    error_message=str(error),
                )

    def sync_news_candidates_for_companies_last_days(
        self,
        *,
        company_ids: list[int],
        company_names: list[str] | None,
        days: int,
        backfill: bool = False,
    ) -> list[IngestionRunResult]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_news_candidates_for_companies_window(
            company_ids=company_ids,
            company_names=company_names,
            window_start=window_start,
            window_end=now,
            backfill=backfill,
        )

    def sync_news_candidates_for_companies_window(
        self,
        *,
        company_ids: list[int],
        company_names: list[str] | None,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
    ) -> list[IngestionRunResult]:
        targets = self._load_company_targets(company_ids=company_ids, company_names=company_names or [])
        results: list[IngestionRunResult] = []

        for target in targets:
            company_id = target["company_id"]
            company_name = target["name"]
            source_suffix = target["source_key"]

            results.append(
                self._sync_news_query(
                    provider="BIGKINDS",
                    source_kind="COMPANY",
                    source_key=f"{source_suffix}:company",
                    source_label=company_name,
                    query_template="{company_name}",
                    query_text=company_name,
                    window_start=window_start,
                    window_end=window_end,
                    backfill=backfill,
                    company_id=company_id,
                )
            )

            company_query = self.naver_provider.build_company_query(company_name=company_name)
            results.append(
                self._sync_news_query(
                    provider="NAVER_NEWS",
                    source_kind="COMPANY",
                    source_key=f"{source_suffix}:company",
                    source_label=company_name,
                    query_template=self.naver_provider.company_query_template,
                    query_text=company_query,
                    window_start=window_start,
                    window_end=window_end,
                    backfill=backfill,
                    company_id=company_id,
                )
            )

            sector_keyword = target.get("sector_keyword")
            if sector_keyword:
                sector_query = self.naver_provider.build_theme_query(keyword=sector_keyword)
                results.append(
                    self._sync_news_query(
                        provider="NAVER_NEWS",
                        source_kind="COMPANY",
                        source_key=f"{source_suffix}:sector:{sector_keyword}",
                        source_label=f"{company_name}:{sector_keyword}",
                        query_template=self.naver_provider.theme_query_template,
                        query_text=sector_query,
                        window_start=window_start,
                        window_end=window_end,
                        backfill=backfill,
                        company_id=company_id,
                    )
                )

        return results

    def sync_news_candidates_for_themes_last_days(
        self,
        *,
        keywords: list[str],
        days: int,
        backfill: bool = False,
    ) -> list[IngestionRunResult]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_news_candidates_for_themes_window(
            keywords=keywords,
            window_start=window_start,
            window_end=now,
            backfill=backfill,
        )

    def sync_news_candidates_for_themes_window(
        self,
        *,
        keywords: list[str],
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
    ) -> list[IngestionRunResult]:
        normalized_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
        results: list[IngestionRunResult] = []

        for keyword in normalized_keywords:
            results.append(
                self._sync_news_query(
                    provider="BIGKINDS",
                    source_kind="THEME",
                    source_key=keyword,
                    source_label=keyword,
                    query_template="{keyword}",
                    query_text=keyword,
                    window_start=window_start,
                    window_end=window_end,
                    backfill=backfill,
                    company_id=None,
                )
            )

            theme_query = self.naver_provider.build_theme_query(keyword=keyword)
            results.append(
                self._sync_news_query(
                    provider="NAVER_NEWS",
                    source_kind="THEME",
                    source_key=keyword,
                    source_label=keyword,
                    query_template=self.naver_provider.theme_query_template,
                    query_text=theme_query,
                    window_start=window_start,
                    window_end=window_end,
                    backfill=backfill,
                    company_id=None,
                )
            )

        return results

    def backfill_by_date_range(
        self,
        *,
        start_date: date,
        end_date: date,
        include_dart: bool,
        include_news: bool,
        company_ids: list[int],
        company_names: list[str],
        keywords: list[str],
    ) -> list[IngestionRunResult]:
        window_start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        window_end = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        results: list[IngestionRunResult] = []
        if include_dart:
            results.append(
                self.sync_dart_disclosures_window(
                    window_start=window_start,
                    window_end=window_end,
                    backfill=True,
                )
            )

        if include_news:
            if company_ids or company_names:
                results.extend(
                    self.sync_news_candidates_for_companies_window(
                        company_ids=company_ids,
                        company_names=company_names,
                        window_start=window_start,
                        window_end=window_end,
                        backfill=True,
                    )
                )
            if keywords:
                results.extend(
                    self.sync_news_candidates_for_themes_window(
                        keywords=keywords,
                        window_start=window_start,
                        window_end=window_end,
                        backfill=True,
                    )
                )

        return results

    def list_raw_documents(
        self,
        *,
        limit: int,
        provider: str | None,
        include_duplicates: bool,
    ) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            filters = []
            params: list[Any] = []

            if provider:
                filters.append("rd.provider = ?")
                params.append(provider)
            if not include_duplicates:
                filters.append("rd.is_duplicate = 0")

            where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
            params.append(limit)

            rows = connection.execute(
                f"""
                SELECT
                    rd.*,
                    c.canonical_name AS company_name
                FROM raw_documents rd
                LEFT JOIN companies c ON c.id = rd.company_id
                {where_clause}
                ORDER BY rd.created_at DESC, rd.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        documents: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["provider_metadata"] = self._json_load(payload.pop("provider_metadata_json", None))
            payload["raw_payload"] = self._json_load(payload.pop("raw_payload_json", None))
            documents.append(payload)

        return documents

    def list_fetch_runs(self, *, limit: int, provider: str | None) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            if provider:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM raw_document_fetch_runs
                    WHERE provider = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (provider, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM raw_document_fetch_runs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = self._json_load(payload.pop("metadata_json", None))
            results.append(payload)
        return results

    def _sync_news_query(
        self,
        *,
        provider: str,
        source_kind: str,
        source_key: str,
        source_label: str,
        query_template: str,
        query_text: str,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
        company_id: int | None,
    ) -> IngestionRunResult:
        mode = "BACKFILL" if backfill else "INCREMENTAL"
        provider_client = self._select_news_provider(provider)

        with get_connection(self.db_path) as connection:
            source = self._ensure_source(
                connection,
                provider=provider,
                source_kind=source_kind,
                source_key=source_key,
                source_label=source_label,
                query_template=query_template,
            )

            cursor_before = None if backfill else source.get("last_cursor")
            run_id = self._start_fetch_run(
                connection,
                job_name="raw_documents_sync_news",
                provider=provider,
                mode=mode,
                source_kind=source_kind,
                source_key=source_key,
                query_text=query_text,
                window_start=window_start,
                window_end=window_end,
                cursor_before=cursor_before,
                metadata={"source_id": source["id"], "source_label": source_label},
            )

            processed_count = 0
            inserted_count = 0
            duplicate_count = 0
            failed_count = 0
            cursor_after = cursor_before

            try:
                batch = provider_client.fetch_news(
                    query=query_text,
                    window_start=window_start,
                    window_end=window_end,
                    cursor=cursor_before,
                )

                if batch.disabled_reason:
                    self._finish_fetch_run(
                        connection,
                        run_id=run_id,
                        status="SKIPPED_DISABLED",
                        processed_count=0,
                        inserted_count=0,
                        duplicate_count=0,
                        failed_count=0,
                        cursor_after=cursor_before,
                        metadata={"disabled_reason": batch.disabled_reason, "query": query_text},
                        error_message=None,
                    )
                    return IngestionRunResult(
                        run_id=run_id,
                        status="SKIPPED_DISABLED",
                        provider=provider,
                        source_kind=source_kind,
                        source_key=source_key,
                        processed_count=0,
                        inserted_count=0,
                        duplicate_count=0,
                        failed_count=0,
                        cursor_before=cursor_before,
                        cursor_after=cursor_before,
                    )

                for record in batch.records:
                    processed_count += 1
                    try:
                        resolved_record = record
                        if company_id is not None and record.company_id is None:
                            resolved_record = replace(record, company_id=company_id)

                        inserted, is_duplicate = self._upsert_raw_document(
                            connection,
                            candidate=resolved_record,
                            run_id=run_id,
                        )
                        inserted_count += int(inserted)
                        duplicate_count += int(is_duplicate)
                    except Exception as error:  # noqa: BLE001
                        failed_count += 1
                        logger.exception(
                            "news_ingestion_record_failed",
                            extra={
                                "run_id": run_id,
                                "provider": provider,
                                "source_key": source_key,
                                "error": str(error),
                            },
                        )

                cursor_after = batch.next_cursor or cursor_before
                self._finish_fetch_run(
                    connection,
                    run_id=run_id,
                    status="SUCCESS",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_after=cursor_after,
                    metadata=batch.metadata,
                    error_message=None,
                )

                if not backfill and cursor_after is not None:
                    self._update_source_success_cursor(
                        connection,
                        source_id=source["id"],
                        cursor=cursor_after,
                        run_id=run_id,
                    )

                return IngestionRunResult(
                    run_id=run_id,
                    status="SUCCESS",
                    provider=provider,
                    source_kind=source_kind,
                    source_key=source_key,
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_before=cursor_before,
                    cursor_after=cursor_after,
                )
            except Exception as error:  # noqa: BLE001
                self._finish_fetch_run(
                    connection,
                    run_id=run_id,
                    status="FAILED",
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_after=cursor_after,
                    metadata=None,
                    error_message=str(error),
                )
                return IngestionRunResult(
                    run_id=run_id,
                    status="FAILED",
                    provider=provider,
                    source_kind=source_kind,
                    source_key=source_key,
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_before=cursor_before,
                    cursor_after=cursor_after,
                    error_message=str(error),
                )

    def _resolve_dart_company_reference(
        self,
        connection,
        candidate: RawDocumentCandidate,
    ) -> RawDocumentCandidate:
        corp_code = str(candidate.provider_metadata.get("corp_code") or "").strip() or None
        if corp_code is None:
            return candidate

        row = connection.execute(
            """
            SELECT company_id
            FROM company_source_mappings
            WHERE source_system = 'DART' AND source_record_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (corp_code,),
        ).fetchone()

        company_id = int(row["company_id"]) if row and row["company_id"] is not None else None
        if company_id is None:
            return candidate

        return replace(candidate, company_id=company_id)

    def _upsert_raw_document(
        self,
        connection,
        *,
        candidate: RawDocumentCandidate,
        run_id: int,
    ) -> tuple[bool, bool]:
        now = utcnow_iso()
        normalized_title_hash = title_hash(candidate.title)
        canonical_url = canonicalize_url(candidate.canonical_url or candidate.source_url)

        metadata_json = json.dumps(candidate.provider_metadata, ensure_ascii=False, sort_keys=True)
        payload_json = (
            json.dumps(candidate.raw_payload, ensure_ascii=False, sort_keys=True)
            if candidate.raw_payload is not None
            else None
        )

        existing = None
        if candidate.provider_document_id:
            existing = connection.execute(
                """
                SELECT *
                FROM raw_documents
                WHERE provider = ? AND provider_document_id = ?
                """,
                (candidate.provider, candidate.provider_document_id),
            ).fetchone()
        elif canonical_url and normalized_title_hash:
            existing = connection.execute(
                """
                SELECT *
                FROM raw_documents
                WHERE provider = ? AND canonical_url = ? AND normalized_title_hash = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (candidate.provider, canonical_url, normalized_title_hash),
            ).fetchone()

        if existing is None:
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.provider,
                    candidate.provider_document_id,
                    candidate.document_type,
                    candidate.title,
                    candidate.summary,
                    candidate.publisher,
                    candidate.source_url,
                    canonical_url,
                    candidate.published_at,
                    candidate.receipt_at,
                    candidate.report_type,
                    candidate.company_id,
                    candidate.company_ref,
                    candidate.query_text,
                    normalized_title_hash,
                    run_id,
                    run_id,
                    metadata_json,
                    payload_json,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
            document_id = int(row["id"])
            inserted = True
        else:
            document_id = int(existing["id"])
            company_id = candidate.company_id or existing["company_id"]
            connection.execute(
                """
                UPDATE raw_documents
                SET
                    title = ?,
                    summary = ?,
                    publisher = ?,
                    source_url = ?,
                    canonical_url = ?,
                    published_at = ?,
                    receipt_at = ?,
                    report_type = ?,
                    company_id = ?,
                    company_ref = ?,
                    query_text = ?,
                    normalized_title_hash = ?,
                    last_seen_run_id = ?,
                    provider_metadata_json = ?,
                    raw_payload_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    candidate.title,
                    candidate.summary,
                    candidate.publisher,
                    candidate.source_url,
                    canonical_url,
                    candidate.published_at,
                    candidate.receipt_at,
                    candidate.report_type,
                    company_id,
                    candidate.company_ref,
                    candidate.query_text,
                    normalized_title_hash,
                    run_id,
                    metadata_json,
                    payload_json,
                    now,
                    document_id,
                ),
            )
            inserted = False

        dedup_type = candidate.dedup_type
        dedup_key = candidate.dedup_key

        if dedup_type is None:
            if candidate.provider == "DART":
                dedup_type = "PROVIDER_ID"
                dedup_key = dart_dedup_key(candidate.provider_document_id)
            elif candidate.document_type == "NEWS_CANDIDATE":
                dedup_type = "NEWS_URL_TITLE"
                dedup_key = news_dedup_key(
                    canonical_url=canonical_url,
                    normalized_title_hash=normalized_title_hash,
                )

        is_duplicate = False
        if dedup_type and dedup_key:
            is_duplicate = self._apply_dedup_key(
                connection,
                provider=candidate.provider,
                dedup_type=dedup_type,
                dedup_key=dedup_key,
                document_id=document_id,
            )

        return inserted, is_duplicate

    def _apply_dedup_key(
        self,
        connection,
        *,
        provider: str,
        dedup_type: str,
        dedup_key: str,
        document_id: int,
    ) -> bool:
        now = utcnow_iso()
        primary_row = connection.execute(
            """
            SELECT primary_document_id
            FROM raw_document_dedup_keys
            WHERE dedup_type = ? AND dedup_key = ? AND is_primary = 1
            ORDER BY id ASC
            LIMIT 1
            """,
            (dedup_type, dedup_key),
        ).fetchone()

        if primary_row is None:
            connection.execute(
                """
                INSERT OR IGNORE INTO raw_document_dedup_keys (
                    dedup_type,
                    dedup_key,
                    provider,
                    document_id,
                    primary_document_id,
                    is_primary,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (dedup_type, dedup_key, provider, document_id, document_id, now),
            )
            connection.execute(
                """
                UPDATE raw_documents
                SET
                    is_duplicate = 0,
                    duplicate_of_document_id = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, document_id),
            )
            return False

        primary_document_id = int(primary_row["primary_document_id"])

        if primary_document_id == document_id:
            connection.execute(
                """
                INSERT OR IGNORE INTO raw_document_dedup_keys (
                    dedup_type,
                    dedup_key,
                    provider,
                    document_id,
                    primary_document_id,
                    is_primary,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (dedup_type, dedup_key, provider, document_id, document_id, now),
            )
            connection.execute(
                """
                UPDATE raw_documents
                SET
                    is_duplicate = 0,
                    duplicate_of_document_id = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, document_id),
            )
            return False

        connection.execute(
            """
            INSERT OR IGNORE INTO raw_document_dedup_keys (
                dedup_type,
                dedup_key,
                provider,
                document_id,
                primary_document_id,
                is_primary,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (dedup_type, dedup_key, provider, document_id, primary_document_id, now),
        )
        connection.execute(
            """
            UPDATE raw_documents
            SET
                is_duplicate = 1,
                duplicate_of_document_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (primary_document_id, now, document_id),
        )
        return True

    def _ensure_source(
        self,
        connection,
        *,
        provider: str,
        source_kind: str,
        source_key: str,
        source_label: str | None,
        query_template: str | None,
    ) -> dict[str, Any]:
        existing = connection.execute(
            """
            SELECT *
            FROM raw_document_sources
            WHERE provider = ? AND source_kind = ? AND source_key = ?
            """,
            (provider, source_kind, source_key),
        ).fetchone()

        now = utcnow_iso()
        if existing is not None:
            connection.execute(
                """
                UPDATE raw_document_sources
                SET
                    source_label = ?,
                    query_template = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (source_label, query_template, now, existing["id"]),
            )
            row = connection.execute(
                "SELECT * FROM raw_document_sources WHERE id = ?",
                (existing["id"],),
            ).fetchone()
            assert row is not None
            return dict(row)

        connection.execute(
            """
            INSERT INTO raw_document_sources (
                provider,
                source_kind,
                source_key,
                source_label,
                query_template,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (provider, source_kind, source_key, source_label, query_template, now, now),
        )
        row = connection.execute(
            "SELECT * FROM raw_document_sources WHERE id = last_insert_rowid()"
        ).fetchone()
        assert row is not None
        return dict(row)

    def _update_source_success_cursor(
        self,
        connection,
        *,
        source_id: int,
        cursor: str,
        run_id: int,
    ) -> None:
        now = utcnow_iso()
        connection.execute(
            """
            UPDATE raw_document_sources
            SET
                last_cursor = ?,
                last_success_run_id = ?,
                last_success_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (cursor, run_id, now, now, source_id),
        )

    def _select_news_provider(self, provider: str):
        if provider == "BIGKINDS":
            return self.bigkinds_provider
        if provider == "NAVER_NEWS":
            return self.naver_provider
        raise ValueError(f"Unsupported news provider: {provider}")

    def _load_company_targets(
        self,
        *,
        company_ids: list[int],
        company_names: list[str],
    ) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []

        unique_company_ids = sorted({company_id for company_id in company_ids if company_id > 0})
        if unique_company_ids:
            placeholders = ",".join("?" for _ in unique_company_ids)
            with get_connection(self.db_path) as connection:
                rows = connection.execute(
                    f"""
                    SELECT id, canonical_name, market_classification
                    FROM companies
                    WHERE id IN ({placeholders})
                    """,
                    unique_company_ids,
                ).fetchall()

            row_by_id = {int(row["id"]): dict(row) for row in rows}
            for company_id in unique_company_ids:
                row = row_by_id.get(company_id)
                if row is None:
                    logger.warning(
                        "company_target_missing",
                        extra={"company_id": company_id},
                    )
                    continue

                company_name = str(row.get("canonical_name") or "").strip()
                if not company_name:
                    continue

                targets.append(
                    {
                        "company_id": company_id,
                        "name": company_name,
                        "sector_keyword": str(row.get("market_classification") or "").strip() or None,
                        "source_key": f"id:{company_id}",
                    }
                )

        for company_name in company_names:
            normalized = company_name.strip()
            if not normalized:
                continue
            source_key = f"name:{normalized.casefold().replace(' ', '_')}"
            targets.append(
                {
                    "company_id": None,
                    "name": normalized,
                    "sector_keyword": None,
                    "source_key": source_key,
                }
            )

        deduped: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for target in targets:
            key = f"{target['source_key']}:{target['name']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(target)

        return deduped

    def _start_fetch_run(
        self,
        connection,
        *,
        job_name: str,
        provider: str,
        mode: str,
        source_kind: str,
        source_key: str | None,
        query_text: str | None,
        window_start: datetime,
        window_end: datetime,
        cursor_before: str | None,
        metadata: dict[str, Any] | None,
    ) -> int:
        started_at = utcnow_iso()
        connection.execute(
            """
            INSERT INTO raw_document_fetch_runs (
                job_name,
                provider,
                mode,
                source_kind,
                source_key,
                query_text,
                window_start,
                window_end,
                cursor_before,
                status,
                started_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?, ?)
            """,
            (
                job_name,
                provider,
                mode,
                source_kind,
                source_key,
                query_text,
                window_start.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                window_end.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                cursor_before,
                started_at,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = connection.execute("SELECT last_insert_rowid() AS id").fetchone()
        return int(row["id"])

    def _finish_fetch_run(
        self,
        connection,
        *,
        run_id: int,
        status: str,
        processed_count: int,
        inserted_count: int,
        duplicate_count: int,
        failed_count: int,
        cursor_after: str | None,
        metadata: dict[str, Any] | None,
        error_message: str | None,
    ) -> None:
        connection.execute(
            """
            UPDATE raw_document_fetch_runs
            SET
                status = ?,
                finished_at = ?,
                processed_count = ?,
                inserted_count = ?,
                duplicate_count = ?,
                failed_count = ?,
                cursor_after = ?,
                metadata_json = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                status,
                utcnow_iso(),
                processed_count,
                inserted_count,
                duplicate_count,
                failed_count,
                cursor_after,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                error_message,
                run_id,
            ),
        )

    def _json_load(self, value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
