import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";

import KrxGlobalEventsPage from "@/app/krx/global-events/page";
vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("krx global events page route", () => {
  it("redirects global-events to the canonical macro calendar route", async () => {
    await KrxGlobalEventsPage();

    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/krx/macro-calendar");
  });

  it("preserves tab query params when redirecting to macro calendar", async () => {
    await KrxGlobalEventsPage({
      searchParams: Promise.resolve({ tab: "next-24h" }),
    });

    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/krx/macro-calendar?tab=next-24h");
  });
});
