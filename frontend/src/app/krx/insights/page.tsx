import { MacroDashboard } from "@/krx/macro/components/macro-dashboard";
import { getAppHeaderData, getMacroTabData } from "@/krx/server/data-service";

export default async function KrxInsightsPage() {
  const [data, headerData] = await Promise.all([getMacroTabData(), getAppHeaderData()]);

  return <MacroDashboard data={data} headerData={headerData} />;
}
