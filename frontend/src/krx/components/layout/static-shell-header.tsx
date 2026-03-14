import Link from "next/link";

import { TopNav } from "@/krx/components/layout/top-nav";
import { marketBasePath } from "@/krx/lib/market";
import { MarketCode } from "@/krx/types/domain";

export function StaticShellHeader({ market }: { market: MarketCode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-amber-200/15 bg-slate-900/82 text-slate-100 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-3 md:py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href={marketBasePath(market)}
              className="text-lg font-black tracking-tight text-slate-50 md:text-xl"
            >
              Argus KRX
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-100/90 md:flex">
              <span className="inline-block h-4 w-12 animate-pulse rounded bg-white/20" />
            </div>
            <Link
              href={`${marketBasePath(market)}/watchlist`}
              className="rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-100/90 transition hover:bg-white/10"
            >
              관심종목
            </Link>
          </div>
        </div>
        <div
          aria-hidden="true"
          className="h-11 rounded-2xl border border-amber-200/25 bg-slate-800/45 px-4"
        >
          <div className="flex h-full items-center">
            <div className="h-3 w-40 animate-pulse rounded-full bg-white/15" />
          </div>
        </div>
        <TopNav market={market} />
      </div>
    </header>
  );
}
