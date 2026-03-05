import { providerRegistry } from "@/lib/providers";
import { Importance, News, Sentiment } from "@/types/domain";

export async function getHomeData() {
  const [macroNews, allNews, events] = await Promise.all([
    providerRegistry.news.getMacroNews(),
    providerRegistry.news.getAllNews(),
    providerRegistry.marketEvents.getUpcomingEvents(),
  ]);

  return {
    macroNews,
    news: allNews,
    events,
  };
}

export async function getStockPageData(ticker: string) {
  const [stock, stockNews, macroNews] = await Promise.all([
    providerRegistry.stocks.getStockByTicker(ticker),
    providerRegistry.news.getNewsByTicker(ticker),
    providerRegistry.news.getMacroNews(),
  ]);

  return {
    stock,
    stockNews,
    relatedMacro: macroNews.filter((news) => news.relatedTickers.includes(ticker)).slice(0, 4),
  };
}

export async function getNewsDetail(id: string) {
  const [item, allNews] = await Promise.all([
    providerRegistry.news.getNewsById(id),
    providerRegistry.news.getAllNews(),
  ]);

  if (!item) return null;

  const related = allNews
    .filter((news) => news.id !== id)
    .filter(
      (news) =>
        news.category === item.category ||
        news.relatedTickers.some((ticker) => item.relatedTickers.includes(ticker)),
    )
    .slice(0, 5);

  return { item, related };
}

export async function getSearchIndex() {
  const [news, stocks] = await Promise.all([
    providerRegistry.news.getAllNews(),
    providerRegistry.stocks.getAllStocks(),
  ]);

  return {
    stocks,
    news: news.slice(0, 40),
  };
}

export function filterNewsBySentiment(news: News[], sentiment: Sentiment | "all") {
  if (sentiment === "all") return news;
  return news.filter((item) => item.sentiment === sentiment);
}

export function filterNewsByImportance(news: News[], importance: Importance | "all") {
  if (importance === "all") return news;
  return news.filter((item) => item.importance === importance);
}
