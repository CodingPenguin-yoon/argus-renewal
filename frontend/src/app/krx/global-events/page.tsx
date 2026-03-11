import { GlobalEventsDashboard } from "@/krx/components/events/global-events-dashboard";
import { normalizeGlobalEventsTab } from "@/krx/global-events/lib/tabs";
import { getGlobalEventsTabData } from "@/krx/server/data-service";

export default async function KrxGlobalEventsPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
} = {}) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const activeTab = normalizeGlobalEventsTab(resolvedSearchParams.tab);
  const data = await getGlobalEventsTabData();

  return <GlobalEventsDashboard {...data} activeTab={activeTab} />;
}
