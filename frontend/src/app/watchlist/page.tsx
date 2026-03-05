import { WatchlistManager } from "@/components/watchlist/watchlist-manager";
import { providerRegistry } from "@/lib/providers";

export default async function WatchlistPage() {
  const [stocks, news] = await Promise.all([
    providerRegistry.stocks.getAllStocks(),
    providerRegistry.news.getAllNews(),
  ]);

  return <WatchlistManager stocks={stocks} news={news} />;
}
