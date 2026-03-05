"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { News, Stock } from "@/types/domain";

type SearchBoxProps = {
  stocks: Stock[];
  news: News[];
};

export function SearchBox({ stocks, news }: SearchBoxProps) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { stocks: [], news: [] };

    return {
      stocks: stocks
        .filter(
          (stock) =>
            stock.ticker.toLowerCase().includes(q) || stock.name.toLowerCase().includes(q),
        )
        .slice(0, 5),
      news: news
        .filter(
          (item) =>
            item.title.toLowerCase().includes(q) ||
            item.summary.toLowerCase().includes(q) ||
            item.relatedTickers.some((ticker) => ticker.toLowerCase().includes(q)),
        )
        .slice(0, 5),
    };
  }, [query, stocks, news]);

  return (
    <div className="relative w-full">
      <label htmlFor="global-search" className="sr-only">
        종목 또는 뉴스 검색
      </label>
      <input
        id="global-search"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="티커/종목명/키워드 검색"
        className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      />

      {query ? (
        <div className="absolute z-20 mt-2 w-full rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
          <div className="max-h-72 overflow-y-auto">
            <p className="px-2 py-1 text-xs font-semibold text-slate-500">종목</p>
            {results.stocks.length ? (
              <ul>
                {results.stocks.map((stock) => (
                  <li key={stock.ticker}>
                    <Link
                      href={`/stocks/${encodeURIComponent(stock.ticker)}`}
                      className="block rounded-md px-2 py-2 text-sm hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                      onClick={() => setQuery("")}
                    >
                      {stock.name} ({stock.ticker})
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-2 py-2 text-sm text-slate-500">일치하는 종목이 없습니다.</p>
            )}

            <p className="mt-2 px-2 py-1 text-xs font-semibold text-slate-500">뉴스</p>
            {results.news.length ? (
              <ul>
                {results.news.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={`/news/${item.id}`}
                      className="block rounded-md px-2 py-2 text-sm hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                      onClick={() => setQuery("")}
                    >
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-2 py-2 text-sm text-slate-500">일치하는 뉴스가 없습니다.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
