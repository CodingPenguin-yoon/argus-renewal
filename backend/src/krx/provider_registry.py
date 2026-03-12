from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from .company_master.db import utcnow_iso
from .source_ingestion.event_taxonomy import SOURCE_TRUST_SCORES

PROVIDER_FAMILY_DISCLOSURE = "DISCLOSURE"
PROVIDER_FAMILY_CURATED_NEWS = "CURATED_NEWS"
PROVIDER_FAMILY_DISCOVERY_NEWS = "DISCOVERY_NEWS"
PROVIDER_FAMILY_TREND_SIGNAL = "TREND_SIGNAL"
PROVIDER_FAMILY_MARKET_DATA = "MARKET_DATA"
PROVIDER_FAMILY_REFERENCE_DATA = "REFERENCE_DATA"

RAW_NEWS_PROVIDER_FAMILIES = {
    PROVIDER_FAMILY_DISCLOSURE,
    PROVIDER_FAMILY_CURATED_NEWS,
    PROVIDER_FAMILY_DISCOVERY_NEWS,
}


@dataclass(frozen=True)
class ProviderDefinition:
    provider_key: str
    display_name: str
    provider_family: str
    source_type: str | None = None
    document_kind: str | None = None
    storage_policy: str | None = None
    trust_score: float = SOURCE_TRUST_SCORES["DISCOVERY_NEWS"]
    priority: int = 100
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_provider_key(value: str) -> str:
    return str(value or "").strip().upper()


def _family_defaults(provider_family: str) -> dict[str, Any]:
    if provider_family == PROVIDER_FAMILY_DISCLOSURE:
        return {
            "source_type": "DISCLOSURE",
            "document_kind": "DISCLOSURE",
            "storage_policy": "CANONICAL_EVENT",
            "trust_score": SOURCE_TRUST_SCORES["DISCLOSURE"],
            "priority": 10,
        }
    if provider_family == PROVIDER_FAMILY_CURATED_NEWS:
        return {
            "source_type": "CURATED_NEWS",
            "document_kind": "CURATED_NEWS",
            "storage_policy": "PERSISTENT_EVIDENCE",
            "trust_score": SOURCE_TRUST_SCORES["CURATED_NEWS"],
            "priority": 20,
        }
    if provider_family == PROVIDER_FAMILY_TREND_SIGNAL:
        return {
            "source_type": None,
            "document_kind": None,
            "storage_policy": None,
            "trust_score": 0.0,
            "priority": 40,
        }
    if provider_family == PROVIDER_FAMILY_MARKET_DATA:
        return {
            "source_type": None,
            "document_kind": None,
            "storage_policy": None,
            "trust_score": 0.0,
            "priority": 50,
        }
    if provider_family == PROVIDER_FAMILY_REFERENCE_DATA:
        return {
            "source_type": None,
            "document_kind": None,
            "storage_policy": None,
            "trust_score": 0.0,
            "priority": 60,
        }
    return {
        "source_type": "DISCOVERY_NEWS",
        "document_kind": "DISCOVERY_CANDIDATE",
        "storage_policy": "TRANSIENT_DISCOVERY",
        "trust_score": SOURCE_TRUST_SCORES["DISCOVERY_NEWS"],
        "priority": 30,
    }


def infer_provider_family(
    *,
    provider_family: str | None = None,
    source_type: str | None = None,
    document_type: str | None = None,
    document_kind: str | None = None,
) -> str:
    if provider_family:
        return provider_family.strip().upper()

    normalized_source_type = str(source_type or "").strip().upper()
    normalized_document_type = str(document_type or "").strip().upper()
    normalized_document_kind = str(document_kind or "").strip().upper()

    if normalized_source_type == "DISCLOSURE" or normalized_document_type == "DISCLOSURE":
        return PROVIDER_FAMILY_DISCLOSURE
    if normalized_source_type == "CURATED_NEWS" or normalized_document_kind == "CURATED_NEWS":
        return PROVIDER_FAMILY_CURATED_NEWS
    if normalized_source_type == "DISCOVERY_NEWS" or normalized_document_kind == "DISCOVERY_CANDIDATE":
        return PROVIDER_FAMILY_DISCOVERY_NEWS
    return PROVIDER_FAMILY_DISCOVERY_NEWS


def build_provider_definition(
    *,
    provider_key: str,
    display_name: str | None = None,
    provider_family: str | None = None,
    source_type: str | None = None,
    document_type: str | None = None,
    document_kind: str | None = None,
    storage_policy: str | None = None,
    trust_score: float | None = None,
    priority: int | None = None,
    is_active: bool = True,
    metadata: dict[str, Any] | None = None,
) -> ProviderDefinition:
    normalized_key = normalize_provider_key(provider_key)
    family = infer_provider_family(
        provider_family=provider_family,
        source_type=source_type,
        document_type=document_type,
        document_kind=document_kind,
    )
    defaults = _family_defaults(family)

    return ProviderDefinition(
        provider_key=normalized_key,
        display_name=(display_name or normalized_key).strip() or normalized_key,
        provider_family=family,
        source_type=(source_type or defaults["source_type"]),
        document_kind=(document_kind or defaults["document_kind"]),
        storage_policy=(storage_policy or defaults["storage_policy"]),
        trust_score=float(defaults["trust_score"] if trust_score is None else trust_score),
        priority=int(defaults["priority"] if priority is None else priority),
        is_active=bool(is_active),
        metadata=metadata or {},
    )


DEFAULT_PROVIDER_DEFINITIONS: dict[str, ProviderDefinition] = {
    "DART": build_provider_definition(
        provider_key="DART",
        display_name="DART",
        provider_family=PROVIDER_FAMILY_DISCLOSURE,
        priority=10,
    ),
    "BIGKINDS": build_provider_definition(
        provider_key="BIGKINDS",
        display_name="BigKinds",
        provider_family=PROVIDER_FAMILY_CURATED_NEWS,
        priority=20,
        is_active=False,
    ),
    "NAVER_NEWS": build_provider_definition(
        provider_key="NAVER_NEWS",
        display_name="Naver News",
        provider_family=PROVIDER_FAMILY_DISCOVERY_NEWS,
        priority=30,
    ),
    "MK_RSS": build_provider_definition(
        provider_key="MK_RSS",
        display_name="MK RSS",
        provider_family=PROVIDER_FAMILY_CURATED_NEWS,
        priority=22,
    ),
    "NAVER_DATALAB": build_provider_definition(
        provider_key="NAVER_DATALAB",
        display_name="Naver DataLab",
        provider_family=PROVIDER_FAMILY_TREND_SIGNAL,
        priority=40,
    ),
}


def provider_definition_from_row(row: Any) -> ProviderDefinition:
    metadata = row["metadata_json"] if "metadata_json" in row.keys() else None
    return ProviderDefinition(
        provider_key=normalize_provider_key(row["provider_key"]),
        display_name=str(row["display_name"]),
        provider_family=str(row["provider_family"]),
        source_type=row["source_type"],
        document_kind=row["document_kind"],
        storage_policy=row["storage_policy"],
        trust_score=float(row["trust_score"] if row["trust_score"] is not None else 0.0),
        priority=int(row["priority"] if row["priority"] is not None else 100),
        is_active=bool(row["is_active"]),
        metadata=json.loads(metadata) if metadata else {},
    )


def list_provider_definitions(connection) -> dict[str, ProviderDefinition]:
    rows = connection.execute(
        """
        SELECT
            provider_key,
            display_name,
            provider_family,
            source_type,
            document_kind,
            storage_policy,
            trust_score,
            priority,
            is_active,
            metadata_json
        FROM provider_registry
        """
    ).fetchall()
    definitions = dict(DEFAULT_PROVIDER_DEFINITIONS)
    for row in rows:
        definition = provider_definition_from_row(row)
        definitions[definition.provider_key] = definition
    return definitions


def resolve_provider_definition(
    provider_definitions: dict[str, ProviderDefinition],
    *,
    provider_key: str,
    provider_family: str | None = None,
    source_type: str | None = None,
    document_type: str | None = None,
    document_kind: str | None = None,
) -> ProviderDefinition:
    normalized_key = normalize_provider_key(provider_key)
    definition = provider_definitions.get(normalized_key)
    if definition is not None:
        return definition
    return build_provider_definition(
        provider_key=normalized_key,
        provider_family=provider_family,
        source_type=source_type,
        document_type=document_type,
        document_kind=document_kind,
    )


def ensure_provider_definition(connection, definition: ProviderDefinition) -> None:
    now = utcnow_iso()
    connection.execute(
        """
        INSERT INTO provider_registry (
            provider_key,
            display_name,
            provider_family,
            source_type,
            document_kind,
            storage_policy,
            trust_score,
            priority,
            is_active,
            metadata_json,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_key) DO NOTHING
        """,
        (
            definition.provider_key,
            definition.display_name,
            definition.provider_family,
            definition.source_type,
            definition.document_kind,
            definition.storage_policy,
            definition.trust_score,
            definition.priority,
            1 if definition.is_active else 0,
            json.dumps(definition.metadata, ensure_ascii=False, sort_keys=True),
            now,
            now,
        ),
    )
