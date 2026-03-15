import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KrxHomePage from "@/app/krx/page";
import {
  emptyDerivativesInvestorFlow,
  emptyDerivativesSummary,
  emptyDerivativesTrends,
} from "@/krx/derivatives/server/data-service";
import { emptyMarketSignalSummary } from "@/krx/market-signal/server/data-service";
import { getMarketSignalTabData } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getMarketSignalTabData: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

function buildMarketSignalFixture() {
  const summary = emptyMarketSignalSummary();
  summary.interpretationLine = "큰손들의 베팅은 지금 상방 쪽으로 함께 기울고 있습니다.";
  summary.explanationText = "저장된 시장 신호와 규칙 기반 해석을 결합한 테스트 요약입니다.";
  summary.cards = [
    {
      key: "today_conclusion",
      title: "오늘 시장 결론",
      tone: "positive",
      interpretationLine: "상방 쪽 정합성이 높아진 구간입니다.",
      detailText: "외국인 현물과 선물 방향이 함께 개선됐습니다.",
      trendBadge: { label: "상방 신호 강화", tone: "positive" },
      sourceCoverage: { state: "full", coverageRatio: 1, label: "소스 3/3", sourceNames: ["KIS_MARKET_BREADTH", "KRX_DERIVATIVES_REFERENCE"] },
      supportingMetrics: [
        {
          key: "spot",
          label: "외국인+기관 현물",
          rawValue: 4600,
          formattedValue: "+4,600",
          provenance: {
            sourceTable: "market_daily_factors",
            sourceName: "KIS_MARKET_BREADTH",
            sourceUrl: "https://kis.mock",
            sourceRecordId: "spot-1",
            tradeDate: "2026-03-09",
            metricKey: "investor_foreign_net_buy/investor_institution_net_buy",
          },
        },
        {
          key: "futures",
          label: "외국인 선물",
          rawValue: 1800,
          formattedValue: "+1,800",
          provenance: {
            sourceTable: "derivatives_daily_metrics",
            sourceName: "KRX_DERIVATIVES_REFERENCE",
            sourceUrl: "https://krx.mock",
            sourceRecordId: "fut-1",
            tradeDate: "2026-03-09",
            metricKey: "futures_investor_foreign_net_buy",
          },
        },
      ],
    },
    {
      key: "fund_flow",
      title: "자금 흐름",
      tone: "positive",
      interpretationLine: "외국인·기관 유입이 우세합니다.",
      detailText: null,
      trendBadge: { label: "유입 강화", tone: "positive" },
      sourceCoverage: { state: "full", coverageRatio: 1, label: "소스 3/3", sourceNames: ["KIS_MARKET_BREADTH"] },
      supportingMetrics: [
        {
          key: "foreign",
          label: "외국인",
          rawValue: 3400,
          formattedValue: "+3,400",
          provenance: {
            sourceTable: "market_daily_factors",
            sourceName: "KIS_MARKET_BREADTH",
            sourceUrl: "https://kis.mock",
            sourceRecordId: "foreign-1",
            tradeDate: "2026-03-09",
            metricKey: "investor_foreign_net_buy",
          },
        },
      ],
    },
    {
      key: "futures_options",
      title: "선물·옵션 신호",
      tone: "positive",
      interpretationLine: "파생 상방 우위가 유지됩니다.",
      detailText: null,
      trendBadge: { label: "콜 우위 강화", tone: "positive" },
      sourceCoverage: { state: "full", coverageRatio: 1, label: "소스 3/3", sourceNames: ["KRX_DERIVATIVES_REFERENCE", "KIS_NIGHT_FUTURES"] },
      supportingMetrics: [
        {
          key: "pcr",
          label: "PCR",
          rawValue: 0.91,
          formattedValue: "0.91",
          provenance: {
            sourceTable: "derivatives_daily_metrics",
            sourceName: "KRX_DERIVATIVES_REFERENCE",
            sourceUrl: "https://krx.mock",
            sourceRecordId: "pcr-1",
            tradeDate: "2026-03-09",
            metricKey: "put_call_ratio",
          },
        },
      ],
    },
    {
      key: "checkpoints",
      title: "오늘 체크포인트",
      tone: "neutral",
      interpretationLine: "프로그램 수급 지속 여부를 먼저 확인해야 합니다.",
      detailText: null,
      trendBadge: { label: "정상 체크", tone: "neutral" },
      sourceCoverage: { state: "partial", coverageRatio: 0.8, label: "소스 4/5", sourceNames: ["MARKET_BRIEFINGS"] },
      supportingMetrics: [
        {
          key: "top",
          label: "최대 압력",
          rawValue: "Put/Call 비율 압력",
          formattedValue: "Put/Call 비율 압력",
          provenance: {
            sourceTable: "market_signal_components",
            sourceName: "MARKET_BRIEFINGS",
            sourceUrl: null,
            sourceRecordId: "component-1",
            tradeDate: "2026-03-09",
            metricKey: "put_call_ratio",
          },
        },
      ],
    },
  ];
  summary.lastUpdatedAt = "2026-03-09T08:30:00Z";
  summary.sourceCoverage = {
    tradeDate: "2026-03-09",
    state: "partial",
    coverageRatio: 0.83,
    label: "소스 5/6",
    sourceNames: ["KIS_MARKET_BREADTH", "KRX_DERIVATIVES_REFERENCE", "MARKET_BRIEFINGS"],
    sections: [],
  };

  const derivativesSummary = emptyDerivativesSummary();
  derivativesSummary.date = "2026-03-09";
  derivativesSummary.sourceCoverage = {
    tradeDate: "2026-03-09",
    state: "partial",
    coverageRatio: 0.8,
    label: "소스 4/5",
    sourceNames: ["KRX_DERIVATIVES_REFERENCE", "KIS_NIGHT_FUTURES"],
    sections: [],
  };
  derivativesSummary.pcr = 0.91;
  derivativesSummary.pcrChange = -1.8;
  derivativesSummary.callOpenInterest = 560000;
  derivativesSummary.putOpenInterest = 480000;
  derivativesSummary.oiChange = 3.2;
  derivativesSummary.foreignFuturesNetPosition = 1800;
  derivativesSummary.nightFutures.changeRate = 0.61;
  derivativesSummary.impliedVolatility = 17.4;
  derivativesSummary.impliedVolatilityChange = -2.1;
  derivativesSummary.directionalBias = "bullish";
  derivativesSummary.gapBias = "gap_up";
  derivativesSummary.volatilityBias = "stable";
  derivativesSummary.confidenceBucket = "high";
  derivativesSummary.explanationText = "파생 지표는 상방 우위지만 변동성 재확대 여부를 함께 점검해야 합니다.";

  const derivativesTrends = emptyDerivativesTrends();
  derivativesTrends.items = [
    { date: "2026-03-07", pcr: 1.01, callOpenInterest: 490000, putOpenInterest: 500000, openInterestTotal: 990000, impliedVolatility: 20.1, sourceName: "KRX_DERIVATIVES_REFERENCE" },
    { date: "2026-03-08", pcr: 0.98, callOpenInterest: 505000, putOpenInterest: 495000, openInterestTotal: 1000000, impliedVolatility: 19.3, sourceName: "KRX_DERIVATIVES_REFERENCE" },
    { date: "2026-03-09", pcr: 0.91, callOpenInterest: 560000, putOpenInterest: 480000, openInterestTotal: 1040000, impliedVolatility: 17.4, sourceName: "KRX_DERIVATIVES_REFERENCE" },
  ];

  const derivativesInvestorFlow = emptyDerivativesInvestorFlow();
  derivativesInvestorFlow.items = [
    { date: "2026-03-07", futuresForeignNetBuy: 200, futuresInstitutionNetBuy: -120, futuresIndividualNetBuy: -80, optionsForeignNetBuy: 80, optionsInstitutionNetBuy: -20, optionsIndividualNetBuy: -60, sourceName: "KRX_DERIVATIVES_REFERENCE" },
    { date: "2026-03-08", futuresForeignNetBuy: 600, futuresInstitutionNetBuy: -200, futuresIndividualNetBuy: -400, optionsForeignNetBuy: 120, optionsInstitutionNetBuy: -30, optionsIndividualNetBuy: -90, sourceName: "KRX_DERIVATIVES_REFERENCE" },
    { date: "2026-03-09", futuresForeignNetBuy: 1800, futuresInstitutionNetBuy: 900, futuresIndividualNetBuy: -2700, optionsForeignNetBuy: 300, optionsInstitutionNetBuy: -50, optionsIndividualNetBuy: -250, sourceName: "KRX_DERIVATIVES_REFERENCE" },
  ];

  return {
    summary,
    derivativesSummary,
    derivativesTrends,
    derivativesInvestorFlow,
  };
}

describe("krx market signal page route", () => {
  it("renders flat market signal subtabs with 종합 default", async () => {
    vi.mocked(getMarketSignalTabData).mockResolvedValue(buildMarketSignalFixture());

    const component = await KrxHomePage();
    render(component);

    expect(screen.getByRole("tab", { name: "종합" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "자금 흐름" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "파생상품" })).toHaveAttribute("href", "/krx?subtab=derivatives");
    expect(screen.getByRole("tab", { name: "체크포인트" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "홈" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "세부" })).not.toBeInTheDocument();
    expect(screen.getByText("오늘 시장 결론")).toBeInTheDocument();
    expect(screen.getAllByText("KIS 수급").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("KRX 파생 기준").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("시장 브리핑").length).toBeGreaterThanOrEqual(1);
  });

  it("supports direct deep-link navigation to 시장 신호 > 파생", async () => {
    vi.mocked(getMarketSignalTabData).mockResolvedValue(buildMarketSignalFixture());

    const component = await KrxHomePage({
      searchParams: Promise.resolve({ subtab: "derivatives" }),
    });
    render(component);

    expect(screen.getByRole("tab", { name: "파생상품" })).toHaveAttribute("href", "/krx?subtab=derivatives");
    expect(screen.getByText("파생 한줄 결론")).toBeInTheDocument();
    expect(screen.getByText("핵심 파생 카드")).toBeInTheDocument();
    expect(screen.getByText("추이 차트")).toBeInTheDocument();
    expect(screen.getByText("세부 지표")).toBeInTheDocument();
    expect(screen.getByText("해설")).toBeInTheDocument();
    expect(screen.getByText("KIS 야간선물")).toBeInTheDocument();
    expect(screen.queryByText("오늘 시장 결론")).not.toBeInTheDocument();
  });

  it("renders derivatives tab gracefully even with partial data and user-facing empty copy", async () => {
    const fixture = buildMarketSignalFixture();
    fixture.derivativesSummary = emptyDerivativesSummary();
    fixture.derivativesTrends = emptyDerivativesTrends();
    fixture.derivativesInvestorFlow = emptyDerivativesInvestorFlow();
    fixture.summary.cards = fixture.summary.cards.filter((card) => card.key !== "futures_options");
    vi.mocked(getMarketSignalTabData).mockResolvedValue(fixture);

    const component = await KrxHomePage({
      searchParams: Promise.resolve({ subtab: "derivatives" }),
    });
    render(component);

    expect(screen.getByText("파생 한줄 결론")).toBeInTheDocument();
    expect(screen.getAllByText("추이 데이터를 아직 준비하지 못했습니다").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/sync/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cli/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/backfill/i)).not.toBeInTheDocument();
  });
});
