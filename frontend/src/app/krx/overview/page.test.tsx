import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";

import KrxOverviewPage from "@/app/krx/overview/page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("krx overview page route", () => {
  it("redirects overview to the canonical dashboard route", async () => {
    await KrxOverviewPage();

    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/krx/dashboard");
  });
});
