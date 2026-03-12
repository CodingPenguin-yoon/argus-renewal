from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from .company_master.db import utcnow_iso

_WHITESPACE_RE = re.compile(r"\s+")
_PUBLISHER_KEY_RE = re.compile(r"[^0-9A-Za-z가-힣]+")
_PUBLISHER_ALIASES = {
    "매경": "매일경제",
    "매일 경제": "매일경제",
    "한경": "한국경제",
    "한국 경제": "한국경제",
}


@dataclass(frozen=True)
class PublisherDefinition:
    publisher_key: str
    display_name: str
    canonical_name: str
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_publisher_display_name(value: str | None) -> str | None:
    if value is None:
        return None

    candidate = _WHITESPACE_RE.sub(" ", str(value).strip())
    if not candidate:
        return None

    return _PUBLISHER_ALIASES.get(candidate.casefold(), candidate)


def normalize_publisher_key(value: str | None) -> str | None:
    normalized_name = normalize_publisher_display_name(value)
    if normalized_name is None:
        return None

    key = _PUBLISHER_KEY_RE.sub("_", normalized_name).strip("_").upper()
    return key or None


def build_publisher_definition(
    *,
    publisher_name: str | None,
    publisher_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PublisherDefinition | None:
    display_name = normalize_publisher_display_name(publisher_name)
    normalized_key = (publisher_key or normalize_publisher_key(display_name) or "").strip().upper()
    if not display_name or not normalized_key:
        return None

    return PublisherDefinition(
        publisher_key=normalized_key,
        display_name=display_name,
        canonical_name=display_name,
        metadata=metadata or {},
    )


def publisher_definition_from_row(row: Any) -> PublisherDefinition:
    metadata = row["metadata_json"] if "metadata_json" in row.keys() else None
    return PublisherDefinition(
        publisher_key=str(row["publisher_key"]),
        display_name=str(row["display_name"]),
        canonical_name=str(row["canonical_name"]),
        is_active=bool(row["is_active"]),
        metadata=json.loads(metadata) if metadata else {},
    )


def ensure_publisher_definition(
    connection,
    *,
    publisher_name: str | None,
    publisher_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PublisherDefinition | None:
    definition = build_publisher_definition(
        publisher_name=publisher_name,
        publisher_key=publisher_key,
        metadata=metadata,
    )
    if definition is None:
        return None

    now = utcnow_iso()
    connection.execute(
        """
        INSERT INTO publisher_registry (
            publisher_key,
            display_name,
            canonical_name,
            is_active,
            metadata_json,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(publisher_key) DO UPDATE SET
            display_name = excluded.display_name,
            canonical_name = excluded.canonical_name,
            is_active = excluded.is_active,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            definition.publisher_key,
            definition.display_name,
            definition.canonical_name,
            1 if definition.is_active else 0,
            json.dumps(definition.metadata, ensure_ascii=False, sort_keys=True),
            now,
            now,
        ),
    )
    return definition
