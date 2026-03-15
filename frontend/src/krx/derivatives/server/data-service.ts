import { ApiItemResponse, getKrxJson, KRX_SHORT_REVALIDATE_SECONDS } from "@/krx/server/client";
import {
  DerivativesComponent,
  DerivativesConfidenceBucket,
  DerivativesInvestorFlow,
  DerivativesSummary,
  DerivativesTrends,
} from "@/krx/types/domain";

type ApiDerivativesCoverageSection = {
  key: string;
  label: string;
  status: "available" | "missing" | "rule_based";
  source_name: string | null;
  updated_at: string | null;
};

type ApiDerivativesSourceCoverage = {
  trade_date: string | null;
  coverage_ratio: number;
  sections: ApiDerivativesCoverageSection[];
  source_names: string[];
};

type ApiDerivativesSummary = {
  requested_date: string | null;
  date: string | null;
  requested_date_available: boolean;
  is_latest_fallback: boolean;
  source_coverage: ApiDerivativesSourceCoverage;
  pcr: number | null;
  pcr_change: number | null;
  call_notional: number | null;
  put_notional: number | null;
  call_open_interest: number | null;
  put_open_interest: number | null;
  open_interest_total: number | null;
  oi_change: number | null;
  foreign_futures_net_position: number | null;
  implied_volatility: number | null;
  implied_volatility_change: number | null;
  directional_bias: "bullish" | "bearish" | "neutral";
  gap_bias: "gap_up" | "gap_down" | "flat";
  volatility_bias: "rising" | "stable" | "falling";
  confidence_bucket: DerivativesConfidenceBucket;
  explanation_text: string;
  briefing_source: "market_briefings" | "rule_based";
  participant_summary:
    | {
        participant: string;
        futures_net_buy: number | null;
        options_net_buy: number | null;
      }[]
    | null;
  detail_level: number;
  components: Array<{
    component_key?: string | null;
    component_label?: string | null;
    component_group?: string | null;
    raw_value?: unknown;
    score?: number | null;
    explanation_ko?: string | null;
    source_table?: string | null;
    source_name?: string | null;
    source_url?: string | null;
    source_record_id?: string | null;
    source_metric_key?: string | null;
    data_available?: boolean | number | null;
  }> | null;
  last_updated_at: string | null;
  missing_fields: string[];
  night_futures: {
    signal: "gap_up" | "gap_down" | "flat" | null;
    change_rate: number | null;
    price: number | null;
    price_change: number | null;
    instrument_code: string | null;
    instrument_name: string | null;
    snapshot_time: string | null;
    source_name: string | null;
    source_url: string | null;
  };
};

type ApiDerivativesTrends = {
  preset: string;
  date: string | null;
  items: Array<{
    date: string | null;
    pcr: number | null;
    call_open_interest: number | null;
    put_open_interest: number | null;
    open_interest_total: number | null;
    implied_volatility: number | null;
    source_name: string | null;
  }>;
  missing_fields: string[];
};

type ApiDerivativesInvestorFlow = {
  preset: string;
  date: string | null;
  items: Array<{
    date: string | null;
    futures_foreign_net_buy: number | null;
    futures_institution_net_buy: number | null;
    futures_individual_net_buy: number | null;
    options_foreign_net_buy: number | null;
    options_institution_net_buy: number | null;
    options_individual_net_buy: number | null;
    source_name: string | null;
  }>;
  missing_fields: string[];
};

function coverageState(ratio: number): "full" | "partial" | "missing" {
  if (ratio >= 0.9999) return "full";
  if (ratio > 0) return "partial";
  return "missing";
}

function mapComponent(value: NonNullable<ApiDerivativesSummary["components"]>[number]): DerivativesComponent {
  return {
    componentKey: value.component_key ?? "unknown_component",
    componentLabel: value.component_label ?? "지표 해석",
    componentGroup: value.component_group ?? null,
    rawValue: value.raw_value,
    score: value.score ?? null,
    explanationKo: value.explanation_ko ?? null,
    sourceTable: value.source_table ?? null,
    sourceName: value.source_name ?? null,
    sourceUrl: value.source_url ?? null,
    sourceRecordId: value.source_record_id ?? null,
    sourceMetricKey: value.source_metric_key ?? null,
    dataAvailable: Boolean(value.data_available),
  };
}

function mapSummary(item: ApiDerivativesSummary): DerivativesSummary {
  const sections = item.source_coverage.sections.map((section) => ({
    key: section.key,
    label: section.label,
    status: section.status,
    sourceName: section.source_name,
    updatedAt: section.updated_at,
  }));
  const availableCount = sections.filter((section) => section.status === "available" || section.status === "rule_based").length;
  const expectedCount = sections.length || 1;
  const label = `소스 ${availableCount}/${expectedCount}`;

  return {
    requestedDate: item.requested_date,
    date: item.date,
    requestedDateAvailable: item.requested_date_available,
    isLatestFallback: item.is_latest_fallback,
    sourceCoverage: {
      tradeDate: item.source_coverage.trade_date,
      coverageRatio: item.source_coverage.coverage_ratio,
      state: coverageState(item.source_coverage.coverage_ratio),
      label,
      sourceNames: item.source_coverage.source_names,
      sections,
    },
    pcr: item.pcr,
    pcrChange: item.pcr_change,
    callNotional: item.call_notional,
    putNotional: item.put_notional,
    callOpenInterest: item.call_open_interest,
    putOpenInterest: item.put_open_interest,
    openInterestTotal: item.open_interest_total,
    oiChange: item.oi_change,
    foreignFuturesNetPosition: item.foreign_futures_net_position,
    impliedVolatility: item.implied_volatility,
    impliedVolatilityChange: item.implied_volatility_change,
    directionalBias: item.directional_bias,
    gapBias: item.gap_bias,
    volatilityBias: item.volatility_bias,
    confidenceBucket: item.confidence_bucket,
    explanationText: item.explanation_text,
    briefingSource: item.briefing_source,
    participantSummary: (item.participant_summary ?? []).map((participant) => ({
      participant: participant.participant,
      futuresNetBuy: participant.futures_net_buy,
      optionsNetBuy: participant.options_net_buy,
    })),
    detailLevel: item.detail_level,
    components: (item.components ?? []).map(mapComponent),
    lastUpdatedAt: item.last_updated_at,
    missingFields: item.missing_fields,
    nightFutures: {
      signal: item.night_futures.signal,
      changeRate: item.night_futures.change_rate,
      price: item.night_futures.price,
      priceChange: item.night_futures.price_change,
      instrumentCode: item.night_futures.instrument_code,
      instrumentName: item.night_futures.instrument_name,
      snapshotTime: item.night_futures.snapshot_time,
      sourceName: item.night_futures.source_name,
      sourceUrl: item.night_futures.source_url,
    },
  };
}

function mapTrends(item: ApiDerivativesTrends): DerivativesTrends {
  return {
    preset: item.preset,
    date: item.date,
    items: item.items
      .filter((trend) => Boolean(trend.date))
      .map((trend) => ({
        date: String(trend.date),
        pcr: trend.pcr,
        callOpenInterest: trend.call_open_interest,
        putOpenInterest: trend.put_open_interest,
        openInterestTotal: trend.open_interest_total,
        impliedVolatility: trend.implied_volatility,
        sourceName: trend.source_name,
      })),
    missingFields: item.missing_fields,
  };
}

function mapInvestorFlow(item: ApiDerivativesInvestorFlow): DerivativesInvestorFlow {
  return {
    preset: item.preset,
    date: item.date,
    items: item.items
      .filter((flow) => Boolean(flow.date))
      .map((flow) => ({
        date: String(flow.date),
        futuresForeignNetBuy: flow.futures_foreign_net_buy,
        futuresInstitutionNetBuy: flow.futures_institution_net_buy,
        futuresIndividualNetBuy: flow.futures_individual_net_buy,
        optionsForeignNetBuy: flow.options_foreign_net_buy,
        optionsInstitutionNetBuy: flow.options_institution_net_buy,
        optionsIndividualNetBuy: flow.options_individual_net_buy,
        sourceName: flow.source_name,
      })),
    missingFields: item.missing_fields,
  };
}

export function emptyDerivativesSummary(): DerivativesSummary {
  return {
    requestedDate: null,
    date: null,
    requestedDateAvailable: false,
    isLatestFallback: false,
    sourceCoverage: {
      tradeDate: null,
      coverageRatio: 0,
      state: "missing",
      label: "소스 0/5",
      sourceNames: [],
      sections: [],
    },
    pcr: null,
    pcrChange: null,
    callNotional: null,
    putNotional: null,
    callOpenInterest: null,
    putOpenInterest: null,
    openInterestTotal: null,
    oiChange: null,
    foreignFuturesNetPosition: null,
    impliedVolatility: null,
    impliedVolatilityChange: null,
    directionalBias: "neutral",
    gapBias: "flat",
    volatilityBias: "stable",
    confidenceBucket: "low",
    explanationText: "파생 지표가 아직 준비되지 않아 규칙 기반 해석을 생성하지 못했습니다.",
    briefingSource: "rule_based",
    participantSummary: [],
    detailLevel: 0,
    components: [],
    lastUpdatedAt: null,
    missingFields: [],
    nightFutures: {
      signal: null,
      changeRate: null,
      price: null,
      priceChange: null,
      instrumentCode: null,
      instrumentName: null,
      snapshotTime: null,
      sourceName: null,
      sourceUrl: null,
    },
  };
}

export function emptyDerivativesTrends(): DerivativesTrends {
  return {
    preset: "20d",
    date: null,
    items: [],
    missingFields: ["pcr", "call_open_interest", "put_open_interest", "implied_volatility"],
  };
}

export function emptyDerivativesInvestorFlow(): DerivativesInvestorFlow {
  return {
    preset: "20d",
    date: null,
    items: [],
    missingFields: ["futures_investor_foreign_net_buy", "options_investor_foreign_net_buy"],
  };
}

export async function getDerivativesSummary(date?: string): Promise<DerivativesSummary> {
  const suffix = date ? `?date=${encodeURIComponent(date)}` : "";
  try {
    const response = await getKrxJson<ApiItemResponse<ApiDerivativesSummary>>(`/derivatives/summary${suffix}`, {
      revalidate: KRX_SHORT_REVALIDATE_SECONDS,
    });
    return mapSummary(response.item);
  } catch {
    return emptyDerivativesSummary();
  }
}

export async function getDerivativesTrends(
  preset: string = "20d",
  date?: string,
): Promise<DerivativesTrends> {
  const params = new URLSearchParams({ preset });
  if (date) {
    params.set("date", date);
  }
  try {
    const response = await getKrxJson<ApiDerivativesTrends>(`/derivatives/trends?${params.toString()}`, {
      revalidate: KRX_SHORT_REVALIDATE_SECONDS,
    });
    return mapTrends(response);
  } catch {
    return emptyDerivativesTrends();
  }
}

export async function getDerivativesInvestorFlow(
  preset: string = "20d",
  date?: string,
): Promise<DerivativesInvestorFlow> {
  const params = new URLSearchParams({ preset });
  if (date) {
    params.set("date", date);
  }
  try {
    const response = await getKrxJson<ApiDerivativesInvestorFlow>(`/derivatives/investor-flow?${params.toString()}`, {
      revalidate: KRX_SHORT_REVALIDATE_SECONDS,
    });
    return mapInvestorFlow(response);
  } catch {
    return emptyDerivativesInvestorFlow();
  }
}
