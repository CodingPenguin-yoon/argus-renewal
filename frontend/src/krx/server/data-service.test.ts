import { beforeEach, describe, expect, it, vi } from "vitest";

import { KRX_SHORT_REVALIDATE_SECONDS } from "@/krx/server/client";
import { getMarketNewsCards, getMarketNewsDashboard } from "@/krx/news/server/data-service";
import { getGlobalEventsDashboardData } from "@/krx/global-events/server/data-service";
import { getMarketSignalSummary } from "@/krx/market-signal/server/data-service";
import { getMacroNews } from "@/krx/news/server/data-service";
import { getDerivativesInvestorFlow, getDerivativesSummary, getDerivativesTrends } from "@/krx/derivatives/server/data-service";
import { getMacroTabData, getNewsTabData, getOverviewTabData } from "@/krx/server/data-service";
import type { MarketNewsCard, NewsTabData } from "@/krx/types/domain";

vi.mock("@/krx/news/server/data-service", () => ({
  emptyMarketNewsBriefing: vi.fn(() => ({
    headline: "실시간 시장 브리핑 준비 중",
    summary: "표시 가능한 시장 이벤트가 아직 준비되지 않았습니다. 새 뉴스가 들어오면 이 영역에서 핵심 흐름을 요약합니다.",
    keyPoints: [],
    linkedHeadlines: [],
    updatedAt: null,
    generationMethod: "rule_based",
    aiConfidence: 0,
    aiProvider: null,
    aiModel: null,
  })),
  emptyMarketNewsCoverage: vi.fn(() => ({
    state: "empty",
    coverageRatio: 0,
    availableSources: 0,
    expectedSources: 4,
    summary: "뉴스 소스가 아직 준비되지 않았습니다.",
    updatedAt: null,
    items: [],
  })),
  emptyMarketNewsHeaderContext: vi.fn(() => ({
    updatedAt: null,
    summaryLine: "표시 가능한 이벤트 카드가 아직 준비되지 않았습니다.",
    coverage: {
      state: "empty",
      coverageRatio: 0,
      availableSources: 0,
      expectedSources: 4,
      summary: "뉴스 소스가 아직 준비되지 않았습니다.",
    },
    columns: [
      { key: "KR", label: "한국 증시", count: 0, leadTitle: null, leadScope: null },
      { key: "GLOBAL", label: "글로벌 증시", count: 0, leadTitle: null, leadScope: null },
    ],
  })),
  getAllNews: vi.fn(),
  getMacroNews: vi.fn(),
  getNewsByTicker: vi.fn(),
  getNewsDetail: vi.fn(),
  getMarketNewsDashboard: vi.fn(),
  getMarketNewsCards: vi.fn(),
}));

vi.mock("@/krx/lib/env", () => ({
  env: {
    BACKEND_BASE_URL: "http://localhost:4000",
  },
}));

vi.mock("@/krx/global-events/server/data-service", () => ({
  getGlobalEventsDashboardData: vi.fn(),
}));

vi.mock("@/krx/derivatives/server/data-service", () => ({
  getDerivativesInvestorFlow: vi.fn(),
  getDerivativesSummary: vi.fn(),
  getDerivativesTrends: vi.fn(),
}));

vi.mock("@/krx/market-signal/server/data-service", () => ({
  getMarketSignalSummary: vi.fn(),
}));

vi.mock("@/krx/market/server/data-service", () => ({
  getAllStocks: vi.fn(),
  getStockByTicker: vi.fn(),
}));

function buildCard({
  id,
  title,
  updatedAt,
  publishedAt = updatedAt,
  importanceLabel = "high",
  rankingScore,
}: {
  id: string;
  title: string;
  updatedAt: string | null;
  publishedAt?: string | null;
  importanceLabel?: MarketNewsCard["importanceLabel"];
  rankingScore: number;
}): MarketNewsCard {
  return {
    id,
    title,
    oneLineSummary: `${title} 요약`,
    whyItMatters: `${title} 중요성`,
    marketImpact: `${title} 영향`,
    marketScope: "kr_market",
    primaryRegion: "KR",
    trustScore: 0.8,
    materialityScore: 0.7,
    noveltyScore: 0.6,
    attentionScore: 0.5,
    editorialScore: 0.75,
    storyState: "ONGOING",
    importanceLabel,
    editorialReason: null,
    aiConfidence: 0.7,
    rankingScore,
    evidenceCount: 2,
    crossSourceScore: 0.2,
    publishedAt,
    updatedAt,
    evidence: [],
    provenance: {},
  };
}

function buildDashboardFixture(): NewsTabData {
  return {
    krCards: [],
    globalCards: [
      {
        ...buildCard({
          id: "global-2",
          title: "글로벌 2",
          updatedAt: "2026-03-15T00:01:00Z",
          rankingScore: 0.8,
        }),
        primaryRegion: "GLOBAL",
        marketScope: "global_market",
      },
      {
        ...buildCard({
          id: "global-1",
          title: "글로벌 1",
          updatedAt: "2026-03-15T00:02:00Z",
          rankingScore: 0.9,
        }),
        primaryRegion: "GLOBAL",
        marketScope: "global_market",
      },
    ],
    disclosureCards: [],
    briefing: {
      headline: "지금 시장 브리핑",
      summary: "글로벌 변수와 국내 수급을 함께 봐야 합니다.",
      keyPoints: ["글로벌 1"],
      linkedHeadlines: [
        {
          cardId: "global-1",
          title: "글로벌 1",
          summary: "글로벌 1 요약",
          marketScope: "global_market",
          primaryRegion: "GLOBAL",
          publishedAt: "2026-03-15T00:02:00Z",
          sourceUrl: "https://example.com/global-1",
          sourceLabel: "Reuters",
        },
      ],
      updatedAt: "2026-03-15T00:02:00Z",
      generationMethod: "rule_based",
      aiConfidence: 0,
      aiProvider: null,
      aiModel: null,
    },
    headerContext: {
      updatedAt: "2026-03-15T00:02:00Z",
      summaryLine: "헤더",
      coverage: {
        state: "partial",
        coverageRatio: 0.75,
        availableSources: 3,
        expectedSources: 4,
        summary: "일부 소스 반영",
      },
      columns: [
        { key: "KR", label: "한국 증시", count: 0, leadTitle: null, leadScope: null },
        { key: "GLOBAL", label: "글로벌 증시", count: 2, leadTitle: "글로벌 1", leadScope: "global_market" },
      ],
    },
    coverage: {
      state: "partial",
      coverageRatio: 0.75,
      availableSources: 3,
      expectedSources: 4,
      summary: "일부 소스 반영",
      updatedAt: "2026-03-15T00:02:00Z",
      items: [],
    },
  };
}

describe("getNewsTabData", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps summary/global cards ranking-sorted but makes KR feed recency-sorted", async () => {
    vi.mocked(getMarketNewsDashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getMarketNewsCards).mockResolvedValue([
      buildCard({
        id: "kr-ranking-top",
        title: "랭킹은 높지만 더 오래된 카드",
        updatedAt: "2026-03-15T00:01:00Z",
        rankingScore: 0.99,
      }),
      buildCard({
        id: "kr-latest",
        title: "조금 덜 중요하지만 더 최신 카드",
        updatedAt: "2026-03-15T00:05:00Z",
        rankingScore: 0.7,
      }),
    ]);

    const result = await getNewsTabData();

    expect(result.krCards.map((card) => card.id)).toEqual(["kr-latest", "kr-ranking-top"]);
    expect(result.globalCards.map((card) => card.id)).toEqual(["global-1", "global-2"]);
    expect(result.briefing.headline).toBe("지금 시장 브리핑");
  });

  it("keeps lower-importance KR cards in the feed when they are newer", async () => {
    vi.mocked(getMarketNewsDashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getMarketNewsCards).mockResolvedValue([
      buildCard({
        id: "kr-high-older",
        title: "높은 중요도 오래된 카드",
        updatedAt: "2026-03-15T00:01:00Z",
        importanceLabel: "high",
        rankingScore: 0.9,
      }),
      buildCard({
        id: "kr-low-latest",
        title: "낮은 중요도 최신 카드",
        updatedAt: "2026-03-15T00:03:00Z",
        importanceLabel: "low",
        rankingScore: 0.8,
      }),
    ]);

    const result = await getNewsTabData();

    expect(result.krCards.map((card) => card.id)).toEqual(["kr-low-latest", "kr-high-older"]);
  });
});

describe("overview and macro aggregators", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it("builds app-wide overview data from existing tab services", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: null,
        items: [],
        coverage: {
          state: "empty",
          available_items: 0,
          expected_items: 4,
          provider: "disabled",
          summary: "disabled",
          note: "feature_flag_disabled",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const marketSignalSummary = {
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      interpretationLine: "시장 톤은 상방 쪽으로 기울고 있습니다.",
      explanationText: "수급과 파생을 함께 보면 상방 정합성이 높습니다.",
      explanationSource: "rule_based" as const,
      directionalBias: "bullish" as const,
      gapBias: "gap_up" as const,
      volatilityBias: "stable" as const,
      confidenceBucket: "high" as const,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        state: "full" as const,
        coverageRatio: 1,
        label: "소스 6/6",
        sourceNames: ["MARKET_BRIEFINGS"],
        sections: [],
      },
      cards: [
        {
          key: "today_conclusion",
          title: "오늘 시장 결론",
          tone: "positive" as const,
          interpretationLine: "외국인 선물과 현물이 같은 방향입니다.",
          detailText: null,
          trendBadge: null,
          sourceCoverage: {
            state: "full" as const,
            coverageRatio: 1,
            label: "소스 3/3",
            sourceNames: ["MARKET_BRIEFINGS"],
          },
          supportingMetrics: [],
        },
      ],
      lastUpdatedAt: "2026-03-15T01:10:00Z",
      missingFields: [],
    };

    vi.mocked(getMarketSignalSummary).mockResolvedValue(marketSignalSummary);
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 5/5",
        sourceNames: ["KRX_DERIVATIVES_REFERENCE"],
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
      explanationText: "파생 요약 대기",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: null,
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });
    vi.mocked(getMarketNewsDashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getMarketNewsCards).mockResolvedValue([
      buildCard({
        id: "kr-latest",
        title: "최신 KR 카드",
        updatedAt: "2026-03-15T00:05:00Z",
        rankingScore: 0.7,
      }),
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [
        {
          id: "event-1",
          eventKey: "fed-1",
          title: "연준 발언",
          eventType: "speech",
          category: "rates",
          country: "미국",
          status: "published",
          importance: "high",
          importanceSource: "rule",
          eventDateKst: "2026-03-15",
          eventTimeKst: "2026-03-15T00:40:00Z",
          eventTimePrecision: "time",
          previousEventTimeKst: null,
          revisionNote: null,
          whyItMattersKo: "달러와 위험선호에 연결됩니다.",
          source: { key: "fed", name: "Fed", url: null, updatedAt: "2026-03-15T00:40:00Z" },
          release: {
            metricCode: null,
            state: "released",
            unit: null,
            previous: null,
            forecast: null,
            actual: null,
            surprise: null,
            previousValue: null,
            forecastValue: null,
            actualValue: null,
            surpriseValue: null,
            sourceName: null,
            sourceUrl: null,
            sourceRecordId: null,
            actualReleasedAt: null,
          },
          impact: null,
          provenance: {},
          updatedAt: "2026-03-15T00:40:00Z",
        },
      ],
      upcoming: [],
      week: [],
      coverage: {
        state: "partial",
        coverageRatio: 0.5,
        availableSources: 1,
        expectedSources: 2,
        summary: "일부 반영",
        updatedAt: "2026-03-15T00:40:00Z",
        items: [],
      },
    });
    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "요약",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:05:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "요약",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
      {
        id: "macro-rates",
        type: "macro",
        title: "미 10년물 금리 보합",
        summary: "요약",
        whyItMatters: "장기 금리 부담이 진정되는지 확인해야 합니다.",
        source: "연준 모니터",
        sourceUrl: "https://example.com/rates",
        publishedAt: "2026-03-15T00:55:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "neutral",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "금리",
        tags: [],
      },
    ]);

    const result = await getOverviewTabData();

    expect(getMacroNews).toHaveBeenCalledWith({ revalidate: KRX_SHORT_REVALIDATE_SECONDS });
    expect(result.macroWidgets.map((item) => item.label)).toEqual(["환율", "WTI·에너지", "금리"]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/macro-reference/cards", {
      next: { revalidate: 3600 },
    });
    expect(result.marketToneLine).toContain("상방");
    expect(result.gatewayPanels.map((item) => item.title)).toEqual(["파생·수급", "시장 뉴스", "매크로 캘린더"]);
    expect(result.reportLinks[0]?.title).toBe("글로벌 1");
    expect(result.globalHighlights[0]?.title).toBe("연준 발언");
  });

  it("uses FRED cards for overview macro widgets even if backend order changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: "2026-03-15T01:10:00Z",
        items: [
          {
            key: "wti",
            label: "WTI·에너지",
            summary: "WTI·에너지 $67.55/bbl · 2026-03-15 기준",
            value: 67.55,
            value_display: "$67.55/bbl",
            change_value: 1.45,
            change_display: "+$1.45/bbl",
            unit: "usd_per_barrel",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              url: "https://fred.stlouisfed.org/series/DCOILWTICO",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              semantics: "daily_spot_price_usd_per_barrel",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "fedfunds",
            label: "연방기금실효금리(월평균)",
            summary: "연방기금실효금리(월평균) 4.33% · 2026-03-01 기준",
            value: 4.33,
            value_display: "4.33%",
            change_value: 0,
            change_display: "0.00%p",
            unit: "pct",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              url: "https://fred.stlouisfed.org/series/FEDFUNDS",
              observed_at: "2026-03-01",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-01",
              age_seconds: 0,
              ttl_seconds: 3888000,
            },
            metadata: {
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              semantics: "monthly_average_effective_federal_funds_rate_percent",
              frequency: "monthly",
              freshness_ttl_seconds: 3888000,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "usdkrw",
            label: "환율",
            summary: "환율 1,458.30원 · 2026-03-15 기준",
            value: 1458.3,
            value_display: "1,458.30원",
            change_value: 6.2,
            change_display: "+6.20원",
            unit: "krw_per_usd",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              url: "https://fred.stlouisfed.org/series/DEXKOUS",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              semantics: "daily_spot_exchange_rate_krw_per_usd",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "us10y",
            label: "미국채 10년물",
            summary: "미국채 10년물 4.31% · 2026-03-15 기준",
            value: 4.31,
            value_display: "4.31%",
            change_value: 0.05,
            change_display: "+0.05%p",
            unit: "pct",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DGS10",
              series_name: "DGS10",
              url: "https://fred.stlouisfed.org/series/DGS10",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DGS10",
              series_name: "DGS10",
              semantics: "daily_market_yield_percent",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
        ],
        coverage: {
          state: "full",
          available_items: 4,
          expected_items: 4,
          provider: "file",
          summary: "full",
          note: null,
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMarketSignalSummary).mockResolvedValue({
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      interpretationLine: "시장 톤은 상방 쪽으로 기울고 있습니다.",
      explanationText: "수급과 파생을 함께 보면 상방 정합성이 높습니다.",
      explanationSource: "rule_based",
      directionalBias: "bullish",
      gapBias: "gap_up",
      volatilityBias: "stable",
      confidenceBucket: "high",
      sourceCoverage: {
        tradeDate: "2026-03-15",
        state: "full",
        coverageRatio: 1,
        label: "소스 6/6",
        sourceNames: ["MARKET_BRIEFINGS"],
        sections: [],
      },
      cards: [],
      lastUpdatedAt: "2026-03-15T01:10:00Z",
      missingFields: [],
    });
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 5/5",
        sourceNames: ["KRX_DERIVATIVES_REFERENCE"],
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
      explanationText: "파생 요약 대기",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: null,
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });
    vi.mocked(getMarketNewsDashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getMarketNewsCards).mockResolvedValue([
      buildCard({
        id: "kr-latest",
        title: "최신 KR 카드",
        updatedAt: "2026-03-15T00:05:00Z",
        rankingScore: 0.7,
      }),
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "partial",
        coverageRatio: 0.5,
        availableSources: 1,
        expectedSources: 2,
        summary: "일부 반영",
        updatedAt: "2026-03-15T00:40:00Z",
        items: [],
      },
    });
    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "요약",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:05:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "요약",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
    ]);

    const result = await getOverviewTabData();

    expect(result.macroWidgets.map((item) => item.label)).toEqual(["환율", "WTI·에너지", "미국채 10년물"]);
    expect(result.macroWidgets.every((item) => item.sourceLabel === "FRED")).toBe(true);
    expect(result.macroWidgets[2]?.sourceLabel).toBe("FRED");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/macro-reference/cards", {
      next: { revalidate: 3600 },
    });
  });

  it("falls back to FEDFUNDS for the overview rate slot when DGS10 is missing", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: "2026-03-15T01:10:00Z",
        items: [
          {
            key: "fedfunds",
            label: "연방기금실효금리(월평균)",
            summary: "연방기금실효금리(월평균) 4.33% · 2026-03-01 기준",
            value: 4.33,
            value_display: "4.33%",
            change_value: 0,
            change_display: "0.00%p",
            unit: "pct",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              url: "https://fred.stlouisfed.org/series/FEDFUNDS",
              observed_at: "2026-03-01",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-01",
              age_seconds: 0,
              ttl_seconds: 3888000,
            },
            metadata: {
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              semantics: "monthly_average_effective_federal_funds_rate_percent",
              frequency: "monthly",
              freshness_ttl_seconds: 3888000,
              provider_mode: "file",
              retry_count: 0,
            },
          },
        ],
        coverage: {
          state: "partial",
          available_items: 1,
          expected_items: 4,
          provider: "file",
          summary: "partial",
          note: "partial_series_available",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMarketSignalSummary).mockResolvedValue({
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      interpretationLine: "시장 톤은 상방 쪽으로 기울고 있습니다.",
      explanationText: "수급과 파생을 함께 보면 상방 정합성이 높습니다.",
      explanationSource: "rule_based",
      directionalBias: "bullish",
      gapBias: "gap_up",
      volatilityBias: "stable",
      confidenceBucket: "high",
      sourceCoverage: {
        tradeDate: "2026-03-15",
        state: "full",
        coverageRatio: 1,
        label: "소스 6/6",
        sourceNames: ["MARKET_BRIEFINGS"],
        sections: [],
      },
      cards: [],
      lastUpdatedAt: "2026-03-15T01:10:00Z",
      missingFields: [],
    });
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 5/5",
        sourceNames: ["KRX_DERIVATIVES_REFERENCE"],
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
      explanationText: "파생 요약 대기",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: null,
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });
    vi.mocked(getMarketNewsDashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getMarketNewsCards).mockResolvedValue([
      buildCard({
        id: "kr-latest",
        title: "최신 KR 카드",
        updatedAt: "2026-03-15T00:05:00Z",
        rankingScore: 0.7,
      }),
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "partial",
        coverageRatio: 0.5,
        availableSources: 1,
        expectedSources: 2,
        summary: "일부 반영",
        updatedAt: "2026-03-15T00:40:00Z",
        items: [],
      },
    });
    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "요약",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:05:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "요약",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
      {
        id: "macro-rates",
        type: "macro",
        title: "국채 금리 부담",
        summary: "기존 금리 카드",
        whyItMatters: "기존 금리 카드",
        source: "Reuters",
        sourceUrl: "https://example.com/rates",
        publishedAt: "2026-03-15T00:30:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "금리",
        tags: [],
      },
    ]);

    const result = await getOverviewTabData();

    expect(result.macroWidgets.map((item) => item.label)).toEqual(["환율", "WTI·에너지", "연방기금실효금리(월평균)"]);
    expect(result.macroWidgets.map((item) => item.sourceLabel)).toEqual(["연합뉴스", "로이터", "FRED"]);
  });

  it("builds macro tab data from existing macro, derivatives, and global-event services", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: null,
        items: [],
        coverage: {
          state: "empty",
          available_items: 0,
          expected_items: 4,
          provider: "disabled",
          summary: "disabled",
          note: "feature_flag_disabled",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "요약",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "요약",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T00:50:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "partial",
        coverageRatio: 0.5,
        availableSources: 1,
        expectedSources: 2,
        summary: "일부 반영",
        updatedAt: "2026-03-15T00:40:00Z",
        items: [],
      },
    });
    const derivativesSummary = {
      requestedDate: null,
      date: "2026-03-15",
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 0.8,
        state: "partial" as const,
        label: "소스 4/5",
        sourceNames: ["KRX_DERIVATIVES_REFERENCE"],
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
      directionalBias: "bullish" as const,
      gapBias: "gap_up" as const,
      volatilityBias: "stable" as const,
      confidenceBucket: "medium" as const,
      explanationText: "파생은 상방 우위를 유지합니다.",
      briefingSource: "rule_based" as const,
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: "2026-03-15T01:20:00Z",
      missingFields: [],
      preOpenFutures: {
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
    vi.mocked(getDerivativesSummary).mockResolvedValue(derivativesSummary);
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });

    const result = await getMacroTabData();

    expect(getMacroNews).toHaveBeenCalledWith({ revalidate: KRX_SHORT_REVALIDATE_SECONDS });
    expect(result.referenceCards.map((item) => item.label)).toContain("환율");
    expect(result.referenceCards.map((item) => item.label)).toContain("WTI·에너지");
    expect(result.referenceCards.map((item) => item.label)).toContain("파생 시그널");
    expect(result.updatedAt).toBe("2026-03-15T01:20:00Z");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/macro-reference/cards", {
      next: { revalidate: 3600 },
    });
  });

  it("replaces legacy macro reference cards with FRED cards when available", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: "2026-03-15T01:10:00Z",
        items: [
          {
            key: "usdkrw",
            label: "환율",
            summary: "환율 1,458.30원 · 2026-03-15 기준",
            value: 1458.3,
            value_display: "1,458.30원",
            change_value: 6.2,
            change_display: "+6.20원",
            unit: "krw_per_usd",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              url: "https://fred.stlouisfed.org/series/DEXKOUS",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              semantics: "daily_spot_exchange_rate_krw_per_usd",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "wti",
            label: "WTI·에너지",
            summary: "WTI·에너지 $67.55/bbl · 2026-03-15 기준",
            value: 67.55,
            value_display: "$67.55/bbl",
            change_value: 1.45,
            change_display: "+$1.45/bbl",
            unit: "usd_per_barrel",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              url: "https://fred.stlouisfed.org/series/DCOILWTICO",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              semantics: "daily_spot_price_usd_per_barrel",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "us10y",
            label: "미국채 10년물",
            summary: "미국채 10년물 4.31% · 2026-03-15 기준",
            value: 4.31,
            value_display: "4.31%",
            change_value: 0.05,
            change_display: "+0.05%p",
            unit: "pct",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DGS10",
              series_name: "DGS10",
              url: "https://fred.stlouisfed.org/series/DGS10",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DGS10",
              series_name: "DGS10",
              semantics: "daily_market_yield_percent",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
          {
            key: "fedfunds",
            label: "연방기금실효금리(월평균)",
            summary: "연방기금실효금리(월평균) 4.33% · 2026-03-01 기준",
            value: 4.33,
            value_display: "4.33%",
            change_value: 0,
            change_display: "0.00%p",
            unit: "pct",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              url: "https://fred.stlouisfed.org/series/FEDFUNDS",
              observed_at: "2026-03-01",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-01",
              age_seconds: 0,
              ttl_seconds: 3888000,
            },
            metadata: {
              series_id: "FEDFUNDS",
              series_name: "FEDFUNDS",
              semantics: "monthly_average_effective_federal_funds_rate_percent",
              frequency: "monthly",
              freshness_ttl_seconds: 3888000,
              provider_mode: "file",
              retry_count: 0,
            },
          },
        ],
        coverage: {
          state: "full",
          available_items: 4,
          expected_items: 4,
          provider: "file",
          summary: "full",
          note: null,
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-rates",
        type: "macro",
        title: "국채 금리 부담",
        summary: "기존 금리 카드",
        whyItMatters: "기존 금리 카드",
        source: "Reuters",
        sourceUrl: "https://example.com/rates",
        publishedAt: "2026-03-15T00:30:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "금리",
        tags: [],
      },
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "empty",
        coverageRatio: 0,
        availableSources: 0,
        expectedSources: 0,
        summary: "없음",
        updatedAt: null,
        items: [],
      },
    });
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      tradeDate: "2026-03-15",
      requestedDate: null,
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 1/1",
        sourceNames: ["KIS"],
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
      confidenceBucket: "medium",
      explanationText: "파생 중립",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: "2026-03-15T01:20:00Z",
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });

    const result = await getMacroTabData();

    expect(result.referenceCards.map((item) => item.label)).toEqual([
      "환율",
      "WTI·에너지",
      "미국채 10년물",
      "연방기금실효금리(월평균)",
      "파생 시그널",
    ]);
  });

  it("keeps legacy fallback cards when only USD/KRW FRED is available", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: "2026-03-15T01:10:00Z",
        items: [
          {
            key: "usdkrw",
            label: "환율",
            summary: "환율 1,458.30원 · 2026-03-15 기준",
            value: 1458.3,
            value_display: "1,458.30원",
            change_value: 6.2,
            change_display: "+6.20원",
            unit: "krw_per_usd",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              url: "https://fred.stlouisfed.org/series/DEXKOUS",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DEXKOUS",
              series_name: "DEXKOUS",
              semantics: "daily_spot_exchange_rate_krw_per_usd",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
        ],
        coverage: {
          state: "partial",
          available_items: 1,
          expected_items: 4,
          provider: "file",
          summary: "partial",
          note: "partial_series_available",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "기존 환율 카드",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "기존 유가 카드",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T00:50:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
      {
        id: "macro-rates",
        type: "macro",
        title: "국채 금리 부담",
        summary: "기존 금리 카드",
        whyItMatters: "기존 금리 카드",
        source: "Reuters",
        sourceUrl: "https://example.com/rates",
        publishedAt: "2026-03-15T00:30:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "금리",
        tags: [],
      },
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "empty",
        coverageRatio: 0,
        availableSources: 0,
        expectedSources: 0,
        summary: "없음",
        updatedAt: null,
        items: [],
      },
    });
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      tradeDate: "2026-03-15",
      requestedDate: null,
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 1/1",
        sourceNames: ["KIS"],
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
      confidenceBucket: "medium",
      explanationText: "파생 중립",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: "2026-03-15T01:20:00Z",
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });

    const result = await getMacroTabData();

    expect(result.referenceCards.map((item) => item.label)).toEqual(["환율", "WTI·에너지", "금리", "파생 시그널"]);
    expect(result.referenceCards.map((item) => item.sourceLabel)).toEqual(["FRED", "로이터", "Reuters", "소스 1/1"]);
  });

  it("keeps legacy fallback cards when only WTI FRED is available", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        updated_at: "2026-03-15T01:10:00Z",
        items: [
          {
            key: "wti",
            label: "WTI·에너지",
            summary: "WTI·에너지 $67.55/bbl · 2026-03-15 기준",
            value: 67.55,
            value_display: "$67.55/bbl",
            change_value: 1.45,
            change_display: "+$1.45/bbl",
            unit: "usd_per_barrel",
            stale: false,
            source: {
              key: "FRED",
              name: "Federal Reserve Economic Data",
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              url: "https://fred.stlouisfed.org/series/DCOILWTICO",
              observed_at: "2026-03-15",
              updated_at: "2026-03-15T01:10:00Z",
            },
            freshness: {
              status: "fresh",
              observed_at: "2026-03-15",
              age_seconds: 0,
              ttl_seconds: 172800,
            },
            metadata: {
              series_id: "DCOILWTICO",
              series_name: "DCOILWTICO",
              semantics: "daily_spot_price_usd_per_barrel",
              frequency: "daily",
              freshness_ttl_seconds: 172800,
              provider_mode: "file",
              retry_count: 0,
            },
          },
        ],
        coverage: {
          state: "partial",
          available_items: 1,
          expected_items: 4,
          provider: "file",
          summary: "partial",
          note: "partial_series_available",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    vi.mocked(getMacroNews).mockResolvedValue([
      {
        id: "macro-fx",
        type: "macro",
        title: "달러 강세",
        summary: "기존 환율 카드",
        whyItMatters: "환율 부담이 커집니다.",
        source: "연합뉴스",
        sourceUrl: "https://example.com/fx",
        publishedAt: "2026-03-15T01:00:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.8,
        editorialScore: 0.8,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "high",
        relatedSectors: [],
        relatedTickers: [],
        category: "환율",
        tags: [],
      },
      {
        id: "macro-oil",
        type: "macro",
        title: "유가 반등",
        summary: "기존 유가 카드",
        whyItMatters: "에너지 비용 변수입니다.",
        source: "로이터",
        sourceUrl: "https://example.com/oil",
        publishedAt: "2026-03-15T00:50:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "NEW",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "유가/에너지",
        tags: [],
      },
      {
        id: "macro-rates",
        type: "macro",
        title: "국채 금리 부담",
        summary: "기존 금리 카드",
        whyItMatters: "기존 금리 카드",
        source: "Reuters",
        sourceUrl: "https://example.com/rates",
        publishedAt: "2026-03-15T00:30:00Z",
        credibilityScore: 0.8,
        materialityScore: 0.7,
        editorialScore: 0.7,
        storyState: "ONGOING",
        editorialReason: null,
        aiConfidence: 0.7,
        sentiment: "negative",
        importance: "medium",
        relatedSectors: [],
        relatedTickers: [],
        category: "금리",
        tags: [],
      },
    ]);
    vi.mocked(getGlobalEventsDashboardData).mockResolvedValue({
      highlights: [],
      upcoming: [],
      week: [],
      coverage: {
        state: "empty",
        coverageRatio: 0,
        availableSources: 0,
        expectedSources: 0,
        summary: "없음",
        updatedAt: null,
        items: [],
      },
    });
    vi.mocked(getDerivativesSummary).mockResolvedValue({
      tradeDate: "2026-03-15",
      requestedDate: null,
      requestedDateAvailable: true,
      isLatestFallback: false,
      sourceCoverage: {
        tradeDate: "2026-03-15",
        coverageRatio: 1,
        state: "full",
        label: "소스 1/1",
        sourceNames: ["KIS"],
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
      confidenceBucket: "medium",
      explanationText: "파생 중립",
      briefingSource: "rule_based",
      participantSummary: [],
      detailLevel: 1,
      components: [],
      lastUpdatedAt: "2026-03-15T01:20:00Z",
      missingFields: [],
      preOpenFutures: {
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
    });
    vi.mocked(getDerivativesTrends).mockResolvedValue({ preset: "20d", date: "2026-03-15", items: [], missingFields: [] });
    vi.mocked(getDerivativesInvestorFlow).mockResolvedValue({
      preset: "20d",
      date: "2026-03-15",
      items: [],
      missingFields: [],
    });

    const result = await getMacroTabData();

    expect(result.referenceCards.map((item) => item.label)).toEqual(["WTI·에너지", "환율", "금리", "파생 시그널"]);
    expect(result.referenceCards.map((item) => item.sourceLabel)).toEqual(["FRED", "연합뉴스", "Reuters", "소스 1/1"]);
  });
});
