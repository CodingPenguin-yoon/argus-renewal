import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KrxNewsPage from "@/app/krx/news/page";
import { getNewsTabData } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getNewsTabData: vi.fn(),
}));

vi.mock("@/krx/news/components/news-tab-live-dashboard", () => ({
  NewsTabLiveDashboard: ({
    activeTab,
    initialData,
  }: {
    activeTab: string;
    initialData: ReturnType<typeof buildNewsFixture>;
  }) => (
    <div>
      <p data-testid="active-tab">{activeTab}</p>
      <p>{initialData.headerContext.summaryLine}</p>
      <p>{initialData.briefing.headline}</p>
      <p>{initialData.krCards[0]?.title}</p>
      <p>{initialData.globalCards[0]?.title}</p>
      <p>{initialData.disclosureCards[0]?.title}</p>
    </div>
  ),
}));

afterEach(() => {
  cleanup();
});

function buildNewsFixture() {
  return {
    krCards: [
      {
        id: "kr-card-1",
        title: "외국인 순매수 확대로 반도체 대형주 강세",
        oneLineSummary: "장 초반 외국인 수급이 유입되며 지수 상방 시도가 강화됐습니다.",
        whyItMatters: "수급 방향이 유지되면 국내 지수의 추세 복원 가능성이 커집니다.",
        marketImpact: "지수 상방 시도 강화",
        marketScope: "kr_market" as const,
        primaryRegion: "KR" as const,
        trustScore: 0.84,
        materialityScore: 0.76,
        noveltyScore: 0.63,
        attentionScore: 0.52,
        editorialScore: 0.81,
        storyState: "ONGOING" as const,
        importanceLabel: "high" as const,
        editorialReason: "외국인 수급과 반도체 강세가 메인 시장 표면에 직접 연결됩니다.",
        aiConfidence: 0.74,
        rankingScore: 0.88,
        evidenceCount: 3,
        crossSourceScore: 0.21,
        publishedAt: "2026-03-10T01:30:00Z",
        updatedAt: "2026-03-10T01:35:00Z",
        evidence: [],
        provenance: {},
      },
    ],
    globalCards: [
      {
        id: "global-card-1",
        title: "연준 위원 발언으로 달러 강세 재확인",
        oneLineSummary: "금리 인하 기대가 밀리며 원화 변동성이 커질 수 있습니다.",
        whyItMatters: "한국 증시의 외국인 수급과 환율 민감도에 직접 연결됩니다.",
        marketImpact: "환율 변동성 확대",
        marketScope: "global_market" as const,
        primaryRegion: "GLOBAL" as const,
        trustScore: 0.8,
        materialityScore: 0.69,
        noveltyScore: 0.54,
        attentionScore: 0.46,
        editorialScore: 0.73,
        storyState: "NEW" as const,
        importanceLabel: "medium" as const,
        editorialReason: "환율과 위험선호 전이에 영향을 주는 글로벌 변수입니다.",
        aiConfidence: 0.68,
        rankingScore: 0.85,
        evidenceCount: 2,
        crossSourceScore: 0.19,
        publishedAt: "2026-03-10T01:40:00Z",
        updatedAt: "2026-03-10T01:45:00Z",
        evidence: [],
        provenance: {},
      },
    ],
    disclosureCards: [
      {
        id: "disclosure-card-1",
        title: "삼성전자 공급계약 공시",
        oneLineSummary: "대형 공급계약 체결 공시가 확인됐습니다.",
        whyItMatters: "대형 수주 공시는 실적 가시성과 밸류에이션에 영향을 줄 수 있습니다.",
        marketImpact: "섹터 내 투자심리 개선 가능성",
        marketScope: "company" as const,
        primaryRegion: "KR" as const,
        trustScore: 0.92,
        materialityScore: 0.82,
        noveltyScore: 0.58,
        attentionScore: 0.49,
        editorialScore: 0.87,
        storyState: "DISCLOSURE_CONFIRMED" as const,
        importanceLabel: "high" as const,
        editorialReason: "공시 확인이 완료된 직접 이벤트입니다.",
        aiConfidence: 0.9,
        rankingScore: 0.91,
        evidenceCount: 2,
        crossSourceScore: 0.34,
        publishedAt: "2026-03-10T02:00:00Z",
        updatedAt: "2026-03-10T02:05:00Z",
        evidence: [
          {
            role: "PRIMARY" as const,
            provider: "DART" as const,
            title: "공급계약 체결",
            snippet: "최근 매출액 대비 4.8% 규모",
            publisher: "금융감독원 전자공시",
            sourceUrl: "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310000111",
            canonicalUrl: "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310000111",
            storagePolicy: "CANONICAL_EVENT" as const,
            publishedAt: "2026-03-10T01:58:00Z",
          },
        ],
        provenance: {},
      },
    ],
    briefing: {
      headline: "지금 시장 브리핑",
      summary: "국내 수급 회복과 글로벌 금리 변수를 함께 반영하는 구간입니다.",
      keyPoints: ["외국인 순매수 강화", "환율 변수 재확인", "핵심 공시 체크 필요"],
      linkedHeadlines: [
        {
          cardId: "kr-card-1",
          title: "외국인 순매수 확대로 반도체 대형주 강세",
          summary: "장 초반 외국인 수급이 유입되며 지수 상방 시도가 강화됐습니다.",
          marketScope: "kr_market" as const,
          primaryRegion: "KR" as const,
          publishedAt: "2026-03-10T01:35:00Z",
          sourceUrl: "https://example.com/kr-briefing",
          sourceLabel: "매일경제",
        },
      ],
      updatedAt: "2026-03-10T02:05:00Z",
      generationMethod: "llm" as const,
      aiConfidence: 0.81,
      aiProvider: "stub_editorial_ai",
      aiModel: "stub-model",
    },
    headerContext: {
      updatedAt: "2026-03-10T02:05:00Z",
      summaryLine: "국내 수급 회복, 글로벌 금리 변수, 핵심 공시를 함께 점검해야 하는 구간입니다.",
      coverage: {
        state: "partial" as const,
        coverageRatio: 0.75,
        availableSources: 3,
        expectedSources: 4,
        summary: "일부 소스가 부분 반영 상태입니다.",
      },
      columns: [
        { key: "KR" as const, label: "한국 증시", count: 1, leadTitle: "외국인 순매수 확대로 반도체 대형주 강세", leadScope: "kr_market" },
        { key: "GLOBAL" as const, label: "글로벌 증시", count: 1, leadTitle: "연준 위원 발언으로 달러 강세 재확인", leadScope: "global_market" },
      ],
    },
    coverage: {
      state: "partial" as const,
      coverageRatio: 0.75,
      availableSources: 3,
      expectedSources: 4,
      summary: "일부 소스가 부분 반영 상태입니다.",
      updatedAt: "2026-03-10T02:05:00Z",
      items: [],
    },
  };
}

describe("krx news page route", () => {
  it("renders flat tabs with summary default", async () => {
    vi.mocked(getNewsTabData).mockResolvedValue(buildNewsFixture());

    const component = await KrxNewsPage();
    render(component);

    expect(screen.getByTestId("active-tab")).toHaveTextContent("summary");
    expect(screen.getByText("국내 수급 회복, 글로벌 금리 변수, 핵심 공시를 함께 점검해야 하는 구간입니다.")).toBeInTheDocument();
    expect(screen.getByText("지금 시장 브리핑")).toBeInTheDocument();
    expect(screen.getByText("외국인 순매수 확대로 반도체 대형주 강세")).toBeInTheDocument();
    expect(screen.getByText("연준 위원 발언으로 달러 강세 재확인")).toBeInTheDocument();
    expect(screen.getByText("삼성전자 공급계약 공시")).toBeInTheDocument();
  });

  it("supports direct deep-link navigation to 뉴스 > 공시", async () => {
    vi.mocked(getNewsTabData).mockResolvedValue(buildNewsFixture());

    const component = await KrxNewsPage({
      searchParams: Promise.resolve({ tab: "disclosures" }),
    });
    render(component);

    expect(screen.getByTestId("active-tab")).toHaveTextContent("disclosures");
    expect(screen.getByText("삼성전자 공급계약 공시")).toBeInTheDocument();
  });
});
