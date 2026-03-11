import { NewsTabDashboard } from "@/krx/components/news/news-tab-dashboard";
import { normalizeNewsTab } from "@/krx/news/lib/tabs";
import { getNewsTabData } from "@/krx/server/data-service";

export const dynamic = "force-dynamic";

export default async function KrxNewsPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
} = {}) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const activeTab = normalizeNewsTab(resolvedSearchParams.tab);
  const data = await getNewsTabData();

  return <NewsTabDashboard {...data} activeTab={activeTab} />;
}
