import { describe, expect, it } from "vitest";

import {
  globalEventsTabHref,
  normalizeGlobalEventsTab,
} from "@/krx/global-events/lib/tabs";

describe("global events tabs helpers", () => {
  it("normalizes unknown values to summary", () => {
    expect(normalizeGlobalEventsTab(undefined)).toBe("summary");
    expect(normalizeGlobalEventsTab("unknown")).toBe("summary");
    expect(normalizeGlobalEventsTab(["next-24h", "week"])).toBe("next-24h");
  });

  it("builds stable deep-link hrefs", () => {
    expect(globalEventsTabHref("summary")).toBe("/krx/macro-calendar");
    expect(globalEventsTabHref("highlights")).toBe("/krx/macro-calendar?tab=highlights");
    expect(globalEventsTabHref("next-24h")).toBe("/krx/macro-calendar?tab=next-24h");
    expect(globalEventsTabHref("week")).toBe("/krx/macro-calendar?tab=week");
    expect(globalEventsTabHref("earnings")).toBe("/krx/macro-calendar?tab=earnings");
  });
});
