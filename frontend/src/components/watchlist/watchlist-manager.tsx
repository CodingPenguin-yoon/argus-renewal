"use client";

import { useMemo, useState } from "react";

import { NewsCard } from "@/components/news/news-card";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { SectionHeader } from "@/components/ui/section-header";
import { getWatchlist, saveWatchlist, toggleWatchlist } from "@/lib/watchlist-storage";
import { News, Sentiment, Stock } from "@/types/domain";

type WatchlistManagerProps = {
  stocks: Stock[];
  news: News[];
};

export function WatchlistManager({ stocks, news }: WatchlistManagerProps) {
  const [watchlist, setWatchlist] = useState<string[]>(() => getWatchlist());
  const [query, setQuery] = useState("");
  const [sentiment, setSentiment] = useState<Sentiment | "all">("all");
  const [importance, setImportance] = useState<News["importance"] | "all">("all");

  const filteredStocks = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return stocks;

    return stocks.filter(
      (stock) =>
        stock.ticker.toLowerCase().includes(q) || stock.name.toLowerCase().includes(q),
    );
  }, [stocks, query]);

  const watchlistNews = useMemo(() => {
    return news
      .filter((item) => item.relatedTickers.some((ticker) => watchlist.includes(ticker)))
      .filter((item) => (sentiment === "all" ? true : item.sentiment === sentiment))
      .filter((item) => (importance === "all" ? true : item.importance === importance));
  }, [news, watchlist, sentiment, importance]);

  const handleManualAdd = (ticker: string) => {
    const next = [...new Set([ticker.toUpperCase(), ...watchlist])];
    setWatchlist(next);
    saveWatchlist(next);
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
      <DisclaimerBanner />

      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
        <SectionHeader title="관심종목 관리" description="로그인 없이 브라우저에 저장됩니다." />

        <label htmlFor="watchlist-search" className="sr-only">
          관심종목 검색
        </label>
        <input
          id="watchlist-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-10 w-full rounded-xl border border-slate-300 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          placeholder="티커 또는 종목명 검색"
        />

        <div className="flex flex-wrap gap-2" role="list" aria-label="추가 가능한 종목">
          {filteredStocks.slice(0, 8).map((stock) => {
            const selected = watchlist.includes(stock.ticker);
            return (
              <button
                key={stock.ticker}
                type="button"
                onClick={() => {
                  if (selected) {
                    setWatchlist(toggleWatchlist(stock.ticker));
                  } else {
                    handleManualAdd(stock.ticker);
                  }
                }}
                className={`rounded-full border px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                  selected
                    ? "border-sky-600 bg-sky-600 text-white"
                    : "border-slate-300 bg-white text-slate-700"
                }`}
              >
                {stock.name} ({stock.ticker})
              </button>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeader title="관심종목 뉴스" description="감정/중요도 필터로 빠르게 우선순위를 정하세요." />

        <div className="space-y-2">
          <FilterBar
            ariaLabel="감정 필터"
            value={sentiment}
            onChange={(value) => setSentiment(value as Sentiment | "all")}
            options={[
              { value: "all", label: "감정 전체" },
              { value: "positive", label: "긍정" },
              { value: "neutral", label: "중립" },
              { value: "negative", label: "부정" },
            ]}
          />
          <FilterBar
            ariaLabel="중요도 필터"
            value={importance}
            onChange={(value) => setImportance(value as News["importance"] | "all")}
            options={[
              { value: "all", label: "중요도 전체" },
              { value: "high", label: "높음" },
              { value: "medium", label: "중간" },
              { value: "low", label: "낮음" },
            ]}
          />
        </div>

        {watchlistNews.length ? (
          <div className="grid gap-4">
            {watchlistNews.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="조건에 맞는 관심종목 뉴스가 없습니다"
            description="필터를 조정하거나 관심종목을 추가해 보세요."
          />
        )}
      </section>
    </div>
  );
}
