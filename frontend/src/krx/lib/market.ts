import { MarketCode } from "@/krx/types/domain";

export const DEFAULT_MARKET: MarketCode = "krx";

export function marketBasePath(market: MarketCode): string {
  return `/${market}`;
}

export function marketOverviewPath(market: MarketCode): string {
  return `${marketBasePath(market)}/dashboard`;
}

export function marketInsightsPath(market: MarketCode): string {
  return `${marketBasePath(market)}/insights`;
}

export function marketMacroCalendarPath(market: MarketCode): string {
  return `${marketBasePath(market)}/macro-calendar`;
}

export function marketHref(market: MarketCode, subPath: string = ""): string {
  if (!subPath) {
    return marketBasePath(market);
  }
  return `${marketBasePath(market)}${subPath.startsWith("/") ? subPath : `/${subPath}`}`;
}
