import { OverviewDashboard } from "@/krx/overview/components/overview-dashboard";
import { getOverviewTabData } from "@/krx/server/data-service";

export default async function KrxDashboardPage() {
  const data = await getOverviewTabData();

  return <OverviewDashboard data={data} />;
}
