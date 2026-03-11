import { env } from "@/krx/lib/env";
import { getGlobalEventsDashboardData } from "@/krx/global-events/server/data-service";
import {
  getDerivativesInvestorFlow,
  getDerivativesSummary,
  getDerivativesTrends,
} from "@/krx/derivatives/server/data-service";
import { getMarketSignalSummary } from "@/krx/market-signal/server/data-service";
import { AppHeader, MarketNewsCard } from "@/krx/types/domain";
import { getAllStocks, getStockByTicker } from "@/krx/market/server/data-service";
import {
  emptyMarketNewsCoverage,
  emptyMarketNewsHeaderContext,
  getAllNews,
  getMarketNewsCards,
  getMarketNewsCoverage,
  getMarketNewsHeaderContext,
  getMacroNews,
  getNewsByTicker,
  getNewsDetail,
} from "@/krx/news/server/data-service";

const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");
const APP_HEADER_RETRY_DELAYS_MS = [0, 150, 350];

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

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function keepMvpNewsScope(region: "KR" | "GLOBAL", cards: Awaited<ReturnType<typeof getMarketNewsCards>>) {
  const allowedScope = region === "KR" ? "kr_market" : "global_market";
  return cards.filter((card) => card.primaryRegion === region && card.marketScope === allowedScope);
}

function hasDisclosureSignal(card: MarketNewsCard) {
  return card.marketScope === "company" || card.evidence.some((evidence) => evidence.provider === "DART");
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
  let lastError: unknown = null;

  for (const delayMs of APP_HEADER_RETRY_DELAYS_MS) {
    if (delayMs > 0) {
      await sleep(delayMs);
    }

    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/app/header?market=krx`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`App header request failed (${response.status})`);
      }

      const payload = (await response.json()) as ApiAppHeader;
      return mapAppHeader(payload);
    } catch (error) {
      lastError = error;
    }
  }

  console.error(
    JSON.stringify(
      {
        scope: "krx_app_header_fetch",
        status: "failed",
        error: lastError instanceof Error ? lastError.message : String(lastError),
      },
      null,
      0,
    ),
  );

  return emptyAppHeader();
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

export async function getNewsTabData() {
  try {
    const [krCardsRaw, globalCardsRaw, headerContext, coverage] = await Promise.all([
      getMarketNewsCards("kr"),
      getMarketNewsCards("global"),
      getMarketNewsHeaderContext(),
      getMarketNewsCoverage(),
    ]);
    const krCards = sortByRankingScoreDesc(keepMvpNewsScope("KR", krCardsRaw));
    const globalCards = sortByRankingScoreDesc(keepMvpNewsScope("GLOBAL", globalCardsRaw));
    const disclosureCards = sortByRankingScoreDesc(
      [...krCardsRaw, ...globalCardsRaw].filter(hasDisclosureSignal),
    ).slice(0, 12);

    return {
      krCards,
      globalCards,
      disclosureCards,
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
      headerContext: emptyMarketNewsHeaderContext(),
      coverage: emptyMarketNewsCoverage(),
    };
  }
}

export async function getGlobalEventsTabData() {
  return getGlobalEventsDashboardData();
}
