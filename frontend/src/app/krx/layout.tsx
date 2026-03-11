import { AppShellHeader } from "@/krx/components/layout/app-shell";
import { SharedMarketHeader } from "@/krx/components/layout/shared-market-header";
import { getAppHeaderData, getSearchIndex } from "@/krx/server/data-service";

export default async function KrxLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const [searchIndex, headerData] = await Promise.all([getSearchIndex(), getAppHeaderData()]);

  return (
    <div className="market-shell market-shell-krx">
      <AppShellHeader
        market="krx"
        stocks={searchIndex.stocks}
        news={searchIndex.news}
        headerMeta={{ phase: headerData.phase, updatedAt: headerData.updatedAt }}
      />
      <SharedMarketHeader data={headerData} />
      <main className="min-h-[calc(100vh-88px)]">{children}</main>
    </div>
  );
}
