import { MarketCode } from "@/krx/types/domain";

export const DEFAULT_MARKET: MarketCode = "krx";

export function marketBasePath(market: MarketCode): string {
  return `/${market}`;
}

export function marketHref(market: MarketCode, subPath: string = ""): string {
  if (!subPath) {
    return marketBasePath(market);
  }
  return `${marketBasePath(market)}${subPath.startsWith("/") ? subPath : `/${subPath}`}`;
}
