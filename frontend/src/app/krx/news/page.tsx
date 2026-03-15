import { NewsTabLiveDashboard } from "@/krx/news/components/news-tab-live-dashboard";
import { NewsTabScrollReset } from "@/krx/news/components/news-tab-scroll-reset";
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

  return (
    <>
      <NewsTabScrollReset />
      <NewsTabLiveDashboard initialData={data} activeTab={activeTab} />
    </>
  );
}
