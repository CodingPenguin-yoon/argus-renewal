import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ArgusPage from "@/app/argus/page";
import ArgusNewsFeedPage from "@/app/argus/triggers/news/page";
import { getArgusV2Dashboard, getArgusV2NewsFeed } from "@/argus_v2/server/dashboard";
import type { MarketDashboard, NewsFeedResponse } from "@/argus_v2/contracts/dashboard";

vi.mock("@/argus_v2/server/dashboard", () => ({
  getArgusV2Dashboard: vi.fn(),
  getArgusV2NewsFeed: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

function buildDashboardFixture(): MarketDashboard {
  const point = (value: number | null, unit: string, source = "mock") => ({
    value,
    unit,
    source,
    observed_at: "2026-03-15T02:10:00Z",
    freshness: "partial" as const,
  });

  return {
    as_of: "2026-03-15T02:10:00Z",
    session_phase: "live",
    derivatives: {
      foreign_futures_net_buy: point(-180_000_000_000, "KRW", "mock.kis.derivatives"),
      institution_futures_net_buy: point(62_000_000_000, "KRW"),
      individual_futures_net_buy: point(118_000_000_000, "KRW"),
      basis: point(-0.42, "pt"),
      put_call_ratio: point(1.08, "ratio"),
      open_interest_change_rate: point(1.7, "pct"),
      kospi200_futures_change_rate: point(-0.34, "pct"),
      option_pressure: "PUT",
      option_open_interest_change: {
        freshness: "partial",
        call_change_rate: 0.4,
        put_change_rate: 1.7,
        net_change_rate: -1.2,
        total_change_rate: 1.7,
        dominant_side: "PUT",
        source: "mock.option_chain",
        observed_at: "2026-03-15T02:10:00Z",
      },
      key_levels: [
        {
          role: "put_wall",
          label: "하단 풋 OI 집중",
          side: "PUT",
          strike_price: 365,
          summary: "365pt 부근 풋 미결제약정이 방어/이탈 확인 레벨입니다.",
          source: "mock.option_chain",
          observed_at: "2026-03-15T02:10:00Z",
          freshness: "partial",
        },
      ],
      summary: "외국인 KOSPI200 선물 매도와 풋 우위 옵션 압력이 먼저 확인됩니다.",
      freshness: "partial",
    },
    triggers: [
      {
        id: "rates",
        title: "미국 금리 상승 경계",
        summary: "밤사이 금리 상승은 위험자산과 원화에는 부담으로 해석됩니다.",
        impact: "negative",
        source: "mock.news.macro",
        published_at: "2026-03-15T02:10:00Z",
        connection_strength: "medium",
        ai_reason: "금리 상승은 국내 위험자산과 원화에 부담으로 연결됩니다.",
        ai_confidence: "high",
        affected_factors: ["금리", "환율", "위험자산"],
        freshness: "partial",
      },
    ],
    reaction: {
      kospi_change_rate: point(-0.18, "pct"),
      kosdaq_change_rate: point(0.12, "pct"),
      kospi200_futures_change_rate: point(-0.34, "pct"),
      advancing_count: point(432, "count"),
      declining_count: point(511, "count"),
      spot_foreign_net_buy: point(-82_000_000_000, "KRW", "mock.market.reaction"),
      spot_institution_net_buy: point(34_000_000_000, "KRW", "mock.market.reaction"),
      spot_individual_net_buy: point(48_000_000_000, "KRW", "mock.market.reaction"),
      strong_sectors: [
        {
          name: "반도체",
          change_rate: 1.15,
          reason: "미국 AI/반도체 모멘텀 반영",
          tone: "positive",
          source: "mock.market.reaction",
          observed_at: "2026-03-15T02:10:00Z",
        },
      ],
      weak_sectors: [],
      summary: "지수는 약하지만 반도체가 버티며 하방 압력을 제한합니다.",
      freshness: "partial",
    },
    judgement: {
      label: "하방 우위",
      summary: "외국인 선물 매도와 풋 우위 옵션 압력이 하방을 먼저 가리킵니다.",
      primary_driver: "외국인 KOSPI200 선물",
      confidence: "medium",
      data_reliability: "partial",
      reasons: ["외국인 KOSPI200 선물 매도", "미국 금리 상승 경계"],
      counter_evidence: ["반도체 강세가 지수 낙폭을 제한합니다."],
      transition_condition: "외국인 선물 매도가 줄면 중립으로 낮춥니다.",
      watch_points: ["외국인 선물 순매도 지속 여부"],
      source: "rule_based",
    },
    provider_health: [
      {
        key: "kis_derivatives",
        label: "KIS 파생 실데이터",
        status: "missing",
        last_success_at: null,
        observed_count: 0,
        missing_fields: ["KIS_APP_KEY"],
        error: "실데이터 smoke test 전입니다.",
      },
    ],
  };
}

function buildNewsFeedFixture(): NewsFeedResponse {
  return {
    as_of: "2026-03-15T02:12:00Z",
    provider: "rss",
    status: "fresh",
    observed_count: 2,
    error: null,
    items: [
      {
        id: "feed-fx",
        title: "원/달러 환율 장중 상승",
        summary: "달러 강세와 외국인 수급 경계가 이어집니다.",
        source: "테스트 경제 뉴스",
        published_at: "2026-03-15T02:11:00Z",
        source_url: "https://example.test/fx",
        freshness: "fresh",
      },
      {
        id: "feed-chip",
        title: "반도체 대형주 강세",
        summary: "AI 반도체 수요 기대가 지수 하단을 지지합니다.",
        source: "테스트 경제 뉴스",
        published_at: "2026-03-15T02:10:00Z",
        source_url: "https://example.test/chip",
        freshness: "fresh",
      },
    ],
  };
}

describe("argus market judgement route", () => {
  it("renders the Argus v2 PRD tab shell", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());

    render(await ArgusPage());

    expect(screen.getByRole("heading", { name: "하방 우위" })).toBeInTheDocument();
    expect(screen.getByText("Argus v2 market cockpit")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /시장 판단/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /옵션·선물/ })).toHaveAttribute("href", "/argus/derivatives");
    expect(screen.getByRole("link", { name: /현물 반응/ })).toHaveAttribute("href", "/argus/reaction");
    expect(screen.getByRole("link", { name: /뉴스 분석/ })).toHaveAttribute("href", "/argus/triggers");
    expect(screen.getByRole("heading", { name: "시장 판단" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "핵심 수급" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "뉴스·현물 검증" })).toBeInTheDocument();
    expect(screen.getByText("금리 상승은 국내 위험자산과 원화에 부담으로 연결됩니다.")).toBeInTheDocument();
    expect(screen.getByText("KIS 파생 실데이터")).toBeInTheDocument();
  });

  it("renders explicit empty states for unconnected data areas", async () => {
    const fixture = buildDashboardFixture();
    fixture.derivatives.key_levels = [];
    fixture.triggers = [];
    fixture.reaction.strong_sectors = [];
    fixture.reaction.weak_sectors = [];
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(fixture);

    render(await ArgusPage());

    expect(screen.getByText("대표 뉴스 없음")).toBeInTheDocument();
    expect(screen.getByText("강한 섹터 없음")).toBeInTheDocument();
    expect(screen.getByText("약한 섹터 없음")).toBeInTheDocument();
  });

  it("renders the news analysis feed subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getArgusV2NewsFeed).mockResolvedValue(buildNewsFeedFixture());

    render(await ArgusNewsFeedPage());

    expect(screen.getByRole("link", { name: /메인/ })).toHaveAttribute("href", "/argus/triggers");
    expect(screen.getByRole("link", { name: /뉴스\s+실시간 원천 피드/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "실시간 뉴스" })).toBeInTheDocument();
    expect(screen.getByText("원/달러 환율 장중 상승")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "원문" })[0]).toHaveAttribute("href", "https://example.test/fx");
  });
});
