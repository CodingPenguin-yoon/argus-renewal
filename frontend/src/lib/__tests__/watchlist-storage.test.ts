import { beforeEach, describe, expect, it } from "vitest";

import { getWatchlist, saveWatchlist, toggleWatchlist } from "@/lib/watchlist-storage";

describe("watchlist storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("persists and reads watchlist", () => {
    saveWatchlist(["AAPL", "NVDA"]);
    expect(getWatchlist()).toEqual(["AAPL", "NVDA"]);
  });

  it("toggles ticker", () => {
    expect(toggleWatchlist("AAPL")).toEqual(["AAPL"]);
    expect(toggleWatchlist("AAPL")).toEqual([]);
  });

  it("removes duplicates on save", () => {
    saveWatchlist(["AAPL", "AAPL", "TSLA"]);
    expect(getWatchlist()).toEqual(["AAPL", "TSLA"]);
  });
});
