"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { marketHref } from "@/krx/lib/market";
import { MarketCode, News, Stock } from "@/krx/types/domain";

type SearchBoxProps = {
  market: MarketCode;
  stocks?: Stock[];
  news?: News[];
};

type SearchIndexPayload = {
  stocks: Stock[];
  news: News[];
};

const EMPTY_STOCKS: Stock[] = [];
const EMPTY_NEWS: News[] = [];

function normalizeSearchIndex(payload: SearchIndexPayload | null | undefined): SearchIndexPayload {
  return {
    stocks: Array.isArray(payload?.stocks) ? payload.stocks : [],
    news: Array.isArray(payload?.news) ? payload.news : [],
  };
}

export function SearchBox({ market, stocks, news }: SearchBoxProps) {
  const propStocks = stocks ?? EMPTY_STOCKS;
  const propNews = news ?? EMPTY_NEWS;
  const hasInitialIndex = propStocks.length > 0 || propNews.length > 0;
  const [query, setQuery] = useState("");
  const [searchIndex, setSearchIndex] = useState<SearchIndexPayload>(() =>
    normalizeSearchIndex({ stocks: propStocks, news: propNews }),
  );
  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const didBootstrapRef = useRef(hasInitialIndex);
  const bootstrapPromiseRef = useRef<Promise<void> | null>(null);
  const inputId = `${market}-global-search`;

  useEffect(() => {
    setSearchIndex(normalizeSearchIndex({ stocks: propStocks, news: propNews }));
    if (hasInitialIndex) {
      didBootstrapRef.current = true;
      setIsBootstrapping(false);
    }
  }, [hasInitialIndex, propNews, propStocks]);

  async function ensureSearchIndexLoaded() {
    if (didBootstrapRef.current || bootstrapPromiseRef.current) {
      await bootstrapPromiseRef.current;
      return;
    }

    didBootstrapRef.current = true;
    setIsBootstrapping(true);

    const bootstrapPromise = (async () => {
      try {
        const response = await fetch("/api/krx/search-index");
        if (!response.ok) {
          throw new Error(`Search index request failed (${response.status})`);
        }

        const payload = normalizeSearchIndex((await response.json()) as SearchIndexPayload);
        startTransition(() => {
          setSearchIndex(payload);
          setIsBootstrapping(false);
        });
      } catch (error) {
        didBootstrapRef.current = false;
        setIsBootstrapping(false);
        console.error(
          JSON.stringify(
            {
              scope: "krx_search_index_bootstrap",
              status: "failed",
              error: error instanceof Error ? error.message : String(error),
            },
            null,
            0,
          ),
        );
      } finally {
        bootstrapPromiseRef.current = null;
      }
    })();

    bootstrapPromiseRef.current = bootstrapPromise;
    await bootstrapPromise;
  }

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { stocks: [], news: [] };

    return {
      stocks: searchIndex.stocks
        .filter(
          (stock) =>
            stock.ticker.toLowerCase().includes(q) || stock.name.toLowerCase().includes(q),
        )
        .slice(0, 5),
      news: searchIndex.news
        .filter(
          (item) =>
            item.title.toLowerCase().includes(q) ||
            item.summary.toLowerCase().includes(q) ||
            item.relatedTickers.some((ticker) => ticker.toLowerCase().includes(q)),
        )
        .slice(0, 5),
    };
  }, [query, searchIndex.news, searchIndex.stocks]);

  return (
    <div className="relative w-full">
      <label htmlFor={inputId} className="sr-only">
        종목 또는 뉴스 검색
      </label>
      <input
        id={inputId}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => {
          if (!hasInitialIndex) {
            void ensureSearchIndexLoaded();
          }
        }}
        placeholder="티커/종목명/키워드 검색"
        className="h-11 w-full rounded-2xl border border-amber-200/25 bg-slate-800/45 px-4 text-sm text-slate-100 shadow-sm backdrop-blur placeholder:text-amber-50/55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200"
      />

      {query ? (
        <div className="absolute z-20 mt-2 w-full rounded-2xl border border-slate-600/70 bg-slate-900/88 p-2 text-slate-100 shadow-xl backdrop-blur">
          <div className="max-h-72 overflow-y-auto">
            {isBootstrapping ? (
              <p className="px-2 py-2 text-sm text-slate-300/80">검색 인덱스를 불러오는 중입니다.</p>
            ) : null}
            <p className="px-2 py-1 text-xs font-semibold tracking-wide text-amber-200">종목</p>
            {results.stocks.length ? (
              <ul>
                {results.stocks.map((stock) => (
                  <li key={stock.ticker}>
                    <Link
                      href={marketHref(market, `/stocks/${encodeURIComponent(stock.ticker)}`)}
                      className="block rounded-xl px-2 py-2 text-sm transition hover:bg-amber-100/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200"
                      onClick={() => setQuery("")}
                    >
                      {stock.name} ({stock.ticker})
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-2 py-2 text-sm text-slate-300/70">일치하는 종목이 없습니다.</p>
            )}

            <p className="mt-2 px-2 py-1 text-xs font-semibold tracking-wide text-amber-200">뉴스</p>
            {results.news.length ? (
              <ul>
                {results.news.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={marketHref(market, `/news/${item.id}`)}
                      className="block rounded-xl px-2 py-2 text-sm transition hover:bg-amber-100/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200"
                      onClick={() => setQuery("")}
                    >
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-2 py-2 text-sm text-slate-300/70">일치하는 뉴스가 없습니다.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
