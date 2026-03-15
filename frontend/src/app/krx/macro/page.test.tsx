import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";

import KrxMacroPage from "@/app/krx/macro/page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("krx macro page route", () => {
  it("redirects macro to the canonical insights route", async () => {
    await KrxMacroPage();

    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/krx/insights");
  });
});
