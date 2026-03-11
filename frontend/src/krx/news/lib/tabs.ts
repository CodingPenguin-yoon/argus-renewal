export const NEWS_TAB_PARAM = "tab";

export const NEWS_TAB_OPTIONS = [
  { key: "summary", label: "종합" },
  { key: "kr", label: "한국 증시" },
  { key: "global", label: "글로벌 증시" },
  { key: "disclosures", label: "공시" },
] as const;

export type NewsTabKey = (typeof NEWS_TAB_OPTIONS)[number]["key"];

const VALID_NEWS_TABS = new Set<NewsTabKey>(NEWS_TAB_OPTIONS.map((item) => item.key));

export function normalizeNewsTab(raw: string | string[] | null | undefined): NewsTabKey {
  const first = Array.isArray(raw) ? raw[0] : raw;
  if (!first) return "summary";
  const normalized = first.trim().toLowerCase();
  if (VALID_NEWS_TABS.has(normalized as NewsTabKey)) {
    return normalized as NewsTabKey;
  }
  return "summary";
}

export function newsTabHref(tab: NewsTabKey): string {
  const params = new URLSearchParams();
  if (tab !== "summary") {
    params.set(NEWS_TAB_PARAM, tab);
  }
  const query = params.toString();
  return query ? `/krx/news?${query}` : "/krx/news";
}
