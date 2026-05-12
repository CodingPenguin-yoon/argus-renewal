import { marketDashboardSchema, type MarketDashboard } from "@/argus_v2/contracts/dashboard";
import { argusV2Env } from "@/argus_v2/lib/env";

const BACKEND_BASE_URL = argusV2Env.BACKEND_BASE_URL.replace(/\/+$/, "");

export async function getArgusV2Dashboard(): Promise<MarketDashboard> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/argus/v2/dashboard`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Argus v2 dashboard request failed (${response.status})`);
  }

  return marketDashboardSchema.parse(await response.json());
}

