import { describe, expect, it } from "vitest";

import { sortByPublishedAtDesc } from "@/lib/utils";

describe("utils", () => {
  it("sorts by published date descending", () => {
    const sorted = sortByPublishedAtDesc([
      { id: "1", publishedAt: "2026-03-03T10:00:00.000Z" },
      { id: "2", publishedAt: "2026-03-04T10:00:00.000Z" },
      { id: "3", publishedAt: "2026-03-02T10:00:00.000Z" },
    ]);

    expect(sorted.map((item) => item.id)).toEqual(["2", "1", "3"]);
  });
});
