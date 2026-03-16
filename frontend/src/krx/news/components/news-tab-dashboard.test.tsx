import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { NewsTabDashboard } from "@/krx/news/components/news-tab-dashboard";
import type { MarketNewsCard, NewsTabData } from "@/krx/types/domain";

function buildCard(index: number): MarketNewsCard {
  return {
    id: `kr-card-${index}`,
    title: `한국 증시 ${String(7 - index).padStart(2, "0")}:00 카드`,
    oneLineSummary: `요약 ${index}`,
    whyItMatters: `중요성 ${index}`,
    marketImpact: `영향 ${index}`,
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
    rankingScore: 1 - index * 0.01,
    evidenceCount: 2,
    crossSourceScore: 0.2,
    publishedAt: `2026-03-15T0${7 - index}:00:00Z`,
    updatedAt: `2026-03-15T0${7 - index}:01:00Z`,
    evidence: [
      {
        role: "PRIMARY",
        provider: "MK_RSS",
        title: `원문 ${index}`,
        snippet: `근거 ${index}`,
        publisher: "매일경제",
        sourceUrl: `https://example.com/kr-${index}`,
        canonicalUrl: `https://example.com/kr-${index}`,
        storagePolicy: "PERSISTENT_EVIDENCE",
        publishedAt: `2026-03-15T0${7 - index}:00:00Z`,
      },
    ],
    provenance: {},
  };
}

function buildFixture(): NewsTabData {
  return {
    krCards: Array.from({ length: 6 }, (_, index) => buildCard(index + 1)),
    globalCards: [],
    disclosureCards: [],
    briefing: {
      headline: "외국인 수급과 환율 변수를 함께 봐야 하는 장세입니다.",
      summary:
        "국내에서는 반도체와 외국인 수급이 주도하고 있습니다.\n\n동시에 환율 변수는 장중 변동성 요인이라 수급 해석을 함께 봐야 합니다.\n\n따라서 주도 업종의 강세 지속과 환율 반응을 같이 확인하는 흐름입니다.",
      keyPoints: [
        "반도체와 외국인 수급이 주도 흐름입니다.",
        "환율 변수는 장중 변동성 확대 요인입니다.",
        "환율 변수는 장중 변동성 확대 요인입니다.",
      ],
      linkedHeadlines: [
        {
          cardId: "kr-card-1",
          title: "외국인 순매수 확대로 반도체 대형주 강세",
          summary: "국내 핵심 섹터와 수급이 동시에 개선됐습니다.",
          marketScope: "kr_market",
          primaryRegion: "KR",
          publishedAt: "2026-03-15T06:01:00Z",
          sourceUrl: "https://example.com/lead-link",
          sourceLabel: "매일경제",
        },
      ],
      updatedAt: "2026-03-15T06:05:00Z",
      generationMethod: "llm",
      aiConfidence: 0.84,
      aiProvider: "stub_editorial_ai",
      aiModel: "stub-model",
    },
    headerContext: {
      updatedAt: "2026-03-15T00:01:00Z",
      summaryLine: "한국 증시 누적형 테스트",
      coverage: {
        state: "partial",
        coverageRatio: 0.75,
        availableSources: 3,
        expectedSources: 4,
        summary: "일부 소스 반영",
      },
      columns: [
        { key: "KR", label: "한국 증시", count: 6, leadTitle: "한국 증시 카드 1", leadScope: "kr_market" },
        { key: "GLOBAL", label: "글로벌 증시", count: 0, leadTitle: null, leadScope: null },
      ],
    },
    coverage: {
      state: "partial",
      coverageRatio: 0.75,
      availableSources: 3,
      expectedSources: 4,
      summary: "일부 소스 반영",
      updatedAt: "2026-03-15T00:01:00Z",
      items: [],
    },
  };
}

function KrTabHarness() {
  const data = buildFixture();
  const [krPage, setKrPage] = useState(0);
  const krPageSize = 5;
  const krPageCount = Math.ceil(data.krCards.length / krPageSize);

  return (
    <NewsTabDashboard
      {...data}
      activeTab="kr"
      krPage={krPage}
      krPageSize={krPageSize}
      krPageCount={krPageCount}
      onKrPagePrevious={() => setKrPage((current) => Math.max(current - 1, 0))}
      onKrPageNext={() => setKrPage((current) => Math.min(current + 1, krPageCount - 1))}
    />
  );
}

describe("NewsTabDashboard", () => {
  it("renders the rolling summary briefing with linked headlines", () => {
    const data = buildFixture();

    render(
      <NewsTabDashboard
        {...data}
        activeTab="summary"
        krPage={0}
        krPageSize={5}
        krPageCount={2}
        onKrPagePrevious={() => {}}
        onKrPageNext={() => {}}
      />,
    );

    expect(screen.getAllByText("오늘 핵심 스토리").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("스토리 종합 브리핑")).toBeInTheDocument();
    expect(screen.getByText("스토리 해설")).toBeInTheDocument();
    expect(screen.getByText("오늘 체크할 변수")).toBeInTheDocument();
    expect(screen.getByText("참고 기사와 공시")).toBeInTheDocument();
    expect(screen.getByText("외국인 수급과 환율 변수를 함께 봐야 하는 장세입니다.")).toBeInTheDocument();
    expect(screen.getAllByText("외국인 순매수 확대로 반도체 대형주 강세").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("근거 2건")).toBeInTheDocument();
    expect(screen.getAllByText("환율 변수는 장중 변동성 확대 요인입니다.")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "외국인 순매수 확대로 반도체 대형주 강세" })).toHaveAttribute(
      "href",
      "https://example.com/lead-link",
    );
  });

  it("renders unsafe or missing briefing URLs as non-clickable text", () => {
    const data = buildFixture();
    data.briefing.linkedHeadlines = [
      {
        cardId: "kr-card-unsafe",
        title: "안전하지 않은 링크 기사",
        summary: "javascript 링크는 클릭 불가 텍스트로 내려야 합니다.",
        marketScope: "kr_market",
        primaryRegion: "KR",
        publishedAt: "2026-03-15T06:01:00Z",
        sourceUrl: "javascript:alert('xss')",
        sourceLabel: "매일경제",
      },
      {
        cardId: "kr-card-no-url",
        title: "원문 링크 없는 중요 기사",
        summary: "링크가 없어도 항목은 남아야 합니다.",
        marketScope: "kr_market",
        primaryRegion: "KR",
        publishedAt: "2026-03-15T06:02:00Z",
        sourceUrl: null,
        sourceLabel: "원문 링크 없음",
      },
    ];

    render(
      <NewsTabDashboard
        {...data}
        activeTab="summary"
        krPage={0}
        krPageSize={5}
        krPageCount={2}
        onKrPagePrevious={() => {}}
        onKrPageNext={() => {}}
      />,
    );

    expect(screen.getAllByText("오늘 핵심 스토리").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole("link", { name: "안전하지 않은 링크 기사" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "원문 링크 없는 중요 기사" })).not.toBeInTheDocument();
    expect(screen.getAllByText("안전하지 않은 링크 기사").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("원문 링크 없는 중요 기사").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the KR accumulated feed in 5-card chronological pages and moves to the next page on click", async () => {
    const user = userEvent.setup();

    render(<KrTabHarness />);

    expect(screen.getByText("한국 증시 06:00 카드")).toBeInTheDocument();
    expect(screen.getByText("한국 증시 02:00 카드")).toBeInTheDocument();
    expect(screen.queryByText("한국 증시 01:00 카드")).not.toBeInTheDocument();
    expect(screen.getByText("1-5 / 6건")).toBeInTheDocument();
    expect(screen.getByText("한국 증시에 직접 연결되는 카드를 최신 시각 순으로 누적하고, 5개씩 넘겨 보도록 구성했습니다.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "다음 5개" }));

    expect(screen.getByText("한국 증시 01:00 카드")).toBeInTheDocument();
    expect(screen.getByText("6-6 / 6건")).toBeInTheDocument();
  });
});
