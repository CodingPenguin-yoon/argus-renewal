import {
  marketFlowDashboardSchema,
  type MarketFlowDashboard,
} from "@/market_terminal/contracts/market-flow";
import { marketTerminalEnv } from "@/market_terminal/lib/env";

const BACKEND_BASE_URL = marketTerminalEnv.BACKEND_BASE_URL.replace(/\/+$/, "");

export async function getMarketFlowDashboard(): Promise<MarketFlowDashboard> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/market-data/v1/dashboard/market-flow?data_mode=mock`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Market flow request failed (${response.status})`);
  }

  return marketFlowDashboardSchema.parse(await response.json());
}

