import { describe, expect, it } from "vitest";

import { newsTabHref, normalizeNewsTab } from "@/krx/news/lib/tabs";

describe("news tabs helpers", () => {
  it("normalizes unknown values to summary", () => {
    expect(normalizeNewsTab(undefined)).toBe("summary");
    expect(normalizeNewsTab("unknown")).toBe("summary");
    expect(normalizeNewsTab(["disclosures", "kr"])).toBe("disclosures");
  });

  it("builds stable deep-link hrefs", () => {
    expect(newsTabHref("summary")).toBe("/krx/news");
    expect(newsTabHref("kr")).toBe("/krx/news?tab=kr");
    expect(newsTabHref("global")).toBe("/krx/news?tab=global");
    expect(newsTabHref("disclosures")).toBe("/krx/news?tab=disclosures");
  });
});
