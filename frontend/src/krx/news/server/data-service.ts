import {
  MarketNewsCard,
  MarketNewsCoverage,
  MarketNewsHeaderContext,
  MacroNews,
  News,
  Sector,
  StockNews,
} from "@/krx/types/domain";

import { env } from "@/krx/lib/env";
import { ApiItemResponse, ApiListResponse, getKrxJson, getKrxJsonOrNull } from "@/krx/server/client";

const BACKEND_BASE_URL = env.BACKEND_BASE_URL.replace(/\/+$/, "");

type ApiNews = {
  id: string;
  type: "macro" | "stock";
  title: string;
  summary: string;
  why_it_matters: string;
  source: string;
  source_url: string;
  published_at: string;
  credibility_score: number;
  materiality_score: number;
  editorial_score: number;
  story_state: "NEW" | "ONGOING" | "DISCLOSURE_CONFIRMED";
  editorial_reason: string | null;
  ai_confidence: number;
  sentiment: "positive" | "neutral" | "negative";
  importance: "high" | "medium" | "low";
  related_sectors: string[];
  related_tickers: string[];
  category: string;
  tags: string[];
};

type ApiMarketNewsEvidence = {
  role: "PRIMARY" | "CONFIRMING" | "DISCOVERY";
  provider: "DART" | "BIGKINDS" | "NAVER_NEWS" | "MK_RSS";
  title: string | null;
  snippet: string | null;
  publisher: string | null;
  source_url: string | null;
  canonical_url: string | null;
  storage_policy: "CANONICAL_EVENT" | "PERSISTENT_EVIDENCE" | "TRANSIENT_DISCOVERY";
  published_at: string | null;
};

type ApiMarketNewsCard = {
  id: string;
  title: string;
  one_line_summary: string;
  why_it_matters: string;
  market_impact: string;
  market_scope: "kr_market" | "global_market" | "sector" | "company" | "ignore";
  primary_region: "KR" | "GLOBAL";
  trust_score: number;
  materiality_score: number;
  novelty_score: number;
  attention_score: number;
  editorial_score: number;
  story_state: "NEW" | "ONGOING" | "DISCLOSURE_CONFIRMED";
  importance_label: "high" | "medium" | "low";
  editorial_reason: string | null;
  ai_confidence: number;
  ranking_score: number;
  evidence_count: number;
  cross_source_score: number;
  published_at: string | null;
  updated_at: string | null;
  evidence: ApiMarketNewsEvidence[];
  provenance: Record<string, unknown>;
};

type ApiMarketNewsCoverageItem = {
  provider: "DART" | "BIGKINDS" | "NAVER_NEWS" | "MK_RSS" | "NAVER_DATALAB";
  status: "available" | "partial" | "missing";
  document_count: number;
  event_count: number;
  evidence_count: number;
  last_published_at: string | null;
  last_synced_at: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
};

type ApiMarketNewsCoverage = {
  state: "full" | "partial" | "empty";
  coverage_ratio: number;
  available_sources: number;
  expected_sources: number;
  summary: string;
  updated_at: string | null;
  items: ApiMarketNewsCoverageItem[];
};

type ApiMarketNewsHeaderContext = {
  updated_at: string | null;
  summary_line: string;
  coverage: {
    state: "full" | "partial" | "empty";
    coverage_ratio: number;
    available_sources: number;
    expected_sources: number;
    summary: string;
  };
  columns: Array<{
    key: "KR" | "GLOBAL";
    label: string;
    count: number;
    lead_title: string | null;
    lead_scope: string | null;
  }>;
};

function mapNews(item: ApiNews): News {
  const base = {
    id: item.id,
    title: item.title,
    summary: item.summary,
    whyItMatters: item.why_it_matters,
    source: item.source,
    sourceUrl: item.source_url,
    publishedAt: item.published_at,
    credibilityScore: item.credibility_score,
    materialityScore: item.materiality_score,
    editorialScore: item.editorial_score,
    storyState: item.story_state,
    editorialReason: item.editorial_reason,
    aiConfidence: item.ai_confidence,
    sentiment: item.sentiment,
    importance: item.importance,
    relatedSectors: item.related_sectors as Sector[],
    relatedTickers: item.related_tickers,
    tags: item.tags,
  };

  if (item.type === "macro") {
    const macroNews: MacroNews = {
      ...base,
      type: "macro",
      category: item.category as MacroNews["category"],
    };
    return macroNews;
  }

  const stockNews: StockNews = {
    ...base,
    type: "stock",
    category: item.category as StockNews["category"],
  };
  return stockNews;
}

function mapMarketNewsCard(item: ApiMarketNewsCard): MarketNewsCard {
  return {
    id: item.id,
    title: item.title,
    oneLineSummary: item.one_line_summary,
    whyItMatters: item.why_it_matters,
    marketImpact: item.market_impact,
    marketScope: item.market_scope,
    primaryRegion: item.primary_region,
    trustScore: item.trust_score,
    materialityScore: item.materiality_score,
    noveltyScore: item.novelty_score,
    attentionScore: item.attention_score,
    editorialScore: item.editorial_score,
    storyState: item.story_state,
    importanceLabel: item.importance_label,
    editorialReason: item.editorial_reason,
    aiConfidence: item.ai_confidence,
    rankingScore: item.ranking_score,
    evidenceCount: item.evidence_count,
    crossSourceScore: item.cross_source_score,
    publishedAt: item.published_at,
    updatedAt: item.updated_at,
    evidence: item.evidence.map((evidence) => ({
      role: evidence.role,
      provider: evidence.provider,
      title: evidence.title,
      snippet: evidence.snippet,
      publisher: evidence.publisher,
      sourceUrl: evidence.source_url,
      canonicalUrl: evidence.canonical_url,
      storagePolicy: evidence.storage_policy,
      publishedAt: evidence.published_at,
    })),
    provenance: item.provenance,
  };
}

function mapMarketNewsCoverage(payload: ApiMarketNewsCoverage): MarketNewsCoverage {
  return {
    state: payload.state,
    coverageRatio: payload.coverage_ratio,
    availableSources: payload.available_sources,
    expectedSources: payload.expected_sources,
    summary: payload.summary,
    updatedAt: payload.updated_at,
    items: payload.items.map((item) => ({
      provider: item.provider,
      status: item.status,
      documentCount: item.document_count,
      eventCount: item.event_count,
      evidenceCount: item.evidence_count,
      lastPublishedAt: item.last_published_at,
      lastSyncedAt: item.last_synced_at,
      note: item.note,
      metadata: item.metadata,
    })),
  };
}

function mapMarketNewsHeaderContext(payload: ApiMarketNewsHeaderContext): MarketNewsHeaderContext {
  return {
    updatedAt: payload.updated_at,
    summaryLine: payload.summary_line,
    coverage: {
      state: payload.coverage.state,
      coverageRatio: payload.coverage.coverage_ratio,
      availableSources: payload.coverage.available_sources,
      expectedSources: payload.coverage.expected_sources,
      summary: payload.coverage.summary,
    },
    columns: payload.columns.map((column) => ({
      key: column.key,
      label: column.label,
      count: column.count,
      leadTitle: column.lead_title,
      leadScope: column.lead_scope,
    })),
  };
}

async function getNewsProductJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/news${path}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`News product request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export async function getAllNews() {
  const response = await getKrxJson<ApiListResponse<ApiNews>>("/news");
  return response.items.map(mapNews);
}

export async function getMacroNews() {
  const response = await getKrxJson<ApiListResponse<ApiNews>>("/news/macro");
  return response.items.map(mapNews);
}

export async function getNewsByTicker(ticker: string) {
  const response = await getKrxJson<ApiListResponse<ApiNews>>(
    `/news/by-ticker/${encodeURIComponent(ticker)}`,
  );
  return response.items.map(mapNews);
}

async function getNewsById(id: string) {
  const response = await getKrxJsonOrNull<ApiItemResponse<ApiNews>>(`/news/${encodeURIComponent(id)}`);
  if (!response) return null;
  return mapNews(response.item);
}

export async function getNewsDetail(id: string) {
  const [item, allNews] = await Promise.all([getNewsById(id), getAllNews()]);

  if (!item) return null;

  const related = allNews
    .filter((news) => news.id !== id)
    .filter(
      (news) =>
        news.category === item.category ||
        news.relatedTickers.some((ticker) => item.relatedTickers.includes(ticker)),
    )
    .slice(0, 5);

  return { item, related };
}

export function emptyMarketNewsCoverage(): MarketNewsCoverage {
  return {
    state: "empty",
    coverageRatio: 0,
    availableSources: 0,
    expectedSources: 4,
    summary: "뉴스 소스가 아직 준비되지 않았습니다.",
    updatedAt: null,
    items: [],
  };
}

export function emptyMarketNewsHeaderContext(): MarketNewsHeaderContext {
  return {
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
  };
}

export async function getMarketNewsCards(region: "kr" | "global" | "disclosures") {
  const response = await getNewsProductJson<ApiListResponse<ApiMarketNewsCard>>(`/${region}`);
  return response.items.map(mapMarketNewsCard);
}

export async function getMarketNewsCoverage() {
  const response = await getNewsProductJson<ApiMarketNewsCoverage>("/coverage");
  return mapMarketNewsCoverage(response);
}

export async function getMarketNewsHeaderContext() {
  const response = await getNewsProductJson<ApiMarketNewsHeaderContext>("/header-context");
  return mapMarketNewsHeaderContext(response);
}
