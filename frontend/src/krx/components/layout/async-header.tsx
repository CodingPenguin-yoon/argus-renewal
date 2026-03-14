import { AppShellHeader } from "@/krx/components/layout/app-shell";
import { SharedMarketHeader } from "@/krx/components/layout/shared-market-header";
import { getAppHeaderData } from "@/krx/server/data-service";

export async function AsyncMarketHeader() {
  const headerData = await getAppHeaderData();

  return (
    <>
      <AppShellHeader
        market="krx"
        headerMeta={{ phase: headerData.phase, updatedAt: headerData.updatedAt }}
      />
      <SharedMarketHeader data={headerData} />
    </>
  );
}
