const WATCHLIST_KEY = "argus.watchlist";

function isBrowser() {
  return typeof window !== "undefined";
}

export function getWatchlist(): string[] {
  if (!isBrowser()) return [];

  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveWatchlist(tickers: string[]) {
  if (!isBrowser()) return;
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify([...new Set(tickers)]));
}

export function toggleWatchlist(ticker: string) {
  const current = getWatchlist();
  const exists = current.includes(ticker);
  const next = exists ? current.filter((item) => item !== ticker) : [...current, ticker];
  saveWatchlist(next);
  return next;
}
