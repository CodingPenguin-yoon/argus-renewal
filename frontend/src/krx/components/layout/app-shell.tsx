import Link from "next/link";

import { TopNav } from "@/krx/components/layout/top-nav";
import { SearchBox } from "@/krx/components/search/search-box";
import { formatKoreanDate } from "@/krx/lib/utils";
import { marketBasePath, marketOverviewPath } from "@/krx/lib/market";
import { AppHeader, MarketCode, News, Stock } from "@/krx/types/domain";

function phaseLabel(phase: AppHeader["phase"]) {
  if (phase === "live") return "장중";
  if (phase === "post-close") return "장후";
  return "장전";
}

export function AppShellHeader({
  market,
  stocks,
  news,
  headerMeta,
}: {
  market: MarketCode;
  stocks?: Stock[];
  news?: News[];
  headerMeta: Pick<AppHeader, "phase" | "updatedAt">;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-amber-200/15 bg-slate-900/82 text-slate-100 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-3 md:py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href={marketOverviewPath(market)}
              className="text-lg font-black tracking-tight text-slate-50 md:text-xl"
            >
              Argus KRX
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-100/90 md:flex">
              <span>{phaseLabel(headerMeta.phase)}</span>
              <span aria-hidden>•</span>
              <span>{headerMeta.updatedAt ? `업데이트 ${formatKoreanDate(headerMeta.updatedAt)}` : "업데이트 대기"}</span>
            </div>
            <Link
              href={`${marketBasePath(market)}/watchlist`}
              className="rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-100/90 transition hover:bg-white/10"
            >
              관심종목
            </Link>
          </div>
        </div>
        <SearchBox market={market} stocks={stocks} news={news} />
        <TopNav market={market} />
      </div>
    </header>
  );
}
