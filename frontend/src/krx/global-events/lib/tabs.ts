export const GLOBAL_EVENTS_TAB_PARAM = "tab";

export const GLOBAL_EVENTS_BASE_TAB_OPTIONS = [
  { key: "summary", label: "종합" },
  { key: "highlights", label: "핵심 이벤트" },
  { key: "next-24h", label: "다음 24시간" },
  { key: "week", label: "이번 주" },
] as const;

export const GLOBAL_EVENTS_EARNINGS_TAB_OPTION = { key: "earnings", label: "실적" } as const;

export type GlobalEventsTabKey =
  | (typeof GLOBAL_EVENTS_BASE_TAB_OPTIONS)[number]["key"]
  | typeof GLOBAL_EVENTS_EARNINGS_TAB_OPTION.key;

const VALID_GLOBAL_EVENTS_TABS = new Set<GlobalEventsTabKey>([
  ...GLOBAL_EVENTS_BASE_TAB_OPTIONS.map((item) => item.key),
  GLOBAL_EVENTS_EARNINGS_TAB_OPTION.key,
]);

export function normalizeGlobalEventsTab(raw: string | string[] | null | undefined): GlobalEventsTabKey {
  const first = Array.isArray(raw) ? raw[0] : raw;
  if (!first) return "summary";
  const normalized = first.trim().toLowerCase();
  if (VALID_GLOBAL_EVENTS_TABS.has(normalized as GlobalEventsTabKey)) {
    return normalized as GlobalEventsTabKey;
  }
  return "summary";
}

export function globalEventsTabHref(tab: GlobalEventsTabKey): string {
  const params = new URLSearchParams();
  if (tab !== "summary") {
    params.set(GLOBAL_EVENTS_TAB_PARAM, tab);
  }
  const query = params.toString();
  return query ? `/krx/global-events?${query}` : "/krx/global-events";
}
