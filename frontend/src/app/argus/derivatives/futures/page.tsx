import { ArgusV2FuturesView } from "@/argus_v2/components/dashboard";
import { getArgusV2Dashboard, getArgusV2Futures } from "@/argus_v2/server/dashboard";

export default async function ArgusFuturesPage() {
  const [data, futures] = await Promise.all([
    getArgusV2Dashboard(),
    getArgusV2Futures(),
  ]);

  return <ArgusV2FuturesView data={data} futures={futures} />;
}
