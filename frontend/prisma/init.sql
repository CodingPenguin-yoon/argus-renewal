PRAGMA foreign_keys=OFF;

DROP TABLE IF EXISTS "NewsStock";
DROP TABLE IF EXISTS "MarketEvent";
DROP TABLE IF EXISTS "News";
DROP TABLE IF EXISTS "Stock";

CREATE TABLE "Stock" (
  "ticker" TEXT NOT NULL PRIMARY KEY,
  "name" TEXT NOT NULL,
  "market" TEXT NOT NULL,
  "sector" TEXT NOT NULL,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "News" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "type" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "summary" TEXT NOT NULL,
  "whyItMatters" TEXT NOT NULL,
  "source" TEXT NOT NULL,
  "sourceUrl" TEXT NOT NULL,
  "publishedAt" DATETIME NOT NULL,
  "sentiment" TEXT NOT NULL,
  "importance" TEXT NOT NULL,
  "category" TEXT NOT NULL,
  "tags" JSON NOT NULL,
  "relatedSectors" JSON NOT NULL,
  "relatedTickers" JSON NOT NULL,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "NewsStock" (
  "newsId" TEXT NOT NULL,
  "stockTicker" TEXT NOT NULL,
  PRIMARY KEY ("newsId", "stockTicker"),
  FOREIGN KEY ("newsId") REFERENCES "News"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY ("stockTicker") REFERENCES "Stock"("ticker") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE "MarketEvent" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "title" TEXT NOT NULL,
  "eventDate" DATETIME NOT NULL,
  "country" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "impactLevel" TEXT NOT NULL,
  "relatedTickers" JSON NOT NULL,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX "News_publishedAt_idx" ON "News"("publishedAt");
CREATE INDEX "News_type_idx" ON "News"("type");
CREATE INDEX "MarketEvent_eventDate_idx" ON "MarketEvent"("eventDate");

PRAGMA foreign_keys=ON;
