"use client";

import { NewsCard } from "@/components/news/news-card";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { SectionHeader } from "@/components/ui/section-header";
import { StockTimeline } from "@/components/stocks/stock-timeline";
import { STOCK_CATEGORIES } from "@/lib/constants";
import { News, Stock } from "@/types/domain";
import { useMemo, useState } from "react";

export function StockDetail({ stock, stockNews, macroNews }: { stock: Stock; stockNews: News[]; macroNews: News[] }) {
  const [category, setCategory] = useState<string>("all");

  const filtered = useMemo(() => {
    if (category === "all") return stockNews;
    return stockNews.filter((item) => item.category === category);
  }, [stockNews, category]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
      <DisclaimerBanner />

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">종목 상세</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">
          {stock.name} <span className="text-sky-700">({stock.ticker})</span>
        </h1>
        <p className="mt-2 text-sm text-slate-700">
          {stock.market === "KR" ? "한국" : "미국"} 시장 · {stock.sector} 섹터
        </p>
      </section>

      <section className="space-y-4">
        <SectionHeader title="종목 관련 주요 뉴스" description="카테고리 필터로 필요한 이슈를 빠르게 확인하세요." />
        <FilterBar
          ariaLabel="종목 뉴스 필터"
          value={category}
          onChange={setCategory}
          options={[{ value: "all", label: "전체" }, ...STOCK_CATEGORIES.map((item) => ({ value: item, label: item }))]}
        />

        {filtered.length ? (
          <div className="grid gap-4">
            {filtered.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>
        ) : (
          <EmptyState title="해당 카테고리 뉴스가 없습니다" description="다른 필터를 선택해 보세요." />
        )}
      </section>

      <section className="space-y-4">
        <SectionHeader title="최근 이 종목에 영향을 준 주요 이벤트" description="타임라인으로 맥락을 빠르게 파악하세요." />
        {stockNews.length ? (
          <StockTimeline items={stockNews.slice(0, 6)} />
        ) : (
          <EmptyState title="표시할 이벤트가 없습니다" description="잠시 후 다시 확인해 보세요." />
        )}
      </section>

      <section className="space-y-4">
        <SectionHeader title="관련 거시 뉴스" description="개별 종목 이슈와 연결되는 거시 흐름입니다." />
        {macroNews.length ? (
          <div className="grid gap-4">
            {macroNews.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>
        ) : (
          <EmptyState title="연결된 거시 뉴스가 없습니다" description="다른 종목을 선택해 보세요." />
        )}
      </section>
    </div>
  );
}
