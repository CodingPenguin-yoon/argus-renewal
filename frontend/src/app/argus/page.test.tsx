import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ArgusPage from "@/app/argus/page";
import ArgusDerivativesPage from "@/app/argus/derivatives/page";
import ArgusFuturesPage from "@/app/argus/derivatives/futures/page";
import ArgusOptionLayerPage from "@/app/argus/derivatives/option-layer/page";
import ArgusOptionQuotesPage from "@/app/argus/derivatives/option-quotes/page";
import ArgusPositionsPage from "@/app/argus/derivatives/positions/page";
import ArgusNewsFeedPage from "@/app/argus/triggers/news/page";
import { getArgusV2Dashboard, getArgusV2Futures, getArgusV2NewsFeed, getArgusV2OptionQuotes } from "@/argus_v2/server/dashboard";
import type { FuturesQuoteResponse, MarketDashboard, NewsFeedResponse, OptionQuotesResponse } from "@/argus_v2/contracts/dashboard";

vi.mock("@/argus_v2/server/dashboard", () => ({
  getArgusV2Dashboard: vi.fn(),
  getArgusV2Futures: vi.fn(),
  getArgusV2NewsFeed: vi.fn(),
  getArgusV2OptionQuotes: vi.fn(),
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

function buildOptionQuotesFixture(): OptionQuotesResponse {
  return {
    as_of: "2026-03-15T02:10:00Z",
    trade_date: "2026-03-15",
    source: "mock.option_chain",
    status: "fresh",
    observed_count: 2,
    underlying_code: "KOSPI200",
    underlying_name: "KOSPI200",
    underlying_price: 366.2,
    expiry_date: "202603",
    contract_month: "202603",
    atm_strike: 365,
    rows: [
      {
        strike_price: 365,
        moneyness: "ATM",
        call_last_price: 2.14,
        call_change_rate: 0.35,
        call_volume: 12048,
        call_trading_value: 25_782_720,
        call_open_interest: 9150,
        call_open_interest_change: 320,
        call_implied_volatility: 22.4,
        put_last_price: 3.02,
        put_change_rate: -0.18,
        put_volume: 15420,
        put_trading_value: 46_568_400,
        put_open_interest: 12200,
        put_open_interest_change: 410,
        put_implied_volatility: 24.1,
        total_open_interest: 21350,
        net_call_put_oi: -3050,
        call_put_oi_ratio: 0.75,
        pressure_side: "PUT",
      },
      {
        strike_price: 367.5,
        moneyness: "UNKNOWN",
        call_last_price: 1.45,
        call_change_rate: 0.22,
        call_volume: 8840,
        call_trading_value: 12_818_000,
        call_open_interest: 10100,
        call_open_interest_change: 280,
        call_implied_volatility: 21.7,
        put_last_price: 4.1,
        put_change_rate: -0.32,
        put_volume: 7600,
        put_trading_value: 31_160_000,
        put_open_interest: 6800,
        put_open_interest_change: -120,
        put_implied_volatility: 25.8,
        total_open_interest: 16900,
        net_call_put_oi: 3300,
        call_put_oi_ratio: 1.49,
        pressure_side: "CALL",
      },
    ],
  };
}

function buildFuturesFixture(): FuturesQuoteResponse {
  return {
    as_of: "2026-03-15T02:10:00Z",
    trade_date: "2026-03-15",
    source: "mock.kis.derivatives",
    status: "fresh",
    observed_count: 1,
    session_type: "PRE_OPEN",
    instrument_code: "A01606",
    instrument_name: "F 202606",
    price: 392.5,
    price_change: -1.2,
    change_rate: -0.31,
    volume: 1500,
    open_interest: 215000,
    put_call_ratio: null,
    implied_volatility: null,
    bid: 392.45,
    ask: 392.55,
    basis: -0.4,
    market_basis: -0.25,
    theoretical_price: 392.8,
    disparity_rate: -0.1,
    open_interest_change: -500,
    open_interest_change_rate: -0.23,
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

  it("renders the derivatives main subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());

    render(await ArgusDerivativesPage());

    expect(screen.getByRole("link", { name: /메인/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /선물\s+KOSPI200 근월/ })).toHaveAttribute("href", "/argus/derivatives/futures");
    expect(screen.getByRole("link", { name: /옵션 시세표/ })).toHaveAttribute("href", "/argus/derivatives/option-quotes");
    expect(screen.getByRole("link", { name: /풋콜 레이어/ })).toHaveAttribute("href", "/argus/derivatives/option-layer");
    expect(screen.getByRole("link", { name: /포지션/ })).toHaveAttribute("href", "/argus/derivatives/positions");
    expect(screen.queryByRole("link", { name: /외인 위치/ })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "옵션·선물" })).toBeInTheDocument();
  });

  it("renders the futures subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getArgusV2Futures).mockResolvedValue(buildFuturesFixture());

    render(await ArgusFuturesPage());

    expect(screen.getByRole("link", { name: /선물\s+KOSPI200 근월/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "선물" })).toBeInTheDocument();
    expect(screen.getAllByText("F 202606").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-0.31%").length).toBeGreaterThan(0);
    expect(screen.getByText("215,000")).toBeInTheDocument();
  });

  it("renders the option quotes subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getArgusV2OptionQuotes).mockResolvedValue(buildOptionQuotesFixture());

    render(await ArgusOptionQuotesPage());

    expect(screen.getByRole("link", { name: /옵션 시세표/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "옵션 시세표" })).toBeInTheDocument();
    expect(screen.getByText("호가 컬럼 미제공")).toBeInTheDocument();
    expect(screen.getByTestId("option-quotes-scroll-window")).toBeInTheDocument();
    expect(screen.getByText(/초기 포커스 365 행사가 · 거래대금 7,235만/)).toBeInTheDocument();
    expect(screen.getByText("12,200")).toBeInTheDocument();
    expect(screen.getByText("-3,050")).toBeInTheDocument();
  });

  it("renders the option put-call layer subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());

    render(await ArgusOptionLayerPage());

    expect(screen.getByRole("link", { name: /풋콜 레이어/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "당일 옵션 풋콜 레이어" })).toBeInTheDocument();
    expect(screen.getByText("CALL OI 변화")).toBeInTheDocument();
    expect(screen.getByText("포지션 탭에서 통합 확인")).toBeInTheDocument();
  });

  it("renders the consolidated position subtab", async () => {
    vi.mocked(getArgusV2Dashboard).mockResolvedValue(buildDashboardFixture());
    vi.mocked(getArgusV2OptionQuotes).mockResolvedValue(buildOptionQuotesFixture());
    vi.mocked(getArgusV2Futures).mockResolvedValue(buildFuturesFixture());

    render(await ArgusPositionsPage());

    expect(screen.getByRole("link", { name: /포지션/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "주체별 포지션" })).toBeInTheDocument();
    expect(screen.getByText("외국인")).toBeInTheDocument();
    expect(screen.getByText("기관")).toBeInTheDocument();
    expect(screen.getByText("개인")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "옵션 거래대금 레이어" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선물 시장 레이어" })).toBeInTheDocument();
    expect(screen.getByText("선물 거래대금 추정")).toBeInTheDocument();
    expect(screen.getAllByText("CALL 거래대금").length).toBeGreaterThan(0);
    expect(screen.getByText("7,235만원")).toBeInTheDocument();
    expect(screen.getByText("옵션 주체별 포지션 미수신")).toBeInTheDocument();
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
