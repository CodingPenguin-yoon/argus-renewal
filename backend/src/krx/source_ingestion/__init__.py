from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = [
    "BriefingInputRunResult",
    "CompanyReportBatchOutcome",
    "CompanyReportRunOutcome",
    "CompanyReportService",
    "EventNormalizationResult",
    "EventNormalizationService",
    "IngestionRunResult",
    "MarketBriefingBacktestResult",
    "MarketBriefingGenerationResult",
    "MarketBriefingInputService",
    "MarketBriefingSignalService",
    "RawDocumentIngestionService",
]

_LAZY_EXPORTS = {
    "BriefingInputRunResult": ".briefing_models",
    "CompanyReportBatchOutcome": ".company_report_service",
    "CompanyReportRunOutcome": ".company_report_service",
    "CompanyReportService": ".company_report_service",
    "EventNormalizationResult": ".event_service",
    "EventNormalizationService": ".event_service",
    "IngestionRunResult": ".service",
    "MarketBriefingBacktestResult": ".briefing_signal_service",
    "MarketBriefingGenerationResult": ".briefing_signal_service",
    "MarketBriefingInputService": ".briefing_service",
    "MarketBriefingSignalService": ".briefing_signal_service",
    "RawDocumentIngestionService": ".service",
}

if TYPE_CHECKING:
    from .briefing_models import BriefingInputRunResult
    from .briefing_service import MarketBriefingInputService
    from .briefing_signal_service import (
        MarketBriefingBacktestResult,
        MarketBriefingGenerationResult,
        MarketBriefingSignalService,
    )
    from .company_report_service import (
        CompanyReportBatchOutcome,
        CompanyReportRunOutcome,
        CompanyReportService,
    )
    from .event_service import EventNormalizationResult, EventNormalizationService
    from .service import IngestionRunResult, RawDocumentIngestionService


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
