import { ArgusV2OptionQuotesView } from "@/argus_v2/components/dashboard";
import { getArgusV2Dashboard, getArgusV2OptionQuotes } from "@/argus_v2/server/dashboard";

export const dynamic = "force-dynamic";

export default async function ArgusOptionQuotesPage() {
  const [data, optionQuotes] = await Promise.all([
    getArgusV2Dashboard(),
    getArgusV2OptionQuotes(),
  ]);

  return <ArgusV2OptionQuotesView data={data} optionQuotes={optionQuotes} />;
}
