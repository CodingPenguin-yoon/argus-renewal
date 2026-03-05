import { NEWS_ITEMS } from "@/lib/mock/seed-data";
import { News } from "@/types/domain";
import { NewsProvider } from "@/lib/providers/interfaces";
import { sortByPublishedAtDesc } from "@/lib/utils";

export class MockNewsProvider implements NewsProvider {
  async getAllNews(): Promise<News[]> {
    return sortByPublishedAtDesc(NEWS_ITEMS);
  }

  async getNewsById(id: string): Promise<News | null> {
    return NEWS_ITEMS.find((news) => news.id === id) ?? null;
  }

  async getNewsByTicker(ticker: string): Promise<News[]> {
    return sortByPublishedAtDesc(
      NEWS_ITEMS.filter((news) => news.relatedTickers.includes(ticker.toUpperCase())),
    );
  }

  async getMacroNews(): Promise<News[]> {
    return sortByPublishedAtDesc(NEWS_ITEMS.filter((news) => news.type === "macro"));
  }

  async getStockNews(): Promise<News[]> {
    return sortByPublishedAtDesc(NEWS_ITEMS.filter((news) => news.type === "stock"));
  }

  async searchNews(query: string): Promise<News[]> {
    const q = query.trim().toLowerCase();
    if (!q) return [];

    return sortByPublishedAtDesc(
      NEWS_ITEMS.filter((news) => {
        return (
          news.title.toLowerCase().includes(q) ||
          news.summary.toLowerCase().includes(q) ||
          news.relatedTickers.some((ticker) => ticker.toLowerCase().includes(q)) ||
          news.tags.some((tag) => tag.toLowerCase().includes(q))
        );
      }),
    );
  }
}
