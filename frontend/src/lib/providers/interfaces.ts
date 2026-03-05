import { MarketEvent, News, Stock } from "@/types/domain";

export interface NewsProvider {
  getAllNews(): Promise<News[]>;
  getNewsById(id: string): Promise<News | null>;
  getNewsByTicker(ticker: string): Promise<News[]>;
  getMacroNews(): Promise<News[]>;
  getStockNews(): Promise<News[]>;
  searchNews(query: string): Promise<News[]>;
}

export interface MarketEventProvider {
  getUpcomingEvents(): Promise<MarketEvent[]>;
}

export interface StockProvider {
  getAllStocks(): Promise<Stock[]>;
  getStockByTicker(ticker: string): Promise<Stock | null>;
}
