import { STOCKS } from "@/lib/mock/seed-data";
import { StockProvider } from "@/lib/providers/interfaces";

export class MockStockProvider implements StockProvider {
  async getAllStocks() {
    return STOCKS;
  }

  async getStockByTicker(ticker: string) {
    return STOCKS.find((stock) => stock.ticker.toUpperCase() === ticker.toUpperCase()) ?? null;
  }
}
