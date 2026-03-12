from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import json
import logging
from typing import Any

from ..company_master.db import get_connection, utcnow_iso
from ..publisher_registry import ensure_publisher_definition
from ..provider_registry import build_provider_definition, ensure_provider_definition, normalize_provider_key
from .document_time import determine_published_at_source
from .models import RawDocumentCandidate
from .normalize import canonicalize_url, dart_dedup_key, news_dedup_key, title_hash
from .provider_descriptors import (
    DisclosureProviderDescriptor,
    DocumentSyncRequest,
    NewsProviderDescriptor,
)
from .providers import BigKindsNewsProvider, DartDisclosureProvider, MkRssNewsProvider, NaverNewsProvider

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
        mk_rss_provider: MkRssNewsProvider | None = None,
        naver_provider: NaverNewsProvider,
        bigkinds_provider: BigKindsNewsProvider | None = None,
        extra_disclosure_provider_descriptors: tuple[DisclosureProviderDescriptor, ...] = (),
        extra_news_provider_descriptors: tuple[NewsProviderDescriptor, ...] = (),
    ) -> None:
        self.db_path = db_path
        self.dart_provider = dart_provider
        self.mk_rss_provider = mk_rss_provider or MkRssNewsProvider(enabled=False, feed_urls=())
        self.bigkinds_provider = bigkinds_provider
        self.naver_provider = naver_provider
        self.disclosure_provider_descriptors = self._build_disclosure_provider_descriptors(
            extra_disclosure_provider_descriptors
        )
        self.news_provider_descriptors = self._build_news_provider_descriptors(
            extra_news_provider_descriptors
        )

    def _ensure_provider_registered(
        self,
        connection,
        *,
        provider: str,
        document_type: str | None = None,
    ) -> None:
        ensure_provider_definition(
            connection,
            build_provider_definition(
                provider_key=provider,
                document_type=document_type,
            ),
        )

    def _ensure_publisher_registered(
        self,
        connection,
        *,
        publisher: str | None,
        publisher_key: str | None = None,
    ) -> str | None:
        definition = ensure_publisher_definition(
            connection,
            publisher_name=publisher,
            publisher_key=publisher_key,
        )
        if definition is None:
            return None
        return definition.publisher_key

    def _build_disclosure_provider_descriptors(
        self,
        extra_descriptors: tuple[DisclosureProviderDescriptor, ...],
    ) -> dict[str, DisclosureProviderDescriptor]:
        defaults = (
            DisclosureProviderDescriptor(
                provider="DART",
                request=DocumentSyncRequest(
                    job_name="raw_documents_sync_dart",
                    provider="DART",
                    source_kind="SYSTEM",
                    source_key="DISCLOSURES",
                    source_label="DART disclosures",
                    query_template=None,
                    query_text=None,
                ),
                fetch_batch=self._fetch_dart_batch,
                resolve_candidate=self._resolve_dart_company_reference,
            ),
        )
        return {
            descriptor.provider: descriptor
            for descriptor in (*defaults, *extra_descriptors)
        }

    def _build_news_provider_descriptors(
        self,
        extra_descriptors: tuple[NewsProviderDescriptor, ...],
    ) -> dict[str, NewsProviderDescriptor]:
        defaults = (
            NewsProviderDescriptor(
                provider="MK_RSS",
                fetch_batch=self._fetch_mk_rss_batch,
                build_company_requests=self._build_mk_rss_company_requests,
                build_theme_requests=self._build_mk_rss_theme_requests,
            ),
            NewsProviderDescriptor(
                provider="NAVER_NEWS",
                fetch_batch=self._fetch_naver_news_batch,
                build_company_requests=self._build_naver_company_requests,
                build_theme_requests=self._build_naver_theme_requests,
            ),
        )
        return {
            descriptor.provider: descriptor
            for descriptor in (*defaults, *extra_descriptors)
        }

    def _fetch_dart_batch(
        self,
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ):
        return self.dart_provider.fetch_disclosures(
            window_start=window_start,
            window_end=window_end,
            cursor=cursor,
        )

    def _fetch_bigkinds_batch(
        self,
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ):
        if request.query_text is None:
            raise ValueError("BIGKINDS request must include query_text")
        return self.bigkinds_provider.fetch_news(
            query=request.query_text,
            window_start=window_start,
            window_end=window_end,
            cursor=cursor,
        )

    def _fetch_mk_rss_batch(
        self,
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ):
        if request.query_text is None:
            raise ValueError("MK_RSS request must include query_text")
        return self.mk_rss_provider.fetch_news(
            query=request.query_text,
            window_start=window_start,
            window_end=window_end,
            cursor=cursor,
        )

    def _fetch_naver_news_batch(
        self,
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        cursor: str | None,
    ):
        if request.query_text is None:
            raise ValueError("NAVER_NEWS request must include query_text")
        return self.naver_provider.fetch_news(
            query=request.query_text,
            window_start=window_start,
            window_end=window_end,
            cursor=cursor,
        )

    def _build_bigkinds_company_requests(self, target: dict[str, Any]) -> list[DocumentSyncRequest]:
        return [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="BIGKINDS",
                source_kind="COMPANY",
                source_key=f"{target['source_key']}:company",
                source_label=target["name"],
                query_template="{company_name}",
                query_text=target["name"],
                company_id=target["company_id"],
            )
        ]

    def _build_bigkinds_theme_requests(self, keyword: str) -> list[DocumentSyncRequest]:
        return [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="BIGKINDS",
                source_kind="THEME",
                source_key=keyword,
                source_label=keyword,
                query_template="{keyword}",
                query_text=keyword,
                company_id=None,
            )
        ]

    def _build_mk_rss_company_requests(self, target: dict[str, Any]) -> list[DocumentSyncRequest]:
        requests = [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="MK_RSS",
                source_kind="COMPANY",
                source_key=f"{target['source_key']}:company",
                source_label=target["name"],
                query_template="{company_name}",
                query_text=target["name"],
                company_id=target["company_id"],
            )
        ]
        sector_keyword = target.get("sector_keyword")
        if sector_keyword:
            requests.append(
                DocumentSyncRequest(
                    job_name="raw_documents_sync_news",
                    provider="MK_RSS",
                    source_kind="COMPANY",
                    source_key=f"{target['source_key']}:sector:{sector_keyword}",
                    source_label=f"{target['name']}:{sector_keyword}",
                    query_template="{keyword}",
                    query_text=sector_keyword,
                    company_id=target["company_id"],
                )
            )
        return requests

    def _build_mk_rss_theme_requests(self, keyword: str) -> list[DocumentSyncRequest]:
        return [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="MK_RSS",
                source_kind="THEME",
                source_key=keyword,
                source_label=keyword,
                query_template="{keyword}",
                query_text=keyword,
                company_id=None,
            )
        ]

    def _build_naver_company_requests(self, target: dict[str, Any]) -> list[DocumentSyncRequest]:
        requests = [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="NAVER_NEWS",
                source_kind="COMPANY",
                source_key=f"{target['source_key']}:company",
                source_label=target["name"],
                query_template=self.naver_provider.company_query_template,
                query_text=self.naver_provider.build_company_query(company_name=target["name"]),
                company_id=target["company_id"],
            )
        ]
        sector_keyword = target.get("sector_keyword")
        if sector_keyword:
            requests.append(
                DocumentSyncRequest(
                    job_name="raw_documents_sync_news",
                    provider="NAVER_NEWS",
                    source_kind="COMPANY",
                    source_key=f"{target['source_key']}:sector:{sector_keyword}",
                    source_label=f"{target['name']}:{sector_keyword}",
                    query_template=self.naver_provider.theme_query_template,
                    query_text=self.naver_provider.build_theme_query(keyword=sector_keyword),
                    company_id=target["company_id"],
                )
            )
        return requests

    def _build_naver_theme_requests(self, keyword: str) -> list[DocumentSyncRequest]:
        return [
            DocumentSyncRequest(
                job_name="raw_documents_sync_news",
                provider="NAVER_NEWS",
                source_kind="THEME",
                source_key=keyword,
                source_label=keyword,
                query_template=self.naver_provider.theme_query_template,
                query_text=self.naver_provider.build_theme_query(keyword=keyword),
                company_id=None,
            )
        ]

    def sync_dart_disclosures_last_days(self, *, days: int, backfill: bool = False) -> IngestionRunResult:
        return self.sync_disclosures_last_days(
            provider="DART",
            days=days,
            backfill=backfill,
        )

    def sync_disclosures_last_days(
        self,
        *,
        provider: str,
        days: int,
        backfill: bool = False,
    ) -> IngestionRunResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_disclosures_window(
            provider=provider,
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
        return self.sync_disclosures_window(
            provider="DART",
            window_start=window_start,
            window_end=window_end,
            backfill=backfill,
        )

    def sync_disclosures_window(
        self,
        *,
        provider: str,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
    ) -> IngestionRunResult:
        descriptor = self.disclosure_provider_descriptors.get(normalize_provider_key(provider))
        if descriptor is None:
            raise ValueError(f"Unsupported disclosure provider: {provider}")
        return self._run_document_sync(
            request=descriptor.request,
            window_start=window_start,
            window_end=window_end,
            backfill=backfill,
            fetch_batch=descriptor.fetch_batch,
            resolve_candidate=descriptor.resolve_candidate,
        )

    def sync_news_candidates_for_companies_last_days(
        self,
        *,
        company_ids: list[int],
        company_names: list[str] | None,
        days: int,
        backfill: bool = False,
        providers: list[str] | None = None,
    ) -> list[IngestionRunResult]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_news_candidates_for_companies_window(
            company_ids=company_ids,
            company_names=company_names,
            window_start=window_start,
            window_end=now,
            backfill=backfill,
            providers=providers,
        )

    def sync_news_candidates_for_companies_window(
        self,
        *,
        company_ids: list[int],
        company_names: list[str] | None,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
        providers: list[str] | None = None,
    ) -> list[IngestionRunResult]:
        targets = self._load_company_targets(company_ids=company_ids, company_names=company_names or [])
        results: list[IngestionRunResult] = []
        selected_descriptors = self._select_news_provider_descriptors(providers)

        for target in targets:
            for descriptor in selected_descriptors:
                requests = descriptor.build_company_requests(target)
                for request in requests:
                    results.append(
                        self._run_document_sync(
                            request=request,
                            window_start=window_start,
                            window_end=window_end,
                            backfill=backfill,
                            fetch_batch=descriptor.fetch_batch,
                        )
                    )

        return results

    def sync_news_candidates_for_themes_last_days(
        self,
        *,
        keywords: list[str],
        days: int,
        backfill: bool = False,
        providers: list[str] | None = None,
    ) -> list[IngestionRunResult]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=max(days, 1))
        return self.sync_news_candidates_for_themes_window(
            keywords=keywords,
            window_start=window_start,
            window_end=now,
            backfill=backfill,
            providers=providers,
        )

    def sync_news_candidates_for_themes_window(
        self,
        *,
        keywords: list[str],
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
        providers: list[str] | None = None,
    ) -> list[IngestionRunResult]:
        normalized_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
        results: list[IngestionRunResult] = []
        selected_descriptors = self._select_news_provider_descriptors(providers)

        for keyword in normalized_keywords:
            for descriptor in selected_descriptors:
                requests = descriptor.build_theme_requests(keyword)
                for request in requests:
                    results.append(
                        self._run_document_sync(
                            request=request,
                            window_start=window_start,
                            window_end=window_end,
                            backfill=backfill,
                            fetch_batch=descriptor.fetch_batch,
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
        effective_time_sql = """
        CASE
            WHEN rd.document_type = 'NEWS_CANDIDATE'
                THEN COALESCE(rd.published_at, rd.observed_at, rd.receipt_at, rd.updated_at, rd.created_at)
            ELSE COALESCE(rd.published_at, rd.receipt_at, rd.observed_at, rd.updated_at, rd.created_at)
        END
        """.strip()
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
                ORDER BY {effective_time_sql} DESC, rd.id DESC
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

    def list_supported_ingestion_providers(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "disclosures": [
                {
                    "provider": descriptor.provider,
                    "supports_system_sync": True,
                }
                for descriptor in self._sorted_disclosure_provider_descriptors()
            ],
            "news": [
                {
                    "provider": descriptor.provider,
                    "supports_company_sync": True,
                    "supports_theme_sync": True,
                }
                for descriptor in self._sorted_news_provider_descriptors()
            ],
        }

    def backfill_publisher_registry(
        self,
        *,
        limit: int | None = None,
        only_missing: bool = True,
    ) -> dict[str, int]:
        filters = [
            "publisher IS NOT NULL",
            "TRIM(publisher) <> ''",
        ]
        params: list[Any] = []
        if only_missing:
            filters.append("(publisher_key IS NULL OR TRIM(publisher_key) = '')")

        limit_clause = ""
        if limit is not None and limit > 0:
            limit_clause = "LIMIT ?"
            params.append(int(limit))

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, publisher, publisher_key
                FROM raw_documents
                WHERE {' AND '.join(filters)}
                ORDER BY id ASC
                {limit_clause}
                """,
                params,
            ).fetchall()

            updated_raw_documents = 0
            seen_publishers: set[str] = set()
            for row in rows:
                publisher_key = self._ensure_publisher_registered(
                    connection,
                    publisher=row["publisher"],
                    publisher_key=row["publisher_key"],
                )
                if publisher_key is None:
                    continue

                seen_publishers.add(publisher_key)
                if row["publisher_key"] == publisher_key:
                    continue

                connection.execute(
                    """
                    UPDATE raw_documents
                    SET publisher_key = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (publisher_key, utcnow_iso(), int(row["id"])),
                )
                updated_raw_documents += 1

            updated_events = connection.execute(
                """
                UPDATE events
                SET publisher_key = (
                    SELECT rd.publisher_key
                    FROM raw_documents rd
                    WHERE rd.id = events.primary_document_id
                )
                WHERE (
                    publisher_key IS NULL OR TRIM(publisher_key) = ''
                )
                  AND primary_document_id IN (
                    SELECT id
                    FROM raw_documents
                    WHERE publisher_key IS NOT NULL
                )
                """
            ).rowcount
            updated_source_documents = connection.execute(
                """
                UPDATE source_documents
                SET publisher_key = (
                    SELECT rd.publisher_key
                    FROM raw_documents rd
                    WHERE rd.id = source_documents.raw_document_id
                )
                WHERE (
                    publisher_key IS NULL OR TRIM(publisher_key) = ''
                )
                  AND raw_document_id IN (
                    SELECT id
                    FROM raw_documents
                    WHERE publisher_key IS NOT NULL
                )
                """
            ).rowcount
            updated_event_evidence = connection.execute(
                """
                UPDATE event_evidence
                SET publisher_key = (
                    SELECT sd.publisher_key
                    FROM source_documents sd
                    WHERE sd.id = event_evidence.source_document_id
                )
                WHERE (
                    publisher_key IS NULL OR TRIM(publisher_key) = ''
                )
                  AND source_document_id IN (
                    SELECT id
                    FROM source_documents
                    WHERE publisher_key IS NOT NULL
                )
                """
            ).rowcount

        return {
            "processed_count": len(rows),
            "publisher_count": len(seen_publishers),
            "updated_raw_documents": updated_raw_documents,
            "updated_events": updated_events,
            "updated_source_documents": updated_source_documents,
            "updated_event_evidence": updated_event_evidence,
        }

    def _run_document_sync(
        self,
        *,
        request: DocumentSyncRequest,
        window_start: datetime,
        window_end: datetime,
        backfill: bool,
        fetch_batch,
        resolve_candidate=None,
    ) -> IngestionRunResult:
        mode = "BACKFILL" if backfill else "INCREMENTAL"

        with get_connection(self.db_path) as connection:
            source = self._ensure_source(
                connection,
                provider=request.provider,
                source_kind=request.source_kind,
                source_key=request.source_key,
                source_label=request.source_label,
                query_template=request.query_template,
            )

            cursor_before = None if backfill else source.get("last_cursor")
            run_id = self._start_fetch_run(
                connection,
                job_name=request.job_name,
                provider=request.provider,
                mode=mode,
                source_kind=request.source_kind,
                source_key=request.source_key,
                query_text=request.query_text,
                window_start=window_start,
                window_end=window_end,
                cursor_before=cursor_before,
                metadata={
                    "source_id": source["id"],
                    "source_label": request.source_label,
                },
            )

            processed_count = 0
            inserted_count = 0
            duplicate_count = 0
            failed_count = 0
            cursor_after = cursor_before

            try:
                batch = fetch_batch(request, window_start, window_end, cursor_before)

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
                        metadata={
                            "disabled_reason": batch.disabled_reason,
                            "query": request.query_text,
                        },
                        error_message=None,
                    )
                    return IngestionRunResult(
                        run_id=run_id,
                        status="SKIPPED_DISABLED",
                        provider=request.provider,
                        source_kind=request.source_kind,
                        source_key=request.source_key,
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
                        if resolve_candidate is not None:
                            resolved_record = resolve_candidate(connection, resolved_record)
                        if request.company_id is not None and resolved_record.company_id is None:
                            resolved_record = replace(resolved_record, company_id=request.company_id)

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
                            "raw_ingestion_record_failed",
                            extra={
                                "run_id": run_id,
                                "provider": request.provider,
                                "source_key": request.source_key,
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
                    provider=request.provider,
                    source_kind=request.source_kind,
                    source_key=request.source_key,
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
                    provider=request.provider,
                    source_kind=request.source_kind,
                    source_key=request.source_key,
                    processed_count=processed_count,
                    inserted_count=inserted_count,
                    duplicate_count=duplicate_count,
                    failed_count=failed_count,
                    cursor_before=cursor_before,
                    cursor_after=cursor_after,
                    error_message=str(error),
                )

    def _sorted_disclosure_provider_descriptors(self) -> list[DisclosureProviderDescriptor]:
        return sorted(
            self.disclosure_provider_descriptors.values(),
            key=lambda descriptor: descriptor.provider,
        )

    def _sorted_news_provider_descriptors(self) -> list[NewsProviderDescriptor]:
        return sorted(
            self.news_provider_descriptors.values(),
            key=lambda descriptor: descriptor.provider,
        )

    def _select_news_provider_descriptors(
        self,
        providers: list[str] | None,
    ) -> list[NewsProviderDescriptor]:
        if not providers:
            return self._sorted_news_provider_descriptors()

        selected: list[NewsProviderDescriptor] = []
        missing: list[str] = []
        for provider in providers:
            normalized = normalize_provider_key(provider)
            descriptor = self.news_provider_descriptors.get(normalized)
            if descriptor is None:
                missing.append(provider)
                continue
            selected.append(descriptor)

        if missing:
            raise ValueError(f"Unsupported news providers: {', '.join(sorted(set(missing)))}")
        return selected

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
        self._ensure_provider_registered(
            connection,
            provider=candidate.provider,
            document_type=candidate.document_type,
        )
        now = utcnow_iso()
        normalized_title_hash = title_hash(candidate.title)
        canonical_url = canonicalize_url(candidate.canonical_url or candidate.source_url)
        publisher_key = self._ensure_publisher_registered(
            connection,
            publisher=candidate.publisher,
            publisher_key=candidate.publisher_key,
        )

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

        resolved_observed_at = (
            (str(existing["observed_at"]).strip() if existing is not None and existing["observed_at"] is not None else None)
            or candidate.observed_at
            or now
        )
        resolved_published_at = (
            candidate.published_at
            or (str(existing["published_at"]).strip() if existing is not None and existing["published_at"] is not None else None)
        )
        resolved_receipt_at = (
            candidate.receipt_at
            or (str(existing["receipt_at"]).strip() if existing is not None and existing["receipt_at"] is not None else None)
        )
        resolved_published_at_source = candidate.published_at_source or determine_published_at_source(
            document_type=candidate.document_type,
            published_at=resolved_published_at,
            receipt_at=resolved_receipt_at,
            observed_at=resolved_observed_at,
        )

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
                    publisher_key,
                    source_url,
                    canonical_url,
                    published_at,
                    observed_at,
                    published_at_source,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.provider,
                    candidate.provider_document_id,
                    candidate.document_type,
                    candidate.title,
                    candidate.summary,
                    candidate.publisher,
                    publisher_key,
                    candidate.source_url,
                    canonical_url,
                    resolved_published_at,
                    resolved_observed_at,
                    resolved_published_at_source,
                    resolved_receipt_at,
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
                    publisher_key = ?,
                    source_url = ?,
                    canonical_url = ?,
                    published_at = ?,
                    observed_at = ?,
                    published_at_source = ?,
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
                    publisher_key,
                    candidate.source_url,
                    canonical_url,
                    resolved_published_at,
                    resolved_observed_at,
                    resolved_published_at_source,
                    resolved_receipt_at,
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
