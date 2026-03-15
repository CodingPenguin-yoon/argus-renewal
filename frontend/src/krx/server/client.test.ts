import { afterEach, describe, expect, it, vi } from "vitest";

import { getKrxJson, getKrxJsonOrNull } from "@/krx/server/client";

vi.mock("@/krx/lib/env", () => ({
  env: {
    BACKEND_BASE_URL: "http://localhost:4000",
  },
}));

describe("krx server client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults to no-store fetches", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    } as Response);

    await getKrxJson("/market-signal/summary");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/market-signal/summary", {
      cache: "no-store",
    });
  });

  it("supports caller-scoped revalidate without changing defaults", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ item: {} }),
    } as Response);

    await getKrxJson("/derivatives/summary", { revalidate: 30 });

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/derivatives/summary", {
      next: { revalidate: 30 },
    });
  });

  it("keeps nullable 404 behavior with custom options", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response);

    await expect(getKrxJsonOrNull("/stocks/005930", { revalidate: 30 })).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:4000/api/krx/stocks/005930", {
      next: { revalidate: 30 },
    });
  });
});
