import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";

import KrxDerivativesPage from "@/app/krx/derivatives/page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("krx derivatives route", () => {
  it("redirects to market signal derivatives subtab", async () => {
    await KrxDerivativesPage();

    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/krx?subtab=derivatives");
  });
});
