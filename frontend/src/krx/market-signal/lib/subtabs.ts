export const MARKET_SIGNAL_SUBTAB_PARAM = "subtab";
export const MARKET_SIGNAL_DEFAULT_SUBTAB = "summary";

export const MARKET_SIGNAL_SUBTAB_OPTIONS = [
  { key: "summary", label: "종합" },
  { key: "fund-flow", label: "자금 흐름" },
  { key: "derivatives", label: "파생상품" },
  { key: "checkpoints", label: "체크포인트" },
] as const;

export type MarketSignalSubtabKey = (typeof MARKET_SIGNAL_SUBTAB_OPTIONS)[number]["key"];

const VALID_SUBTABS = new Set<MarketSignalSubtabKey>(MARKET_SIGNAL_SUBTAB_OPTIONS.map((item) => item.key));

export function normalizeMarketSignalSubtab(raw: string | string[] | null | undefined): MarketSignalSubtabKey {
  const first = Array.isArray(raw) ? raw[0] : raw;
  if (!first) return MARKET_SIGNAL_DEFAULT_SUBTAB;
  const normalized = first.trim().toLowerCase();
  if (VALID_SUBTABS.has(normalized as MarketSignalSubtabKey)) {
    return normalized as MarketSignalSubtabKey;
  }
  return MARKET_SIGNAL_DEFAULT_SUBTAB;
}

export function marketSignalSubtabHref(tab: MarketSignalSubtabKey): string {
  const params = new URLSearchParams();
  if (tab !== MARKET_SIGNAL_DEFAULT_SUBTAB) {
    params.set(MARKET_SIGNAL_SUBTAB_PARAM, tab);
  }
  const query = params.toString();
  return query ? `/krx?${query}` : "/krx";
}
