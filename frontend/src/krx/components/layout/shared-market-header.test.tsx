import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SharedMarketHeader } from "@/krx/components/layout/shared-market-header";
import { AppHeader } from "@/krx/types/domain";

function makeHeader(overrides: Partial<AppHeader> = {}): AppHeader {
  return {
    market: "krx",
    marketToneLine: "외국인 선물 포지션이 상방 우위를 가리키며 코스피 반등 시도가 이어지고 있습니다.",
    supportingPoints: [
      {
        text: "파생 해석은 상방 우위이며 현재 신뢰도는 중간 수준입니다.",
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
      items: [
        {
          key: "news",
          label: "뉴스 해석",
          status: "available",
          sourceName: "Argus KRX Desk",
          sourceUrl: "https://example.com",
          updatedAt: "2026-03-10T01:30:00Z",
        },
      ],
    },
    breakingNews: null,
    ...overrides,
  };
}

describe("shared market header", () => {
  it("renders the shared interpretation header", () => {
    render(<SharedMarketHeader data={makeHeader()} />);

    expect(screen.getByText("오늘의 시장 톤")).toBeInTheDocument();
    expect(screen.getByText(/외국인 선물 포지션이 상방 우위를 가리키며/)).toBeInTheDocument();
    expect(screen.getByText("소스 커버리지")).toBeInTheDocument();
    expect(screen.getByText("모든 핵심 소스가 반영되었습니다.")).toBeInTheDocument();
  });

  it("hides the breaking layer when there is no breaking item", () => {
    render(<SharedMarketHeader data={makeHeader({ breakingNews: null })} />);

    expect(screen.queryByText("속보")).not.toBeInTheDocument();
  });

  it("shows the breaking layer when a breaking item exists", () => {
    render(
      <SharedMarketHeader
        data={makeHeader({
          breakingNews: {
            label: "속보",
            headline: "미 CPI 예상 상회",
            whyItMattersOneLine: "금리 인하 기대가 후퇴할 수 있습니다.",
            impactScope: "한국 증시",
            relatedTabLink: "/krx/news",
            sourceName: "Argus KRX Desk",
            sourceUrl: "https://example.com/breaking",
            publishedAt: "2026-03-10T01:30:00Z",
          },
        })}
      />,
    );

    expect(screen.getByText("속보")).toBeInTheDocument();
    expect(screen.getByText("미 CPI 예상 상회")).toBeInTheDocument();
    expect(screen.getByText("연결 탭: 뉴스")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "관련 탭 보기" })).toHaveAttribute("href", "/krx/news");
  });

  it("shows only the first three supporting points", () => {
    render(
      <SharedMarketHeader
        data={makeHeader({
          supportingPoints: [
            { text: "근거 1", sourceKey: "a", sourceLabel: "A", sourceUrl: null },
            { text: "근거 2", sourceKey: "b", sourceLabel: "B", sourceUrl: null },
            { text: "근거 3", sourceKey: "c", sourceLabel: "C", sourceUrl: null },
            { text: "근거 4", sourceKey: "d", sourceLabel: "D", sourceUrl: null },
          ],
        })}
      />,
    );

    expect(screen.getByText("근거 1")).toBeInTheDocument();
    expect(screen.getByText("근거 2")).toBeInTheDocument();
    expect(screen.getByText("근거 3")).toBeInTheDocument();
    expect(screen.queryByText("근거 4")).not.toBeInTheDocument();
  });
});
