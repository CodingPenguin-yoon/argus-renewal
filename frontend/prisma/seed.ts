import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "@prisma/client";
import { MARKET_EVENTS, NEWS_ITEMS, STOCKS } from "../src/lib/mock/seed-data";

const adapter = new PrismaBetterSqlite3({
  url: process.env.DATABASE_URL ?? "file:./prisma/dev.db",
});

const prisma = new PrismaClient({ adapter });

async function main() {
  await prisma.newsStock.deleteMany();
  await prisma.marketEvent.deleteMany();
  await prisma.news.deleteMany();
  await prisma.stock.deleteMany();

  await prisma.stock.createMany({
    data: STOCKS.map((stock) => ({
      ticker: stock.ticker,
      name: stock.name,
      market: stock.market,
      sector: stock.sector,
    })),
  });

  await prisma.news.createMany({
    data: NEWS_ITEMS.map((item) => ({
      id: item.id,
      type: item.type,
      title: item.title,
      summary: item.summary,
      whyItMatters: item.whyItMatters,
      source: item.source,
      sourceUrl: item.sourceUrl,
      publishedAt: new Date(item.publishedAt),
      sentiment: item.sentiment,
      importance: item.importance,
      category: item.category,
      tags: item.tags,
      relatedSectors: item.relatedSectors,
      relatedTickers: item.relatedTickers,
    })),
  });

  await prisma.marketEvent.createMany({
    data: MARKET_EVENTS.map((event) => ({
      id: event.id,
      title: event.title,
      eventDate: new Date(event.eventDate),
      country: event.country,
      description: event.description,
      impactLevel: event.impactLevel,
      relatedTickers: event.relatedTickers,
    })),
  });

  const stockSet = new Set(STOCKS.map((stock) => stock.ticker));
  const uniqueKeys = new Set<string>();
  const links = NEWS_ITEMS.flatMap((item) =>
    item.relatedTickers
      .filter((ticker) => stockSet.has(ticker))
      .map((ticker) => ({ newsId: item.id, stockTicker: ticker }))
      .filter((link) => {
        const key = `${link.newsId}:${link.stockTicker}`;
        if (uniqueKeys.has(key)) return false;
        uniqueKeys.add(key);
        return true;
      }),
  );

  if (links.length > 0) {
    await prisma.newsStock.createMany({
      data: links,
    });
  }
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    await prisma.$disconnect();
    process.exit(1);
  });
