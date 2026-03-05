import { env } from "@/lib/env";
import { MockMarketEventProvider } from "@/lib/providers/mock-market-event-provider";
import { MockNewsProvider } from "@/lib/providers/mock-news-provider";
import { MockStockProvider } from "@/lib/providers/mock-stock-provider";

const providers = {
  mock: {
    news: new MockNewsProvider(),
    marketEvents: new MockMarketEventProvider(),
    stocks: new MockStockProvider(),
  },
};

export const providerRegistry = providers[env.NEWS_PROVIDER];
