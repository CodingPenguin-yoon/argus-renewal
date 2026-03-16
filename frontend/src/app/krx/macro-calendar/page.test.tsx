import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import KrxMacroCalendarPage from "@/app/krx/macro-calendar/page";
import { getGlobalEventsTabData } from "@/krx/server/data-service";

vi.mock("@/krx/server/data-service", () => ({
  getGlobalEventsTabData: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

function makeEvent({
  eventKey,
  title,
  eventType,
  category,
  eventTimeKst,
}: {
  eventKey: string;
  title: string;
  eventType: string;
  category: string;
  eventTimeKst: string | null;
}) {
  return {
    id: eventKey,
    eventKey,
    title,
    eventType,
    category,
    country: "US",
    status: "scheduled",
    importance: "high" as const,
    importanceSource: "rule_based",
    eventDateKst: "2026-03-11",
    eventTimeKst,
    eventTimePrecision: eventTimeKst ? ("time" as const) : ("date" as const),
    previousEventTimeKst: null,
    revisionNote: null,
    whyItMattersKo: "한국 증시에 파급될 수 있는 핵심 이벤트입니다.",
    source: {
      key: "UNIT_TEST_SOURCE",
      name: "Unit Test Source",
      url: "https://example.com",
      updatedAt: "2026-03-10T00:10:00Z",
    },
    release: {
      metricCode: null,
      state: "scheduled",
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
    impact: {
      summaryKo: "환율과 외국인 수급 경로를 통해 국내 시장 변동성에 영향을 줄 수 있습니다.",
      tone: "mixed" as const,
      impactChannels: ["USD/KRW", "외국인 수급"],
      generationMethod: "rule_based" as const,
      providerName: null,
      modelName: null,
    },
    provenance: {},
    updatedAt: "2026-03-10T00:12:00Z",
  };
}

function buildFixture({ includeEarnings, includeEvents = true }: { includeEarnings: boolean; includeEvents?: boolean }) {
  const cpi = makeEvent({
    eventKey: "BLS:CPI:2026-02",
    title: "미국 CPI",
    eventType: "CPI",
    category: "inflation",
    eventTimeKst: "2026-03-11T21:30:00+09:00",
  });
  const earnings = makeEvent({
    eventKey: "NASDAQ:NVDA:2026-Q1",
    title: "NVIDIA 실적",
    eventType: "EARNINGS",
    category: "earnings",
    eventTimeKst: null,
  });

  return {
    highlights: includeEvents ? [cpi] : [],
    upcoming: includeEvents ? [cpi] : [],
    week: includeEvents ? (includeEarnings ? [cpi, earnings] : [cpi]) : [],
    coverage: {
      state: "partial" as const,
      coverageRatio: 0.8,
      availableSources: 4,
      expectedSources: 5,
      summary: "필수 소스 일부가 부분 반영 상태입니다.",
      updatedAt: "2026-03-10T00:12:00Z",
      items: [
        {
          sourceKey: "FED_CALENDAR",
          sourceName: "Federal Reserve Calendar",
          sourceKind: "schedule" as const,
          isRequired: true,
          status: "available" as const,
          availableCount: 2,
          expectedCount: 2,
          coverageRatio: 1,
          eventTypes: ["FOMC"],
          lastSyncedAt: "2026-03-10T00:10:00Z",
          lastSuccessAt: "2026-03-10T00:10:00Z",
          sourceUrl: "https://www.federalreserve.gov",
          note: null,
          metadata: {},
        },
      ],
    },
  };
}

describe("krx macro calendar page route", () => {
  it("renders flat tabs with summary default and conditional earnings tab", async () => {
    vi.mocked(getGlobalEventsTabData).mockResolvedValue(buildFixture({ includeEarnings: true }));

    const component = await KrxMacroCalendarPage();
    render(component);

    expect(screen.getByRole("tab", { name: "종합" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "핵심 이벤트" })).toHaveAttribute("href", "/krx/macro-calendar?tab=highlights");
    expect(screen.getByRole("tab", { name: "다음 24시간" })).toHaveAttribute("href", "/krx/macro-calendar?tab=next-24h");
    expect(screen.getByRole("tab", { name: "이번 주" })).toHaveAttribute("href", "/krx/macro-calendar?tab=week");
    expect(screen.getByRole("tab", { name: "실적" })).toHaveAttribute("href", "/krx/macro-calendar?tab=earnings");
    expect(screen.queryByRole("tab", { name: "홈" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "세부" })).not.toBeInTheDocument();
    expect(screen.getByText("이번 주 핵심 촉매")).toBeInTheDocument();
    expect(screen.getByText("다음 24시간 주목 이벤트")).toBeInTheDocument();
    expect(screen.getByText("한국 시장 영향 해석")).toBeInTheDocument();
    expect(screen.queryByText(/sync|cli|backfill/i)).not.toBeInTheDocument();
  });

  it("supports direct deep-link navigation to 매크로 캘린더 다음 24시간", async () => {
    vi.mocked(getGlobalEventsTabData).mockResolvedValue(buildFixture({ includeEarnings: true }));

    const component = await KrxMacroCalendarPage({
      searchParams: Promise.resolve({ tab: "next-24h" }),
    });
    render(component);

    expect(screen.getByRole("heading", { name: "다음 24시간" })).toBeInTheDocument();
    expect(screen.getByText("미국 CPI")).toBeInTheDocument();
  });

  it("hides earnings tab when no earnings data is available", async () => {
    vi.mocked(getGlobalEventsTabData).mockResolvedValue(buildFixture({ includeEarnings: false }));

    const component = await KrxMacroCalendarPage();
    render(component);

    expect(screen.queryByRole("tab", { name: "실적" })).not.toBeInTheDocument();
  });

  it("turns empty states into interpreted catalyst guidance", async () => {
    vi.mocked(getGlobalEventsTabData).mockResolvedValue(buildFixture({ includeEarnings: false, includeEvents: false }));

    const component = await KrxMacroCalendarPage();
    render(component);

    expect(screen.getByText("이번 주 대형 글로벌 촉매가 아직 보이지 않습니다")).toBeInTheDocument();
    expect(screen.getByText("다음 24시간 대형 글로벌 촉매 없음")).toBeInTheDocument();
    expect(screen.getAllByText(/내부 수급, 환율, 외국인 선물 변화 비중/).length).toBeGreaterThan(0);
  });
});
