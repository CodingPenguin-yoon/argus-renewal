from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    no_tags = _HTML_TAG_RE.sub(" ", value)
    unescaped = html.unescape(no_tags)
    compact = _WHITESPACE_RE.sub(" ", unescaped).strip()
    return compact or None


def normalize_title(value: str | None) -> str | None:
    stripped = strip_html(value)
    if not stripped:
        return None
    return stripped.casefold()


def title_hash(value: str | None) -> str | None:
    normalized = normalize_title(value)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def canonicalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate

    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query_pairs = []
    for key, current_value in parse_qsl(parsed.query, keep_blank_values=False):
        if key.lower() in _TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, current_value))

    query_pairs.sort(key=lambda item: item[0])
    clean_query = urlencode(query_pairs)

    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=path,
        params="",
        query=clean_query,
        fragment="",
    )
    return urlunparse(normalized)


def news_dedup_key(*, canonical_url: str | None, normalized_title_hash: str | None) -> str | None:
    if not canonical_url or not normalized_title_hash:
        return None
    raw_value = f"{canonical_url}|{normalized_title_hash}"
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def dart_dedup_key(provider_document_id: str | None) -> str | None:
    if provider_document_id is None:
        return None
    candidate = provider_document_id.strip()
    return candidate or None
