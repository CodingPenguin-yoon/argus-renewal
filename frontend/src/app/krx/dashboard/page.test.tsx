import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KrxDashboardPage from "@/app/krx/dashboard/page";
import { getOverviewTabData } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getOverviewTabData: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

describe("krx dashboard page route", () => {
  it("renders app-wide dashboard content with canonical macro calendar links", async () => {
    vi.mocked(getOverviewTabData).mockResolvedValue({
      marketToneLine: "외국인 선물과 뉴스 표면이 함께 상방으로 기울고 있습니다.",
      keyTakeaways: ["외국인 선물 매수 지속", "뉴스 표면은 반도체와 환율 이슈 중심"],
      reportHeadline: "오늘의 종합 리포트",
      reportSummary: "시장 신호, 뉴스 표면, 매크로 캘린더를 한 번에 읽는 허브입니다.",
      reportUpdatedAt: "2026-03-15T02:10:00Z",
      reportLinks: [
        {
          title: "반도체 강세 기사",
          href: "https://example.com/news-1",
          sourceLabel: "매일경제",
          publishedAt: "2026-03-15T02:00:00Z",
        },
      ],
      macroWidgets: [
        {
          key: "환율",
          label: "환율",
          summary: "달러 강세가 외국인 수급에 부담입니다.",
          sourceLabel: "연합뉴스",
          updatedAt: "2026-03-15T02:05:00Z",
          tone: "negative",
        },
        {
          key: "유가/에너지",
          label: "WTI·에너지",
          summary: "유가 반등이 비용 변수로 작용합니다.",
          sourceLabel: "Reuters",
          updatedAt: "2026-03-15T02:03:00Z",
          tone: "negative",
        },
        {
          key: "금리",
          label: "금리",
          summary: "미 10년물 흐름이 밸류에이션 민감도를 자극합니다.",
          sourceLabel: "연준 모니터",
          updatedAt: "2026-03-15T02:01:00Z",
          tone: "neutral",
        },
      ],
      gatewayPanels: [
        {
          key: "market-signal",
          title: "시장 신호",
          href: "/krx",
          summary: "수급과 파생을 함께 봅니다.",
          metricLabel: "신뢰도",
          metricValue: "HIGH",
          updatedAt: "2026-03-15T02:10:00Z",
        },
        {
          key: "news",
          title: "시장 뉴스",
          href: "/krx/news",
          summary: "핵심 카드 12건 반영",
          metricLabel: "핵심 카드",
          metricValue: "12건",
          updatedAt: "2026-03-15T02:10:00Z",
        },
        {
          key: "global-events",
          title: "매크로 캘린더",
          href: "/krx/macro-calendar",
          summary: "FOMC 발언 체크",
          metricLabel: "하이라이트",
          metricValue: "3건",
          updatedAt: "2026-03-15T02:10:00Z",
        },
      ],
      globalHighlights: [
        {
          id: "event-1",
          eventKey: "fed-1",
          title: "FOMC 위원 발언",
          eventType: "speech",
          category: "central_bank",
          country: "미국",
          status: "published",
          importance: "high",
          importanceSource: "rule",
          eventDateKst: "2026-03-15",
          eventTimeKst: "2026-03-15T01:00:00Z",
          eventTimePrecision: "time",
          previousEventTimeKst: null,
          revisionNote: null,
          whyItMattersKo: "달러와 위험선호 재평가에 연결됩니다.",
          source: { key: "fed", name: "Fed", url: null, updatedAt: "2026-03-15T01:00:00Z" },
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
          updatedAt: "2026-03-15T01:00:00Z",
        },
      ],
    });

    render(await KrxDashboardPage());

    expect(screen.getByRole("heading", { name: "대시보드" })).toBeInTheDocument();
    expect(screen.getByText("오늘의 종합 리포트")).toBeInTheDocument();
    expect(screen.getByText("거시 미니 위젯")).toBeInTheDocument();
    expect(screen.getByText("WTI·에너지")).toBeInTheDocument();
    expect(screen.getByText("체크포인트")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /시장 신호/ })).toHaveAttribute("href", "/krx");
    expect(screen.getByRole("link", { name: /매크로 캘린더/ })).toHaveAttribute("href", "/krx/macro-calendar");
    expect(screen.getByText("FOMC 위원 발언")).toBeInTheDocument();
  });
});
