import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NewsTabLiveDashboard } from "@/krx/news/components/news-tab-live-dashboard";
import type { NewsTabData } from "@/krx/types/domain";

vi.mock("@/krx/news/components/news-tab-dashboard", () => ({
  NewsTabDashboard: ({
    briefing,
    krCards,
    globalCards,
    disclosureCards,
    headerContext,
    activeTab,
    krPage,
    krPageCount,
    onKrPageNext,
    onKrPagePrevious,
  }: NewsTabData & {
    activeTab: string;
    krPage: number;
    krPageCount: number;
    onKrPageNext: () => void;
    onKrPagePrevious: () => void;
  }) => (
    <div>
      <div data-testid="active-tab">{activeTab}</div>
      <div data-testid="summary-line">{headerContext.summaryLine}</div>
      <div data-testid="briefing-headline">{briefing.headline}</div>
      <div data-testid="kr-title">{krCards[0]?.title ?? "empty"}</div>
      <div data-testid="global-title">{globalCards[0]?.title ?? "empty"}</div>
      <div data-testid="disclosure-title">{disclosureCards[0]?.title ?? "empty"}</div>
      <div data-testid="kr-page">{krPage + 1}</div>
      <div data-testid="kr-page-count">{krPageCount}</div>
      <button type="button" onClick={onKrPagePrevious}>
        prev page
      </button>
      <button type="button" onClick={onKrPageNext}>
        next page
      </button>
    </div>
  ),
}));

function buildNewsTabData(leadTitle: string, krCount = 1): NewsTabData {
  return {
    krCards: Array.from({ length: krCount }, (_, index) => ({
      id: `${leadTitle}-kr-${index + 1}`,
      title: krCount === 1 ? leadTitle : `${leadTitle} ${index + 1}`,
      oneLineSummary: `${leadTitle} 요약 ${index + 1}`,
      whyItMatters: `${leadTitle} 중요성 ${index + 1}`,
      marketImpact: `${leadTitle} 영향 ${index + 1}`,
      marketScope: "kr_market",
      primaryRegion: "KR",
      trustScore: 0.8,
      materialityScore: 0.7,
      noveltyScore: 0.6,
      attentionScore: 0.5,
      editorialScore: 0.75,
      storyState: "ONGOING",
      importanceLabel: "high",
      editorialReason: null,
      aiConfidence: 0.7,
      rankingScore: 0.9 - index * 0.01,
      evidenceCount: 2,
      crossSourceScore: 0.2,
      publishedAt: "2026-03-14T00:00:00Z",
      updatedAt: "2026-03-14T00:01:00Z",
      evidence: [],
      provenance: {},
    })),
    globalCards: [],
    disclosureCards: [],
    briefing: {
      headline: `${leadTitle} 브리핑`,
      summary: `${leadTitle} 요약 브리핑`,
      keyPoints: [`${leadTitle} 포인트`],
      linkedHeadlines: [],
      updatedAt: "2026-03-14T00:01:00Z",
      generationMethod: "llm",
      aiConfidence: 0.75,
      aiProvider: "stub",
      aiModel: "stub-model",
    },
    headerContext: {
      updatedAt: "2026-03-14T00:01:00Z",
      summaryLine: `${leadTitle} 헤더`,
      coverage: {
        state: "partial",
        coverageRatio: 0.75,
        availableSources: 3,
        expectedSources: 4,
        summary: "일부 소스 반영",
      },
      columns: [
        { key: "KR", label: "한국 증시", count: 1, leadTitle, leadScope: "kr_market" },
        { key: "GLOBAL", label: "글로벌 증시", count: 0, leadTitle: null, leadScope: null },
      ],
    },
    coverage: {
      state: "partial",
      coverageRatio: 0.75,
      availableSources: 3,
      expectedSources: 4,
      summary: "일부 소스 반영",
      updatedAt: "2026-03-14T00:01:00Z",
      items: [],
    },
  };
}

describe("NewsTabLiveDashboard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("updates the rendered dashboard after a successful 60-second poll with the latest KR feed payload", async () => {
    const initialData = buildNewsTabData("초기 뉴스");
    const refreshedData = buildNewsTabData("갱신 뉴스");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => refreshedData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<NewsTabLiveDashboard initialData={initialData} activeTab="summary" />);

    expect(screen.getByTestId("kr-title")).toHaveTextContent("초기 뉴스");
    expect(screen.getByTestId("briefing-headline")).toHaveTextContent("초기 뉴스 브리핑");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(screen.getByTestId("kr-title")).toHaveTextContent("갱신 뉴스");
    expect(screen.getByTestId("briefing-headline")).toHaveTextContent("갱신 뉴스 브리핑");
    expect(fetchMock).toHaveBeenCalledWith("/api/krx/news-tab", { cache: "no-store" });
  });

  it("keeps the last successful dashboard when polling fails", async () => {
    const initialData = buildNewsTabData("초기 뉴스");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    });
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.stubGlobal("fetch", fetchMock);

    render(<NewsTabLiveDashboard initialData={initialData} activeTab="kr" />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("kr-title")).toHaveTextContent("초기 뉴스");
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
  });

  it("clamps the KR page when polling reduces the accumulated card count", async () => {
    const initialData = buildNewsTabData("초기 뉴스", 6);
    const refreshedData = buildNewsTabData("갱신 뉴스", 1);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => refreshedData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<NewsTabLiveDashboard initialData={initialData} activeTab="kr" />);

    expect(screen.getByTestId("kr-page")).toHaveTextContent("1");
    expect(screen.getByTestId("kr-page-count")).toHaveTextContent("2");
    await act(async () => {
      screen.getByRole("button", { name: "next page" }).click();
    });
    expect(screen.getByTestId("kr-page")).toHaveTextContent("2");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(screen.getByTestId("kr-page")).toHaveTextContent("1");
    expect(screen.getByTestId("kr-page-count")).toHaveTextContent("1");
    expect(screen.getByTestId("kr-title")).toHaveTextContent("갱신 뉴스");
  });
});
