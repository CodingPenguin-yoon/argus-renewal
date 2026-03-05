import { SearchBox } from "@/components/search/search-box";
import { TopNav } from "@/components/layout/top-nav";
import { News, Stock } from "@/types/domain";
import Link from "next/link";

export function AppShellHeader({ stocks, news }: { stocks: Stock[]; news: News[] }) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link href="/" className="text-lg font-extrabold text-slate-900">
            Argus 금융 뉴스
          </Link>
          <span className="rounded-full bg-sky-100 px-2 py-1 text-xs font-semibold text-sky-700">MVP</span>
        </div>
        <SearchBox stocks={stocks} news={news} />
        <TopNav />
      </div>
    </header>
  );
}
