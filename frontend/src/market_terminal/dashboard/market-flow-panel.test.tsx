import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarketFlowPanel } from "./market-flow-panel";
import type { MarketFlowDashboard, MarketFlowFact } from "../contracts/market-flow";

afterEach(cleanup);

function buildFact(
  quality: "estimate" | "confirmed",
  source: string,
): MarketFlowFact {
  return {
    source,
    source_record_id: `${source}:kospi_spot:${quality}:2026-07-22T10:30+09:00`,
    data_mode: "mock",
    is_live: false,
    market_scope: "KRX",
    quality,
    trade_date: "2026-07-22",
    observed_at: "2026-07-22T10:30:00+09:00",
    collected_at: "2026-07-22T10:30:00+09:00",
    freshness: "fresh",
    unit: "KRW",
    individual_net: -240_000_000_000,
    foreign_net: 150_000_000_000,
    institution_net: 90_000_000_000,
  };
}

function buildDashboard(): MarketFlowDashboard {
  return {
    as_of: "2026-07-22T10:30:00+09:00",
    data_mode: "mock",
    is_live: false,
    market_scope: "KRX",
    status: "fresh",
    rows: [
      {
        segment: "kospi_spot",
        label: "KOSPI 현물",
        status: "fresh",
        estimate: buildFact("estimate", "FIXTURE_BROKER"),
        confirmed: buildFact("confirmed", "FIXTURE_KRX"),
      },
    ],
  };
}

describe("MarketFlowPanel", () => {
  it("keeps mock data visibly separate from live data", () => {
    render(<MarketFlowPanel data={buildDashboard()} />);

    expect(screen.getByText("DEMO · NOT LIVE")).toBeInTheDocument();
    expect(screen.getByText("KOSPI 현물")).toBeInTheDocument();
    expect(screen.getByText("장중 추정")).toBeInTheDocument();
    expect(screen.getByText("마감 확정 · SIMULATED")).toBeInTheDocument();
    expect(screen.getByText("FIXTURE_BROKER")).toBeInTheDocument();
    expect(screen.getByText("FIXTURE_KRX")).toBeInTheDocument();
  });

  it("shows an explicit API failure instead of fixture fallback", () => {
    render(<MarketFlowPanel error="backend 연결 실패" />);

    expect(screen.getByRole("alert")).toHaveTextContent("시장 수급 API에 연결할 수 없습니다.");
    expect(screen.getByText("backend 연결 실패")).toBeInTheDocument();
    expect(screen.queryByText("DEMO · NOT LIVE")).not.toBeInTheDocument();
  });
});

