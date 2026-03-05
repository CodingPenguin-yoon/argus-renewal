"use client";

import { useMemo, useState } from "react";

import { EventCard } from "@/components/news/event-card";
import { NewsCard } from "@/components/news/news-card";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { SectionHeader } from "@/components/ui/section-header";
import { MACRO_CATEGORIES } from "@/lib/constants";
import { getWatchlist } from "@/lib/watchlist-storage";
import { MarketEvent, News } from "@/types/domain";

export function HomeDashboard({ macroNews, allNews, events }: { macroNews: News[]; allNews: News[]; events: MarketEvent[] }) {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [watchlist] = useState<string[]>(() => getWatchlist());

  const macroFiltered = useMemo(() => {
    if (selectedCategory === "all") return macroNews;
    return macroNews.filter((item) => item.category === selectedCategory);
  }, [macroNews, selectedCategory]);

  const watchlistNews = useMemo(() => {
    if (!watchlist.length) return [];
    return allNews.filter((news) => news.relatedTickers.some((ticker) => watchlist.includes(ticker))).slice(0, 6);
  }, [allNews, watchlist]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
      <DisclaimerBanner />

      <section aria-labelledby="macro-news-title" className="space-y-4">
        <SectionHeader
          title="오늘의 핵심 거시 뉴스"
          description="시장 방향성에 영향을 주는 거시 이슈를 먼저 확인하세요."
        />

        <FilterBar
          ariaLabel="거시 뉴스 카테고리"
          value={selectedCategory}
          onChange={setSelectedCategory}
          options={[{ label: "전체", value: "all" }, ...MACRO_CATEGORIES.map((item) => ({ label: item, value: item }))]}
        />

        {macroFiltered.length ? (
          <div className="grid gap-4">
            {macroFiltered.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>
        ) : (
          <EmptyState title="선택한 카테고리의 뉴스가 없습니다" description="다른 필터를 선택해 보세요." />
        )}
      </section>

      <section aria-labelledby="calendar-title" className="space-y-4">
        <SectionHeader title="오늘의 경제 일정" description="앞으로 2주 내 주요 이벤트입니다." />
        <div className="grid gap-3 md:grid-cols-2">
          {events.slice(0, 8).map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      </section>

      <section aria-labelledby="headline-news-title" className="space-y-4">
        <SectionHeader title="주요 뉴스" description="거시/종목 뉴스를 함께 빠르게 훑어보세요." />
        <div className="grid gap-4">
          {allNews.slice(0, 10).map((item) => (
            <NewsCard key={item.id} news={item} />
          ))}
        </div>
      </section>

      <section aria-labelledby="watchlist-news-title" className="space-y-4">
        <SectionHeader title="관심종목 뉴스 요약" description="관심종목을 추가하면 관련 뉴스가 자동으로 모입니다." />
        {watchlist.length === 0 ? (
          <EmptyState title="관심종목이 비어 있습니다" description="상단 메뉴의 관심종목 페이지에서 티커를 추가해 보세요." />
        ) : watchlistNews.length ? (
          <div className="grid gap-4">
            {watchlistNews.map((item) => (
              <NewsCard key={item.id} news={item} />
            ))}
          </div>
        ) : (
          <EmptyState title="관심종목 관련 뉴스가 없습니다" description="잠시 후 다시 확인해 보세요." />
        )}
      </section>
    </div>
  );
}
