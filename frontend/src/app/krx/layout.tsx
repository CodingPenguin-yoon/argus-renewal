import { Suspense } from "react";

import { AsyncMarketHeader } from "@/krx/components/layout/async-header";
import { StaticShellHeader } from "@/krx/components/layout/static-shell-header";
import { SharedMarketHeaderSkeleton } from "@/krx/components/layout/header-skeleton";

export default function KrxLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="market-shell market-shell-krx">
      <Suspense
        fallback={
          <>
            <StaticShellHeader market="krx" />
            <SharedMarketHeaderSkeleton />
          </>
        }
      >
        <AsyncMarketHeader />
      </Suspense>
      <main className="min-h-[calc(100vh-88px)]">{children}</main>
    </div>
  );
}
