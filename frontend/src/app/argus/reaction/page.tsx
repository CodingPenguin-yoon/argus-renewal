import { ArgusV2ReactionView } from "@/argus_v2/components/dashboard";
import { getArgusV2Dashboard } from "@/argus_v2/server/dashboard";

export const dynamic = "force-dynamic";

export default async function ArgusReactionPage() {
  const data = await getArgusV2Dashboard();

  return <ArgusV2ReactionView data={data} />;
}
