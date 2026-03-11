import { describe, expect, it } from "vitest";

import { normalizePageView, pageViewHref } from "@/krx/lib/page-view";

describe("page view helpers", () => {
  it("normalizes view params with fallback", () => {
    expect(normalizePageView(undefined)).toBe("home");
    expect(normalizePageView("detail")).toBe("detail");
    expect(normalizePageView("unknown", "detail")).toBe("detail");
  });

  it("builds stable view hrefs", () => {
    expect(pageViewHref("/krx/news", "home")).toBe("/krx/news");
    expect(pageViewHref("/krx/news", "detail")).toBe("/krx/news?view=detail");
    expect(pageViewHref("/krx", "detail", { subtab: "derivatives" })).toBe(
      "/krx?view=detail&subtab=derivatives",
    );
  });
});
