import { beforeEach, describe, expect, it } from "vitest";

import { getWatchlist, saveWatchlist, toggleWatchlist } from "@/krx/lib/watchlist-storage";

describe("krx watchlist storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("persists and reads watchlist", () => {
    saveWatchlist(["005930.KS", "000660.KS"]);
    expect(getWatchlist()).toEqual(["005930.KS", "000660.KS"]);
  });

  it("toggles ticker", () => {
    expect(toggleWatchlist("005930.KS")).toEqual(["005930.KS"]);
    expect(toggleWatchlist("005930.KS")).toEqual([]);
  });

  it("removes duplicates on save", () => {
    saveWatchlist(["005930.KS", "005930.KS", "000660.KS"]);
    expect(getWatchlist()).toEqual(["005930.KS", "000660.KS"]);
  });
});
