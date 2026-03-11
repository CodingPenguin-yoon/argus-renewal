import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import KrxLayout from "@/app/krx/layout";
import { getAppHeaderData, getSearchIndex } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getSearchIndex: vi.fn(),
  getAppHeaderData: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/krx",
}));

describe("krx layout", () => {
  it("renders the shared header shell around tab content", async () => {
    vi.mocked(getSearchIndex).mockResolvedValue({
      stocks: [
        { ticker: "005930.KS", name: "삼성전자", market: "KR", sector: "반도체" },
      ],
      news: [
        {
          id: "krx-macro-001",
          type: "macro",
          title: "한국은행, 기준금리 동결 기조 재확인",
          summary: "테스트",
          whyItMatters: "시장 신호에 영향을 줍니다.",
          source: "Argus KRX Desk",
          sourceUrl: "https://example.com",
          publishedAt: "2026-03-10T01:30:00Z",
          sentiment: "neutral",
          importance: "high",
          relatedSectors: ["금융"],
          relatedTickers: ["105560.KS"],
          category: "금리",
          tags: ["금리"],
        },
      ],
    });

    vi.mocked(getAppHeaderData).mockResolvedValue({
      market: "krx",
      marketToneLine: "외국인 선물 매수 우위로 코스피 반등 시도가 이어지고 있습니다.",
      supportingPoints: [
        {
          text: "파생 해석은 상방 우위입니다.",
          sourceKey: "derivatives",
          sourceLabel: "KRX_DERIVATIVES",
          sourceUrl: null,
        },
      ],
      phase: "live",
      updatedAt: "2026-03-10T01:30:00Z",
      sourceCoverage: {
        state: "full",
        coverageRatio: 1,
        availableSources: 3,
        expectedSources: 3,
        summary: "모든 핵심 소스가 반영되었습니다.",
        items: [],
      },
      breakingNews: null,
    });

    const component = await KrxLayout({ children: <div>route body</div> });
    render(component);

    expect(screen.getByRole("link", { name: "시장 신호" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "파생" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "관심종목" })).toBeInTheDocument();
    expect(screen.getByText("오늘의 시장 톤")).toBeInTheDocument();
    expect(screen.getByText("route body")).toBeInTheDocument();
  });
});
