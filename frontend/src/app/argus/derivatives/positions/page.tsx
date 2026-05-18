import { ArgusV2PositionsView } from "@/argus_v2/components/dashboard";
import { getArgusV2Dashboard, getArgusV2Futures, getArgusV2OptionQuotes } from "@/argus_v2/server/dashboard";

export const dynamic = "force-dynamic";

export default async function ArgusPositionsPage() {
  const [data, optionQuotes, futures] = await Promise.all([
    getArgusV2Dashboard(),
    getArgusV2OptionQuotes(),
    getArgusV2Futures(),
  ]);

  return <ArgusV2PositionsView data={data} optionQuotes={optionQuotes} futures={futures} />;
}
