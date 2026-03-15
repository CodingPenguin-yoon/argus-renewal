import { afterEach, describe, expect, it, vi } from "vitest";

import { getMacroNews } from "@/krx/news/server/data-service";

vi.mock("@/krx/lib/env", () => ({
  env: {
    BACKEND_BASE_URL: "http://localhost:4000",
  },
}));

describe("macro news data service", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps macro news live by default", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    } as Response);

    await getMacroNews();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/news/macro", {
      cache: "no-store",
    });
  });

  it("supports caller-scoped revalidate for AI insights only", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    } as Response);

    await getMacroNews({ revalidate: 30 });

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/news/macro", {
      next: { revalidate: 30 },
    });
  });
});
