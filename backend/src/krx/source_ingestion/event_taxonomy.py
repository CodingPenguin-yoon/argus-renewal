from __future__ import annotations

from dataclasses import dataclass
import re

from .normalize import normalize_title

EVENT_TAXONOMY: tuple[str, ...] = (
    "earnings",
    "guidance",
    "contract_order",
    "supply_customer",
    "capex_factory",
    "mna_investment",
    "shareholder_return",
    "financing",
    "regulation_policy",
    "product_launch",
    "management_change_of_control",
    "legal_dispute",
    "accident_outage_incident",
    "macro_theme",
)

EVENT_TYPE_LABELS: dict[str, str] = {
    "earnings": "earnings",
    "guidance": "guidance",
    "contract_order": "contract/order",
    "supply_customer": "supply/customer",
    "capex_factory": "capex/factory",
    "mna_investment": "M&A/investment",
    "shareholder_return": "shareholder_return",
    "financing": "financing",
    "regulation_policy": "regulation/policy",
    "product_launch": "product_launch",
    "management_change_of_control": "management/change_of_control",
    "legal_dispute": "legal/dispute",
    "accident_outage_incident": "accident/outage/incident",
    "macro_theme": "macro/theme",
}

_SENTIMENT_POSITIVE_KEYWORDS = (
    "상향",
    "개선",
    "증가",
    "성장",
    "호조",
    "수혜",
    "확대",
    "record high",
    "beat",
    "strong",
)

_SENTIMENT_NEGATIVE_KEYWORDS = (
    "하향",
    "감소",
    "부진",
    "악화",
    "중단",
    "지연",
    "리콜",
    "소송",
    "벌금",
    "사고",
    "loss",
    "miss",
    "weak",
)

EVENT_TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("earnings", ("실적", "어닝", "영업이익", "순이익", "earnings", "quarter results")),
    ("guidance", ("가이던스", "전망", "guidance", "outlook")),
    ("contract_order", ("수주", "계약", "발주", "order", "contract")),
    ("supply_customer", ("공급", "납품", "고객사", "customer", "supplier", "supply")),
    ("capex_factory", ("증설", "신공장", "공장", "라인", "capex", "facility", "plant")),
    ("mna_investment", ("인수", "합병", "지분투자", "투자", "acquisition", "merger", "m&a")),
    ("shareholder_return", ("자사주", "배당", "소각", "buyback", "dividend", "shareholder return")),
    ("financing", ("유상증자", "회사채", "차입", "대출", "funding", "financing", "bond")),
    ("regulation_policy", ("규제", "정책", "법안", "정부", "regulation", "policy", "bill")),
    ("product_launch", ("출시", "신제품", "서비스", "launch", "rollout", "release")),
    (
        "management_change_of_control",
        ("대표이사", "경영진", "최대주주", "지배구조", "change of control", "ceo", "board"),
    ),
    ("legal_dispute", ("소송", "분쟁", "법원", "제재", "lawsuit", "dispute", "fine")),
    ("accident_outage_incident", ("사고", "화재", "정전", "장애", "중단", "outage", "incident")),
)

RELATIONSHIP_KEYWORDS: tuple[str, ...] = (
    "공급",
    "납품",
    "고객",
    "고객사",
    "자회사",
    "모회사",
    "협력사",
    "주주",
    "경쟁",
    "competitor",
    "supplier",
    "customer",
    "subsidiary",
    "shareholder",
)

THEME_KEYWORDS: tuple[str, ...] = (
    "정책",
    "규제",
    "테마",
    "업종",
    "섹터",
    "거시",
    "금리",
    "환율",
    "macro",
    "theme",
    "sector",
    "policy",
)

SOURCE_TRUST_SCORES: dict[str, float] = {
    "DISCLOSURE": 1.0,
    "CURATED_NEWS": 0.8,
    "DISCOVERY_NEWS": 0.6,
}

_DART_PREFIX_RE = re.compile(r"^\[[^\]]+\]")


@dataclass(frozen=True)
class DartDisclosureClassification:
    normalized_report_name: str
    event_type: str
    sentiment: str
    impact_direction: str
    impact_horizon: str
    event_subtype: str
    risk_flags: tuple[str, ...] = ()


def classify_event_type(text: str | None) -> str:
    normalized = normalize_title(text) or ""
    if not normalized:
        return "macro_theme"

    for event_type, keywords in EVENT_TYPE_KEYWORDS:
        if any(keyword.casefold() in normalized for keyword in keywords):
            return event_type
    return "macro_theme"


def classify_sentiment(text: str | None) -> str:
    normalized = normalize_title(text) or ""
    if not normalized:
        return "neutral"

    has_positive = any(keyword.casefold() in normalized for keyword in _SENTIMENT_POSITIVE_KEYWORDS)
    has_negative = any(keyword.casefold() in normalized for keyword in _SENTIMENT_NEGATIVE_KEYWORDS)

    if has_positive and has_negative:
        return "mixed"
    if has_positive:
        return "positive"
    if has_negative:
        return "negative"
    return "neutral"


def event_type_label(event_type: str) -> str:
    return EVENT_TYPE_LABELS.get(event_type, event_type)


def normalize_event_type(candidate: str | None) -> str | None:
    if candidate is None:
        return None
    value = candidate.strip().lower().replace("/", "_")
    aliases = {
        "contractorder": "contract_order",
        "contract_order": "contract_order",
        "supplycustomer": "supply_customer",
        "supply_customer": "supply_customer",
        "capexfactory": "capex_factory",
        "capex_factory": "capex_factory",
        "m&a": "mna_investment",
        "mna": "mna_investment",
        "mna_investment": "mna_investment",
        "shareholderreturn": "shareholder_return",
        "shareholder_return": "shareholder_return",
        "regulationpolicy": "regulation_policy",
        "regulation_policy": "regulation_policy",
        "productlaunch": "product_launch",
        "product_launch": "product_launch",
        "managementchangeofcontrol": "management_change_of_control",
        "management_change_of_control": "management_change_of_control",
        "legaldispute": "legal_dispute",
        "legal_dispute": "legal_dispute",
        "accidentoutageincident": "accident_outage_incident",
        "accident_outage_incident": "accident_outage_incident",
        "macrotheme": "macro_theme",
        "macro_theme": "macro_theme",
        "earnings": "earnings",
        "guidance": "guidance",
        "financing": "financing",
    }
    if value in aliases:
        return aliases[value]
    return value if value in EVENT_TAXONOMY else None


def normalize_dart_report_title(report_name: str | None) -> str:
    normalized = str(report_name or "").strip()
    while True:
        updated = _DART_PREFIX_RE.sub("", normalized, count=1).strip()
        if updated == normalized:
            return normalized
        normalized = updated


def classify_dart_disclosure(report_name: str | None) -> DartDisclosureClassification:
    original = str(report_name or "").strip()
    normalized = normalize_dart_report_title(original)
    risk_flags: list[str] = []

    if original != normalized:
        risk_flags.append("amended_disclosure")

    def _classification(
        *,
        event_type: str,
        sentiment: str,
        impact_direction: str,
        impact_horizon: str,
        event_subtype: str,
    ) -> DartDisclosureClassification:
        return DartDisclosureClassification(
            normalized_report_name=normalized,
            event_type=event_type,
            sentiment=sentiment,
            impact_direction=impact_direction,
            impact_horizon=impact_horizon,
            event_subtype=event_subtype,
            risk_flags=tuple(risk_flags),
        )

    if any(keyword in normalized for keyword in ("사업보고서", "반기보고서", "분기보고서", "매출액또는손익구조", "영업(잠정)실적")):
        subtype = "periodic_report" if "보고서" in normalized else "earnings_update"
        return _classification(
            event_type="earnings",
            sentiment="neutral",
            impact_direction="mixed",
            impact_horizon="short",
            event_subtype=subtype,
        )

    if any(
        keyword in normalized
        for keyword in (
            "유상증자결정",
            "무상증자결정",
            "전환사채권발행결정",
            "신주인수권부사채권발행결정",
            "교환사채권발행결정",
            "감자결정",
            "자기주식처분결정",
        )
    ):
        return _classification(
            event_type="financing",
            sentiment="mixed",
            impact_direction="mixed",
            impact_horizon="short",
            event_subtype="capital_structure",
        )

    if any(keyword in normalized for keyword in ("자기주식취득결정", "자기주식소각결정", "현금ㆍ현물배당결정", "주식배당결정")):
        return _classification(
            event_type="shareholder_return",
            sentiment="positive",
            impact_direction="positive",
            impact_horizon="medium",
            event_subtype="capital_return",
        )

    if any(keyword in normalized for keyword in ("단일판매ㆍ공급계약체결", "단일판매ㆍ공급계약해지", "공급계약")):
        sentiment = "negative" if "해지" in normalized else "positive"
        impact = "negative" if "해지" in normalized else "positive"
        subtype = "contract_termination" if "해지" in normalized else "contract_award"
        return _classification(
            event_type="contract_order",
            sentiment=sentiment,
            impact_direction=impact,
            impact_horizon="medium",
            event_subtype=subtype,
        )

    if any(keyword in normalized for keyword in ("타법인주식및출자증권취득결정", "타법인주식및출자증권처분결정", "합병", "분할", "영업양수도")):
        return _classification(
            event_type="mna_investment",
            sentiment="neutral",
            impact_direction="mixed",
            impact_horizon="medium",
            event_subtype="strategic_transaction",
        )

    if any(keyword in normalized for keyword in ("최대주주변경", "최대주주등소유주식변동신고서", "주식등의대량보유상황보고서", "임원ㆍ주요주주특정증권등소유상황보고서")):
        return _classification(
            event_type="management_change_of_control",
            sentiment="mixed",
            impact_direction="mixed",
            impact_horizon="medium",
            event_subtype="ownership_change",
        )

    if any(keyword in normalized for keyword in ("소송", "횡령ㆍ배임", "제재")):
        return _classification(
            event_type="legal_dispute",
            sentiment="negative",
            impact_direction="negative",
            impact_horizon="medium",
            event_subtype="legal_risk",
        )

    if any(keyword in normalized for keyword in ("회생절차개시", "부도발생", "영업정지", "해산사유발생", "사고")):
        return _classification(
            event_type="accident_outage_incident",
            sentiment="negative",
            impact_direction="negative",
            impact_horizon="short",
            event_subtype="distress_event",
        )

    if any(keyword in normalized for keyword in ("유형자산취득결정", "유형자산처분결정", "시설투자")):
        return _classification(
            event_type="capex_factory",
            sentiment="neutral",
            impact_direction="mixed",
            impact_horizon="medium",
            event_subtype="asset_investment",
        )

    return _classification(
        event_type=classify_event_type(normalized),
        sentiment=classify_sentiment(normalized),
        impact_direction="mixed",
        impact_horizon="short",
        event_subtype="generic_disclosure",
    )
