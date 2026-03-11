import { WatchlistManager } from "@/krx/components/watchlist/watchlist-manager";
import { getWatchlistPageData } from "@/krx/server/data-service";

export default async function KrxWatchlistPage() {
  const { stocks, news } = await getWatchlistPageData();

  return <WatchlistManager market="krx" stocks={stocks} news={news} />;
}
