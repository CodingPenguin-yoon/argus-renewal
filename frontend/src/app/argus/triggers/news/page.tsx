import { ArgusV2NewsFeedView } from "@/argus_v2/components/dashboard";
import { getArgusV2Dashboard, getArgusV2NewsFeed } from "@/argus_v2/server/dashboard";

export const dynamic = "force-dynamic";

export default async function ArgusNewsFeedPage() {
  const [data, newsFeed] = await Promise.all([
    getArgusV2Dashboard(),
    getArgusV2NewsFeed(),
  ]);

  return <ArgusV2NewsFeedView data={data} newsFeed={newsFeed} />;
}
