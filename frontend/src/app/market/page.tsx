import { MarketFlowPanel } from "@/market_terminal/dashboard/market-flow-panel";
import type { MarketFlowDashboard } from "@/market_terminal/contracts/market-flow";
import { getMarketFlowDashboard } from "@/market_terminal/server/market-flow";

export default async function MarketDashboardPage() {
  let data: MarketFlowDashboard | undefined;
  let error: string | undefined;

  try {
    data = await getMarketFlowDashboard();
  } catch {
    error = "backend 실행 상태와 BACKEND_BASE_URL을 확인하세요.";
  }

  return <MarketFlowPanel data={data} error={error} />;
}
