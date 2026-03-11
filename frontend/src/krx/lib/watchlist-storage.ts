import { MarketCode } from "@/krx/types/domain";
import { DEFAULT_MARKET } from "@/krx/lib/market";

const WATCHLIST_KEY_PREFIX = "argus.watchlist";

function isBrowser() {
  return typeof window !== "undefined";
}

function keyForMarket(market: MarketCode) {
  return `${WATCHLIST_KEY_PREFIX}.${market}`;
}

export function getWatchlist(market: MarketCode = DEFAULT_MARKET): string[] {
  if (!isBrowser()) return [];

  try {
    const raw = localStorage.getItem(keyForMarket(market));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveWatchlist(tickers: string[], market: MarketCode = DEFAULT_MARKET) {
  if (!isBrowser()) return;
  localStorage.setItem(keyForMarket(market), JSON.stringify([...new Set(tickers)]));
}

export function toggleWatchlist(ticker: string, market: MarketCode = DEFAULT_MARKET) {
  const current = getWatchlist(market);
  const exists = current.includes(ticker);
  const next = exists ? current.filter((item) => item !== ticker) : [...current, ticker];
  saveWatchlist(next, market);
  return next;
}
