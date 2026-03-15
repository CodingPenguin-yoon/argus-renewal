import { describe, expect, it, vi } from "vitest";

import { GET } from "@/app/api/krx/news-tab/route";
import { getNewsTabData } from "@/krx/server/data-service";
import type { NewsTabData } from "@/krx/types/domain";

vi.mock("@/krx/server/data-service", () => ({
  getNewsTabData: vi.fn(),
}));

function buildNewsTabData(): NewsTabData {
  return {
    krCards: [],
    globalCards: [],
    disclosureCards: [],
    briefing: {
      headline: "테스트 브리핑",
      summary: "테스트 요약",
      keyPoints: ["테스트 포인트"],
      linkedHeadlines: [],
      updatedAt: "2026-03-14T00:01:00Z",
      generationMethod: "rule_based",
      aiConfidence: 0,
      aiProvider: null,
      aiModel: null,
    },
    headerContext: {
      updatedAt: "2026-03-14T00:01:00Z",
      summaryLine: "테스트 헤더",
      coverage: {
        state: "partial",
        coverageRatio: 0.75,
        availableSources: 3,
        expectedSources: 4,
        summary: "일부 소스 반영",
      },
      columns: [
        { key: "KR", label: "한국 증시", count: 0, leadTitle: null, leadScope: null },
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

describe("GET /api/krx/news-tab", () => {
  it("returns the server payload with no-store caching headers", async () => {
    vi.mocked(getNewsTabData).mockResolvedValue(buildNewsTabData());

    const response = await GET();

    expect(response.headers.get("Cache-Control")).toBe("no-store, max-age=0");
    await expect(response.json()).resolves.toMatchObject({
      briefing: { headline: "테스트 브리핑" },
      headerContext: { summaryLine: "테스트 헤더" },
      coverage: { state: "partial" },
    });
  });
});
