import { MarketSignalDashboard } from "@/krx/components/market-signal/market-signal-dashboard";
import { normalizeMarketSignalSubtab } from "@/krx/market-signal/lib/subtabs";
import { getMarketSignalTabData } from "@/krx/server/data-service";

export default async function KrxHomePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
} = {}) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const activeSubtab = normalizeMarketSignalSubtab(resolvedSearchParams.subtab);
  const data = await getMarketSignalTabData();

  return (
    <MarketSignalDashboard
      summary={data.summary}
      derivativesSummary={data.derivativesSummary}
      derivativesTrends={data.derivativesTrends}
      derivativesInvestorFlow={data.derivativesInvestorFlow}
      activeSubtab={activeSubtab}
    />
  );
}
