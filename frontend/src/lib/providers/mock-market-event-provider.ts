import { MARKET_EVENTS } from "@/lib/mock/seed-data";
import { MarketEventProvider } from "@/lib/providers/interfaces";

export class MockMarketEventProvider implements MarketEventProvider {
  async getUpcomingEvents() {
    return [...MARKET_EVENTS].sort(
      (a, b) => new Date(a.eventDate).getTime() - new Date(b.eventDate).getTime(),
    );
  }
}
