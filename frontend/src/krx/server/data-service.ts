import { env } from "@/krx/lib/env";
import { getGlobalEventsDashboardData } from "@/krx/global-events/server/data-service";
import { KRX_SHORT_REVALIDATE_SECONDS } from "@/krx/server/client";
import {
  getDerivativesInvestorFlow,
  getDerivativesSummary,
  getDerivativesTrends,
} from "@/krx/derivatives/server/data-service";
import { getMarketSignalSummary } from "@/krx/market-signal/server/data-service";
import {
  AppHeader,
  MacroNews,
  MacroReferenceCard,
  MacroTabData,
  MarketNewsCard,
  NewsTabData,
  OverviewTabData,
} from "@/krx/types/domain";
import { getAllStocks, getStockByTicker } from "@/krx/market/server/data-service";
import {
  emptyMarketNewsBriefing,
  emptyMarketNewsCoverage,
  emptyMarketNewsHeaderContext,
  getAllNews,
  getMarketNewsDashboard,
  getMarketNewsCards,
  getMacroNews,
  getNewsByTicker,
  getNewsDetail,
} from "@/krx/news/server/data-service";

const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");
const KR_NEWS_TAB_ACCUMULATION_LIMIT = 50;
const FRED_REFERENCE_REVALIDATE_SECONDS = 60 * 60;

type ApiAppHeaderSupportingPoint = {
  text: string;
  source_key: string;
  source_label: string;
  source_url: string | null;
};

type ApiAppHeaderCoverageItem = {
  key: string;
  label: string;
  status: "available" | "partial" | "missing";
  source_name: string | null;
  source_url: string | null;
  updated_at: string | null;
};

type ApiAppHeaderCoverage = {
  state: "full" | "partial" | "empty";
  coverage_ratio: number;
  available_sources: number;
  expected_sources: number;
  summary: string;
  items: ApiAppHeaderCoverageItem[];
};

type ApiBreakingNews = {
  label: string;
  headline: string;
  why_it_matters_one_line: string;
  impact_scope: string;
  related_tab_link: string;
  source_name: string | null;
  source_url: string | null;
  published_at: string | null;
};

type ApiAppHeader = {
  market: "krx";
  market_tone_line: string;
  supporting_points: ApiAppHeaderSupportingPoint[];
  phase: "pre-open" | "live" | "post-close";
  updated_at: string | null;
  source_coverage: ApiAppHeaderCoverage;
  breaking_news: ApiBreakingNews | null;
};

type ApiMacroReferenceCard = {
  key: string;
  label: string;
  summary: string | null;
  value: number | null;
  value_display: string | null;
  change_value: number | null;
  change_display: string | null;
  unit: string;
  stale: boolean;
  source: {
    key: string;
    name: string;
    series_id: string;
    series_name: string;
    url: string | null;
    observed_at: string | null;
    updated_at: string | null;
  };
  freshness: {
    status: "fresh" | "stale" | "unknown";
    observed_at: string | null;
    age_seconds: number | null;
    ttl_seconds: number;
  };
  metadata: {
    series_id: string;
    series_name: string;
    semantics: string;
    frequency: string;
    freshness_ttl_seconds: number;
    provider_mode: string;
    retry_count: number;
  };
};

type ApiMacroReferencePayload = {
  updated_at: string | null;
  items: ApiMacroReferenceCard[];
  coverage: {
    state: "full" | "partial" | "empty";
    available_items: number;
    expected_items: number;
    provider: string;
    summary: string;
    note: string | null;
  };
};

function keepMvpNewsScope(region: "KR" | "GLOBAL", cards: MarketNewsCard[]) {
  const allowedScope = region === "KR" ? "kr_market" : "global_market";
  return cards.filter((card) => card.primaryRegion === region && card.marketScope === allowedScope);
}

function sortByRankingScoreDesc(cards: MarketNewsCard[]) {
  return [...cards].sort((a, b) => {
    if (b.rankingScore !== a.rankingScore) {
      return b.rankingScore - a.rankingScore;
    }
    const aTime = a.updatedAt ?? a.publishedAt ?? "";
    const bTime = b.updatedAt ?? b.publishedAt ?? "";
    return bTime.localeCompare(aTime);
  });
}

function sortByRecencyDesc(cards: MarketNewsCard[]) {
  return [...cards].sort((a, b) => {
    const aTime = a.updatedAt ?? a.publishedAt ?? "";
    const bTime = b.updatedAt ?? b.publishedAt ?? "";
    if (bTime !== aTime) {
      return bTime.localeCompare(aTime);
    }
    return b.rankingScore - a.rankingScore;
  });
}

function firstNonEmpty(...values: Array<string | null | undefined>) {
  return values.find((value) => typeof value === "string" && value.trim().length > 0) ?? "";
}

function pickLatestIso(...values: Array<string | null | undefined>) {
  const items = values.filter((value): value is string => Boolean(value));
  if (items.length === 0) return null;
  return items.sort((a, b) => b.localeCompare(a))[0];
}

function toneFromSentiment(sentiment: "positive" | "neutral" | "negative"): MacroReferenceCard["tone"] {
  return sentiment;
}

function buildMacroReferenceCards(macroNews: MacroNews[]) {
  const latestByCategory = (category: string) =>
    macroNews.find((item) => item.category === category) ?? null;

  return [
    latestByCategory("환율"),
    latestByCategory("유가/에너지"),
    latestByCategory("금리"),
    latestByCategory("전쟁/지정학"),
  ]
    .filter((item): item is NonNullable<ReturnType<typeof latestByCategory>> => Boolean(item))
    .map((item) => ({
      key: item.category,
      label: item.category === "유가/에너지" ? "WTI·에너지" : item.category,
      summary: firstNonEmpty(item.whyItMatters, item.summary),
      sourceLabel: item.source,
      sourceUrl: item.sourceUrl,
      updatedAt: item.publishedAt,
      tone: toneFromSentiment(item.sentiment),
    }));
}

const FRED_REFERENCE_ORDER = ["usdkrw", "wti", "us10y", "fedfunds"] as const;
const RISING_IS_RISK_OFF_REFERENCE_KEYS = new Set<string>(["usdkrw", "wti", "us10y", "fedfunds"]);

function macroReferenceLabel(key: string, label: string) {
  if (key === "usdkrw") return "환율";
  if (key === "wti") return "WTI·에너지";
  return label;
}

function findFredReferenceCard(cards: MacroReferenceCard[], key: (typeof FRED_REFERENCE_ORDER)[number]) {
  return cards.find((item) => item.key === key) ?? null;
}

function buildOverviewMacroWidgets(macroNews: MacroNews[], fredReferenceCards: MacroReferenceCard[]) {
  const baseCards = buildMacroReferenceCards(macroNews);
  const latestByKey = new Map(baseCards.map((item) => [item.key, item]));

  return [
    findFredReferenceCard(fredReferenceCards, "usdkrw") ?? latestByKey.get("환율") ?? null,
    findFredReferenceCard(fredReferenceCards, "wti") ?? latestByKey.get("유가/에너지") ?? null,
    findFredReferenceCard(fredReferenceCards, "us10y") ?? latestByKey.get("금리") ?? null,
  ].filter((item): item is MacroReferenceCard => Boolean(item));
}

function toneFromMacroReferenceChange(key: string, value: number | null): MacroReferenceCard["tone"] {
  if (value === null || value === 0) return "neutral";
  if (RISING_IS_RISK_OFF_REFERENCE_KEYS.has(key)) {
    return value > 0 ? "negative" : "positive";
  }
  return value > 0 ? "positive" : "negative";
}

async function getBackendMacroReferenceCards(): Promise<MacroReferenceCard[]> {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/krx/macro-reference/cards`, {
      next: { revalidate: FRED_REFERENCE_REVALIDATE_SECONDS },
    });

    if (!response.ok) {
      throw new Error(`Macro reference request failed (${response.status})`);
    }

    const payload = (await response.json()) as ApiMacroReferencePayload;
    return payload.items.map((item) => ({
      key: item.key,
      label: macroReferenceLabel(item.key, item.label),
      summary: firstNonEmpty(item.summary, item.value_display, item.source.series_name),
      sourceLabel: item.source.key,
      sourceUrl: item.source.url,
      updatedAt: item.source.observed_at ?? item.source.updated_at,
      tone: toneFromMacroReferenceChange(item.key, item.change_value),
    }));
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          scope: "krx_macro_reference_fetch",
          status: "failed",
          error: error instanceof Error ? error.message : String(error),
        },
        null,
        0,
      ),
    );
    return [];
  }
}

function mapAppHeader(api: ApiAppHeader): AppHeader {
  return {
    market: api.market,
    marketToneLine: api.market_tone_line,
    supportingPoints: api.supporting_points.map((point) => ({
      text: point.text,
      sourceKey: point.source_key,
      sourceLabel: point.source_label,
      sourceUrl: point.source_url,
    })),
    phase: api.phase,
    updatedAt: api.updated_at,
    sourceCoverage: {
      state: api.source_coverage.state,
      coverageRatio: api.source_coverage.coverage_ratio,
      availableSources: api.source_coverage.available_sources,
      expectedSources: api.source_coverage.expected_sources,
      summary: api.source_coverage.summary,
      items: api.source_coverage.items.map((item) => ({
        key: item.key,
        label: item.label,
        status: item.status,
        sourceName: item.source_name,
        sourceUrl: item.source_url,
        updatedAt: item.updated_at,
      })),
    },
    breakingNews: api.breaking_news
      ? {
          label: api.breaking_news.label,
          headline: api.breaking_news.headline,
          whyItMattersOneLine: api.breaking_news.why_it_matters_one_line,
          impactScope: api.breaking_news.impact_scope,
          relatedTabLink: api.breaking_news.related_tab_link,
          sourceName: api.breaking_news.source_name,
          sourceUrl: api.breaking_news.source_url,
          publishedAt: api.breaking_news.published_at,
        }
      : null,
  };
}

export function emptyAppHeader(): AppHeader {
  return {
    market: "krx",
    marketToneLine: "",
    supportingPoints: [],
    phase: "pre-open",
    updatedAt: null,
    sourceCoverage: {
      state: "empty",
      coverageRatio: 0,
      availableSources: 0,
      expectedSources: 3,
      summary: "헤더 데이터를 아직 준비하지 못했습니다.",
      items: [],
    },
    breakingNews: null,
  };
}

export async function getStockPageData(ticker: string) {
  const normalizedTicker = ticker.toUpperCase();
  const stock = await getStockByTicker(normalizedTicker);
  if (!stock) {
    return { stock: null, stockNews: [], relatedMacro: [] };
  }

  const [stockNews, macroNews] = await Promise.all([
    getNewsByTicker(normalizedTicker),
    getMacroNews(),
  ]);

  return {
    stock,
    stockNews,
    relatedMacro: macroNews
      .filter((news) => news.relatedTickers.some((item) => item.toUpperCase() === normalizedTicker))
      .slice(0, 4),
  };
}

export { getNewsDetail };

export async function getSearchIndex() {
  const [news, stocks] = await Promise.all([getAllNews(), getAllStocks()]);

  return {
    stocks,
    news: news.slice(0, 40),
  };
}

export async function getWatchlistPageData() {
  const [stocks, news] = await Promise.all([getAllStocks(), getAllNews()]);
  return { stocks, news };
}

export async function getAppHeaderData() {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/app/header?market=krx`, {
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      throw new Error(`App header request failed (${response.status})`);
    }

    const payload = (await response.json()) as ApiAppHeader;
    return mapAppHeader(payload);
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          scope: "krx_app_header_fetch",
          status: "failed",
          error: error instanceof Error ? error.message : String(error),
        },
        null,
        0,
      ),
    );

    return emptyAppHeader();
  }
}

export async function getMarketSignalTabData() {
  const [summary, derivativesSummary, derivativesTrends, derivativesInvestorFlow] = await Promise.all([
    getMarketSignalSummary(),
    getDerivativesSummary(),
    getDerivativesTrends("20d"),
    getDerivativesInvestorFlow("20d"),
  ]);
  return { summary, derivativesSummary, derivativesTrends, derivativesInvestorFlow };
}

export async function getNewsTabData(): Promise<NewsTabData> {
  try {
    const [
      { globalCards: globalCardsRaw, disclosureCards: disclosureCardsRaw, briefing, headerContext, coverage },
      krCardsAccumulatedRaw,
    ] = await Promise.all([
      getMarketNewsDashboard(),
      getMarketNewsCards("kr", KR_NEWS_TAB_ACCUMULATION_LIMIT),
    ]);
    const krCards = sortByRecencyDesc(keepMvpNewsScope("KR", krCardsAccumulatedRaw));
    const globalCards = sortByRankingScoreDesc(keepMvpNewsScope("GLOBAL", globalCardsRaw));
    const disclosureCards = sortByRankingScoreDesc(disclosureCardsRaw).slice(0, 12);

    return {
      krCards,
      globalCards,
      disclosureCards,
      briefing,
      headerContext,
      coverage,
    };
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          scope: "krx_news_tab_fetch",
          status: "failed",
          error: error instanceof Error ? error.message : String(error),
        },
        null,
        0,
      ),
    );

    return {
      krCards: [],
      globalCards: [],
      disclosureCards: [],
      briefing: emptyMarketNewsBriefing(),
      headerContext: emptyMarketNewsHeaderContext(),
      coverage: emptyMarketNewsCoverage(),
    };
  }
}

export async function getGlobalEventsTabData() {
  return getGlobalEventsDashboardData();
}

export async function getOverviewTabData(): Promise<OverviewTabData> {
  const [marketSignal, newsTab, globalEvents, macroNews, fredReferenceCards] = await Promise.all([
    getMarketSignalTabData(),
    getNewsTabData(),
    getGlobalEventsTabData(),
    getMacroNews({ revalidate: KRX_SHORT_REVALIDATE_SECONDS }),
    getBackendMacroReferenceCards(),
  ]);
  const macroWidgets = buildOverviewMacroWidgets(macroNews, fredReferenceCards);

  const marketCard = marketSignal.summary.cards[0];
  const globalHighlight = globalEvents.highlights[0];
  const gatewayPanels = [
    {
      key: "market-signal" as const,
      title: "시장 신호",
      href: "/krx",
      summary: firstNonEmpty(marketSignal.summary.explanationText, marketCard?.interpretationLine),
      metricLabel: "신뢰도",
      metricValue: marketSignal.summary.confidenceBucket.toUpperCase(),
      updatedAt: marketSignal.summary.lastUpdatedAt,
    },
    {
      key: "news" as const,
      title: "시장 뉴스",
      href: "/krx/news",
      summary: firstNonEmpty(newsTab.headerContext.summaryLine, newsTab.briefing.summary),
      metricLabel: "핵심 카드",
      metricValue: `${newsTab.krCards.length + newsTab.globalCards.length + newsTab.disclosureCards.length}건`,
      updatedAt: pickLatestIso(newsTab.headerContext.updatedAt, newsTab.briefing.updatedAt),
    },
    {
      key: "global-events" as const,
      title: "매크로 캘린더",
      href: "/krx/macro-calendar",
      summary: firstNonEmpty(globalHighlight?.whyItMattersKo, globalEvents.coverage.summary),
      metricLabel: "하이라이트",
      metricValue: `${globalEvents.highlights.length}건`,
      updatedAt: pickLatestIso(globalHighlight?.updatedAt, globalEvents.coverage.updatedAt),
    },
  ];
  const keyTakeaways = [
    ...newsTab.briefing.keyPoints,
    ...gatewayPanels.map((item) => item.summary),
    globalHighlight?.whyItMattersKo ?? "",
  ]
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, array) => array.indexOf(item) === index)
    .slice(0, 5);

  return {
    marketToneLine: firstNonEmpty(
      marketSignal.summary.interpretationLine,
      newsTab.headerContext.summaryLine,
      newsTab.briefing.headline,
    ),
    keyTakeaways,
    reportHeadline: firstNonEmpty(newsTab.briefing.headline, "오늘의 종합 리포트"),
    reportSummary: firstNonEmpty(
      newsTab.briefing.summary,
      marketSignal.summary.explanationText,
      newsTab.headerContext.summaryLine,
    ),
    reportUpdatedAt: pickLatestIso(
      newsTab.briefing.updatedAt,
      marketSignal.summary.lastUpdatedAt,
      globalHighlight?.updatedAt,
    ),
    reportLinks: newsTab.briefing.linkedHeadlines.slice(0, 4).map((item) => ({
      title: item.title,
      href: item.sourceUrl,
      sourceLabel: item.sourceLabel,
      publishedAt: item.publishedAt,
    })),
    macroWidgets,
    gatewayPanels,
    globalHighlights: globalEvents.highlights.slice(0, 3),
  };
}

export async function getMacroTabData(): Promise<MacroTabData> {
  const [macroNews, globalEvents, derivativesSummary, derivativesTrends, derivativesInvestorFlow, fredReferenceCards] =
    await Promise.all([
      getMacroNews({ revalidate: KRX_SHORT_REVALIDATE_SECONDS }),
      getGlobalEventsTabData(),
      getDerivativesSummary(),
      getDerivativesTrends("20d"),
      getDerivativesInvestorFlow("20d"),
      getBackendMacroReferenceCards(),
    ]);
  const fredReferenceCardsByKey = new Map(fredReferenceCards.map((item) => [item.key, item]));
  const macroReferenceCards = buildMacroReferenceCards(macroNews).filter((item) => {
    if (item.key === "환율") return !fredReferenceCardsByKey.has("usdkrw");
    if (item.key === "유가/에너지") return !fredReferenceCardsByKey.has("wti");
    if (item.key === "금리") {
      return !(fredReferenceCardsByKey.has("us10y") || fredReferenceCardsByKey.has("fedfunds"));
    }
    return true;
  });
  const orderedFredReferenceCards = FRED_REFERENCE_ORDER.flatMap((key) => {
    const card = fredReferenceCardsByKey.get(key);
    return card ? [card] : [];
  });
  const referenceCards: MacroReferenceCard[] = [...orderedFredReferenceCards, ...macroReferenceCards];

  referenceCards.push({
    key: "derivatives",
    label: "파생 시그널",
    summary: firstNonEmpty(derivativesSummary.explanationText, "파생 요약이 아직 준비되지 않았습니다."),
    sourceLabel: derivativesSummary.sourceCoverage.label,
    sourceUrl: null,
    updatedAt: derivativesSummary.lastUpdatedAt,
    tone:
      derivativesSummary.directionalBias === "bullish"
        ? "positive"
        : derivativesSummary.directionalBias === "bearish"
          ? "negative"
          : "neutral",
  });

  return {
    referenceCards,
    macroNews: macroNews.slice(0, 8),
    globalHighlights: globalEvents.highlights.slice(0, 4),
    derivativesSummary,
    derivativesTrends,
    derivativesInvestorFlow,
    updatedAt: pickLatestIso(
      macroNews[0]?.publishedAt,
      ...fredReferenceCards.map((item) => item.updatedAt),
      globalEvents.coverage.updatedAt,
      derivativesSummary.lastUpdatedAt,
    ),
  };
}
