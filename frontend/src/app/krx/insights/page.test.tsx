import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KrxInsightsPage from "@/app/krx/insights/page";
import { emptyDerivativesInvestorFlow, emptyDerivativesSummary, emptyDerivativesTrends } from "@/krx/derivatives/server/data-service";
import { getAppHeaderData, getMacroTabData } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getAppHeaderData: vi.fn(),
  getMacroTabData: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

describe("krx insights page route", () => {
  it("renders macro reference panels, derivatives context, and AI gauge labels", async () => {
    const derivativesSummary = emptyDerivativesSummary();
    derivativesSummary.explanationText = "파생은 상방 우위를 유지하지만 변동성 확대는 확인이 필요합니다.";
    derivativesSummary.lastUpdatedAt = "2026-03-15T02:20:00Z";
    derivativesSummary.pcr = 0.94;
    derivativesSummary.nightFutures.changeRate = 0.63;
    derivativesSummary.impliedVolatility = 18.2;
    derivativesSummary.foreignFuturesNetPosition = 1500;
    derivativesSummary.directionalBias = "bullish";
    derivativesSummary.volatilityBias = "rising";
    derivativesSummary.confidenceBucket = "high";

    vi.mocked(getAppHeaderData).mockResolvedValue({
      market: "krx",
      marketToneLine: "외국인 선물 포지션은 상방 우위를 가리키지만 달러 방향성은 더 확인이 필요합니다.",
      supportingPoints: [
        { text: "외국인 선물은 순매수 우위입니다.", sourceKey: "derivatives", sourceLabel: "KRX", sourceUrl: null },
      ],
      phase: "live",
      updatedAt: "2026-03-15T02:20:00Z",
      sourceCoverage: {
        state: "full",
        coverageRatio: 1,
        availableSources: 3,
        expectedSources: 3,
        summary: "모든 핵심 소스가 반영되었습니다.",
        items: [
          { key: "market", label: "시장 톤", status: "available", sourceName: null, sourceUrl: null, updatedAt: null },
        ],
      },
      breakingNews: null,
    });

    vi.mocked(getMacroTabData).mockResolvedValue({
      referenceCards: [
        {
          key: "fx",
          label: "환율",
          summary: "달러 강세가 외국인 수급에 부담입니다.",
          sourceLabel: "연합뉴스",
          sourceUrl: "https://example.com/fx",
          updatedAt: "2026-03-15T02:00:00Z",
          tone: "negative",
        },
      ],
      macroNews: [
        {
          id: "macro-1",
          type: "macro",
          title: "달러 강세 재확인",
          summary: "요약",
          whyItMatters: "원화 약세와 외국인 수급에 연결됩니다.",
          source: "연합뉴스",
          sourceUrl: "https://example.com/fx",
          publishedAt: "2026-03-15T02:00:00Z",
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
      ],
      globalHighlights: [
        {
          id: "event-1",
          eventKey: "oil-1",
          title: "OPEC 코멘트",
          eventType: "speech",
          category: "energy",
          country: "사우디",
          status: "published",
          importance: "high",
          importanceSource: "rule",
          eventDateKst: "2026-03-15",
          eventTimeKst: "2026-03-15T00:00:00Z",
          eventTimePrecision: "time",
          previousEventTimeKst: null,
          revisionNote: null,
          whyItMattersKo: "유가 변동성에 직접 연결됩니다.",
          source: { key: "opec", name: "OPEC", url: null, updatedAt: "2026-03-15T00:00:00Z" },
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
          updatedAt: "2026-03-15T00:00:00Z",
        },
      ],
      derivativesSummary,
      derivativesTrends: emptyDerivativesTrends(),
      derivativesInvestorFlow: emptyDerivativesInvestorFlow(),
      updatedAt: "2026-03-15T02:20:00Z",
    });

    render(await KrxInsightsPage());

    expect(screen.getByRole("heading", { name: "AI 인사이트" })).toBeInTheDocument();
    expect(screen.getByText("오늘의 해석")).toBeInTheDocument();
    expect(screen.getByText("근거")).toBeInTheDocument();
    expect(screen.getByText("반대 근거")).toBeInTheDocument();
    expect(screen.getByText("해석이 바뀌는 조건")).toBeInTheDocument();
    expect(screen.getAllByText("파생 기준점")).toHaveLength(2);
    expect(screen.getByText("달러 강세 재확인")).toBeInTheDocument();
    expect(screen.getByText("OPEC 코멘트")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "매크로 캘린더 보기" })).toHaveAttribute("href", "/krx/macro-calendar");
    expect(screen.getByRole("progressbar", { name: "시장 심리" })).toHaveAttribute("aria-valuetext", "상방 우위");
    expect(screen.getByRole("progressbar", { name: "AI 확신도" })).toBeInTheDocument();
  });
});
