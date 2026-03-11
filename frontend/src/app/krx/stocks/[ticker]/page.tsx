import { notFound } from "next/navigation";

import { StockDetail } from "@/krx/components/stocks/stock-detail";
import { getStockPageData } from "@/krx/server/data-service";

export default async function KrxStockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const data = await getStockPageData(decodeURIComponent(ticker));

  if (!data.stock) {
    notFound();
  }

  return (
    <StockDetail
      market="krx"
      stock={data.stock}
      stockNews={data.stockNews}
      macroNews={data.relatedMacro}
    />
  );
}
