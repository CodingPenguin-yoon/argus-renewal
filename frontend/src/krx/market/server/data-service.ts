import { Stock } from "@/krx/types/domain";

import { ApiItemResponse, ApiListResponse, getKrxJson, getKrxJsonOrNull } from "@/krx/server/client";

type ApiStock = {
  ticker: string;
  name: string;
  market: "US" | "KR";
  sector: string;
};

function mapStock(item: ApiStock): Stock {
  return {
    ticker: item.ticker,
    name: item.name,
    market: item.market,
    sector: item.sector as Stock["sector"],
  };
}

export async function getAllStocks() {
  const response = await getKrxJson<ApiListResponse<ApiStock>>("/stocks");
  return response.items.map(mapStock);
}

export async function getStockByTicker(ticker: string) {
  const response = await getKrxJsonOrNull<ApiItemResponse<ApiStock>>(
    `/stocks/${encodeURIComponent(ticker)}`,
  );
  if (!response) return null;
  return mapStock(response.item);
}
