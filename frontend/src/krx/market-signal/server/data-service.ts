import {
  MarketSignalCoverageSection,
  MarketSignalMetric,
  MarketSignalSourceCoverage,
  MarketSignalSummary,
  MarketSignalTrendBadge,
} from "@/krx/types/domain";
import { ApiItemResponse, getKrxJson } from "@/krx/server/client";

type ApiMarketSignalTrendBadge = {
  label: string;
  tone: "positive" | "neutral" | "negative";
};

type ApiMarketSignalMetric = {
  key: string;
  label: string;
  raw_value: unknown;
  formatted_value: string;
  provenance: {
    source_table: string | null;
    source_name: string | null;
    source_url: string | null;
    source_record_id: string | null;
    trade_date: string | null;
    metric_key: string | null;
  };
};

type ApiMarketSignalCardCoverage = {
  state: "full" | "partial" | "missing";
  coverage_ratio: number;
  label: string;
  source_names: string[];
};

type ApiMarketSignalCard = {
  key: string;
  title: string;
  tone: "positive" | "neutral" | "negative";
  interpretation_line: string;
  detail_text: string | null;
  trend_badge: ApiMarketSignalTrendBadge | null;
  source_coverage: ApiMarketSignalCardCoverage;
  supporting_metrics: ApiMarketSignalMetric[];
};

type ApiMarketSignalCoverageSection = {
  key: string;
  label: string;
  status: "available" | "missing" | "rule_based";
  source_name: string | null;
  updated_at: string | null;
};

type ApiMarketSignalSourceCoverage = ApiMarketSignalCardCoverage & {
  trade_date: string | null;
  sections: ApiMarketSignalCoverageSection[];
};

type ApiMarketSignalSummary = {
  requested_date: string | null;
  date: string | null;
  requested_date_available: boolean;
  is_latest_fallback: boolean;
  interpretation_line: string;
  explanation_text: string;
  explanation_source: "market_briefings" | "rule_based";
  directional_bias: "bullish" | "bearish" | "neutral";
  gap_bias: "gap_up" | "gap_down" | "flat";
  volatility_bias: "rising" | "stable" | "falling";
  confidence_bucket: "low" | "medium" | "high";
  source_coverage: ApiMarketSignalSourceCoverage;
  cards: ApiMarketSignalCard[];
  last_updated_at: string | null;
  missing_fields: string[];
};

function mapTrendBadge(value: ApiMarketSignalTrendBadge | null): MarketSignalTrendBadge | null {
  if (!value) return null;
  return { label: value.label, tone: value.tone };
}

function mapMetric(value: ApiMarketSignalMetric): MarketSignalMetric {
  return {
    key: value.key,
    label: value.label,
    rawValue: value.raw_value,
    formattedValue: value.formatted_value,
    provenance: {
      sourceTable: value.provenance.source_table,
      sourceName: value.provenance.source_name,
      sourceUrl: value.provenance.source_url,
      sourceRecordId: value.provenance.source_record_id,
      tradeDate: value.provenance.trade_date,
      metricKey: value.provenance.metric_key,
    },
  };
}

function mapCoverageSection(value: ApiMarketSignalCoverageSection): MarketSignalCoverageSection {
  return {
    key: value.key,
    label: value.label,
    status: value.status,
    sourceName: value.source_name,
    updatedAt: value.updated_at,
  };
}

function mapSourceCoverage(value: ApiMarketSignalSourceCoverage): MarketSignalSourceCoverage {
  return {
    tradeDate: value.trade_date,
    state: value.state,
    coverageRatio: value.coverage_ratio,
    label: value.label,
    sourceNames: value.source_names,
    sections: value.sections.map(mapCoverageSection),
  };
}

function emptyCard(key: string, title: string): MarketSignalSummary["cards"][number] {
  return {
    key,
    title,
    tone: "neutral",
    interpretationLine: "데이터가 아직 준비되지 않았습니다.",
    detailText: null,
    trendBadge: null,
    sourceCoverage: {
      state: "missing",
      coverageRatio: 0,
      label: "소스 0/3",
      sourceNames: [],
    },
    supportingMetrics: [
      {
        key: `${key}-metric-1`,
        label: "핵심 지표 1",
        rawValue: null,
        formattedValue: "-",
        provenance: {
          sourceTable: null,
          sourceName: null,
          sourceUrl: null,
          sourceRecordId: null,
          tradeDate: null,
          metricKey: null,
        },
      },
      {
        key: `${key}-metric-2`,
        label: "핵심 지표 2",
        rawValue: null,
        formattedValue: "-",
        provenance: {
          sourceTable: null,
          sourceName: null,
          sourceUrl: null,
          sourceRecordId: null,
          tradeDate: null,
          metricKey: null,
        },
      },
    ],
  };
}

export function emptyMarketSignalSummary(): MarketSignalSummary {
  return {
    requestedDate: null,
    date: null,
    requestedDateAvailable: false,
    isLatestFallback: false,
    interpretationLine: "시장 신호 데이터를 아직 준비하지 못했습니다.",
    explanationText: "시장 신호 데이터를 아직 준비하지 못했습니다.",
    explanationSource: "rule_based",
    directionalBias: "neutral",
    gapBias: "flat",
    volatilityBias: "stable",
    confidenceBucket: "low",
    sourceCoverage: {
      tradeDate: null,
      state: "missing",
      coverageRatio: 0,
      label: "소스 0/6",
      sourceNames: [],
      sections: [],
    },
    cards: [
      emptyCard("today_conclusion", "오늘 시장 결론"),
      emptyCard("fund_flow", "자금 흐름"),
      emptyCard("futures_options", "선물·옵션 신호"),
      emptyCard("checkpoints", "오늘 체크포인트"),
    ],
    lastUpdatedAt: null,
    missingFields: [],
  };
}

function mapSummary(value: ApiMarketSignalSummary): MarketSignalSummary {
  return {
    requestedDate: value.requested_date,
    date: value.date,
    requestedDateAvailable: value.requested_date_available,
    isLatestFallback: value.is_latest_fallback,
    interpretationLine: value.interpretation_line,
    explanationText: value.explanation_text,
    explanationSource: value.explanation_source,
    directionalBias: value.directional_bias,
    gapBias: value.gap_bias,
    volatilityBias: value.volatility_bias,
    confidenceBucket: value.confidence_bucket,
    sourceCoverage: mapSourceCoverage(value.source_coverage),
    cards: value.cards.map((card) => ({
      key: card.key,
      title: card.title,
      tone: card.tone,
      interpretationLine: card.interpretation_line,
      detailText: card.detail_text,
      trendBadge: mapTrendBadge(card.trend_badge),
      sourceCoverage: {
        state: card.source_coverage.state,
        coverageRatio: card.source_coverage.coverage_ratio,
        label: card.source_coverage.label,
        sourceNames: card.source_coverage.source_names,
      },
      supportingMetrics: card.supporting_metrics.map(mapMetric),
    })),
    lastUpdatedAt: value.last_updated_at,
    missingFields: value.missing_fields,
  };
}

export async function getMarketSignalSummary(date?: string): Promise<MarketSignalSummary> {
  const suffix = date ? `?date=${encodeURIComponent(date)}` : "";
  try {
    const response = await getKrxJson<ApiItemResponse<ApiMarketSignalSummary>>(
      `/market-signal/summary${suffix}`,
    );
    return mapSummary(response.item);
  } catch {
    return emptyMarketSignalSummary();
  }
}
