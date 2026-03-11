import { describe, expect, it } from "vitest";

import {
  marketSignalSubtabHref,
  normalizeMarketSignalSubtab,
} from "@/krx/market-signal/lib/subtabs";

describe("market signal subtabs helpers", () => {
  it("normalizes unknown values to summary", () => {
    expect(normalizeMarketSignalSubtab(undefined)).toBe("summary");
    expect(normalizeMarketSignalSubtab("invalid")).toBe("summary");
    expect(normalizeMarketSignalSubtab(["derivatives", "summary"])).toBe("derivatives");
  });

  it("builds flat subtab deep-link hrefs", () => {
    expect(marketSignalSubtabHref("summary")).toBe("/krx");
    expect(marketSignalSubtabHref("fund-flow")).toBe("/krx?subtab=fund-flow");
    expect(marketSignalSubtabHref("derivatives")).toBe("/krx?subtab=derivatives");
    expect(marketSignalSubtabHref("checkpoints")).toBe("/krx?subtab=checkpoints");
  });
});
