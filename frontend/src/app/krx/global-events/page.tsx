import { redirect } from "next/navigation";

export default async function KrxGlobalEventsPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
} = {}) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const params = new URLSearchParams();
  const tab = Array.isArray(resolvedSearchParams.tab) ? resolvedSearchParams.tab[0] : resolvedSearchParams.tab;
  if (tab) {
    params.set("tab", tab);
  }
  const query = params.toString();
  redirect(query ? `/krx/macro-calendar?${query}` : "/krx/macro-calendar");
}
