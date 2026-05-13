import { marketDashboardSchema, newsFeedResponseSchema, type MarketDashboard, type NewsFeedResponse } from "@/argus_v2/contracts/dashboard";
import { argusV2Env } from "@/argus_v2/lib/env";

const BACKEND_BASE_URL = argusV2Env.BACKEND_BASE_URL.replace(/\/+$/, "");

export async function getArgusV2Dashboard(): Promise<MarketDashboard> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/argus/v2/dashboard`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Argus v2 dashboard request failed (${response.status})`);
  }

  return marketDashboardSchema.parse(await response.json());
}

export async function getArgusV2NewsFeed(): Promise<NewsFeedResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/argus/v2/news-feed`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Argus v2 news feed request failed (${response.status})`);
  }

  return newsFeedResponseSchema.parse(await response.json());
}
