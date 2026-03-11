from __future__ import annotations

import re

_CORP_SUFFIX_PATTERNS: tuple[str, ...] = (
    "주식회사",
    "(주)",
    "㈜",
    "유한회사",
    "코스닥",
    "코스피",
    "CORPORATION",
    "CORP",
    "CORP.",
    "CO.,LTD",
    "CO., LTD.",
    "CO LTD",
    "LTD",
    "LTD.",
)


def normalize_company_name(value: str | None) -> str:
    if not value:
        return ""

    normalized = value.strip().upper()
    for token in _CORP_SUFFIX_PATTERNS:
        normalized = normalized.replace(token, "")

    normalized = re.sub(r"[^0-9A-Z가-힣]", "", normalized)
    return normalized.strip()


def normalize_stock_code(value: str | None) -> str | None:
    if not value:
        return None

    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 0:
        return None

    if len(digits) >= 6:
        return digits[-6:]

    return digits.zfill(6)
