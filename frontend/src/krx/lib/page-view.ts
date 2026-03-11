export const PAGE_VIEW_PARAM = "view";

export type PageView = "home" | "detail";

export function normalizePageView(
  raw: string | string[] | null | undefined,
  fallback: PageView = "home",
): PageView {
  const first = Array.isArray(raw) ? raw[0] : raw;
  if (!first) return fallback;
  const normalized = first.trim().toLowerCase();
  if (normalized === "home" || normalized === "detail") {
    return normalized;
  }
  return fallback;
}

export function pageViewHref(
  basePath: string,
  view: PageView,
  extraParams: Record<string, string | undefined> = {},
): string {
  const params = new URLSearchParams();
  if (view !== "home") {
    params.set(PAGE_VIEW_PARAM, view);
  }
  for (const [key, value] of Object.entries(extraParams)) {
    if (value) {
      params.set(key, value);
    }
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}
