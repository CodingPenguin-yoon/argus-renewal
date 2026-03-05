import { notFound } from "next/navigation";

import { StockDetail } from "@/components/stocks/stock-detail";
import { getStockPageData } from "@/lib/server/data-service";

export default async function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const data = await getStockPageData(decodeURIComponent(ticker));

  if (!data.stock) {
    notFound();
  }

  return <StockDetail stock={data.stock} stockNews={data.stockNews} macroNews={data.relatedMacro} />;
}
