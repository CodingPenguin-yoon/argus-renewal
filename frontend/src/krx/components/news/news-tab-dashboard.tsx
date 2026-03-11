import Link from "next/link";

import { MarketNewsCardView } from "@/krx/components/news/market-news-card";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { SectionHeader } from "@/krx/components/ui/section-header";
import { newsTabHref, NEWS_TAB_OPTIONS, NewsTabKey } from "@/krx/news/lib/tabs";
import { formatKoreanDate } from "@/krx/lib/utils";
import { MarketNewsCard, MarketNewsCoverage, MarketNewsHeaderContext } from "@/krx/types/domain";

function formatMaybeDate(value: string | null) {
  if (!value) return "업데이트 정보 없음";
  try {
    return formatKoreanDate(value);
  } catch {
    return value;
  }
}

function CardSection({
  title,
  description,
  cards,
  emptyTitle,
  emptyDescription,
  actionHref,
  actionLabel,
  limit,
}: {
  title: string;
  description: string;
  cards: MarketNewsCard[];
  emptyTitle: string;
  emptyDescription: string;
  actionHref?: string;
  actionLabel?: string;
  limit?: number;
}) {
  const visibleCards = typeof limit === "number" ? cards.slice(0, limit) : cards;

  return (
    <section className="rounded-[32px] border border-slate-200/90 bg-white/70 p-5 shadow-[0_18px_44px_rgba(15,23,42,0.05)] backdrop-blur">
      <SectionHeader
        title={title}
        description={description}
        action={
          actionHref && actionLabel ? (
            <Link
              href={actionHref}
              className="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
            >
              {actionLabel}
            </Link>
          ) : undefined
        }
      />
      {visibleCards.length ? (
        <div className="grid gap-4">
          {visibleCards.map((card) => (
            <MarketNewsCardView key={card.id} card={card} />
          ))}
        </div>
      ) : (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      )}
    </section>
  );
}

export function NewsTabDashboard({
  krCards,
  globalCards,
  disclosureCards,
  headerContext,
  coverage,
  activeTab,
}: {
  krCards: MarketNewsCard[];
  globalCards: MarketNewsCard[];
  disclosureCards: MarketNewsCard[];
  headerContext: MarketNewsHeaderContext;
  coverage: MarketNewsCoverage;
  activeTab: NewsTabKey;
}) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-6 md:py-8">
      <section className="rounded-[36px] border border-slate-200 bg-[linear-gradient(140deg,rgba(255,255,255,0.98),rgba(241,245,249,0.94))] p-6 shadow-[0_24px_56px_rgba(15,23,42,0.08)]">
        <div className="max-w-4xl">
          <p className="text-[11px] font-black uppercase tracking-[0.28em] text-slate-500">Event-First Market News</p>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950">뉴스</h1>
          <p className="mt-3 text-base leading-7 text-slate-700">{headerContext.summaryLine}</p>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5">한국 증시 {krCards.length}건</span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5">글로벌 증시 {globalCards.length}건</span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5">공시 {disclosureCards.length}건</span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5">{coverage.summary}</span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5">{formatMaybeDate(coverage.updatedAt)}</span>
        </div>
        <nav className="mt-4 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="뉴스 세부 탭" data-testid="news-subtabs">
          {NEWS_TAB_OPTIONS.map((option) => {
            const active = option.key === activeTab;
            return (
              <Link
                key={option.key}
                href={newsTabHref(option.key)}
                role="tab"
                aria-selected={active}
                className={`inline-flex min-w-[68px] items-center justify-center rounded-full border px-3 py-1.5 text-sm font-semibold whitespace-nowrap transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
                  active
                    ? "border-amber-500 bg-amber-300 text-slate-950 shadow-sm"
                    : "border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50"
                }`}
              >
                {option.label}
              </Link>
            );
          })}
        </nav>
      </section>

      {activeTab === "summary" ? (
        <section className="grid gap-5 xl:grid-cols-3">
          <CardSection
            title="오늘의 한국 증시 이벤트"
            description="지수·수급과 직접 연결되는 국내 이벤트를 먼저 요약했습니다."
            cards={krCards}
            emptyTitle="한국 증시 이벤트가 아직 없습니다"
            emptyDescription="최신 데이터가 준비되면 이 영역에 표시됩니다."
            actionHref={newsTabHref("kr")}
            actionLabel="한국 증시 전체"
            limit={2}
          />
          <CardSection
            title="한국 관련 글로벌 이벤트"
            description="원화, 외국인 수급, 위험선호에 전이되는 해외 변수만 모았습니다."
            cards={globalCards}
            emptyTitle="글로벌 이벤트가 아직 없습니다"
            emptyDescription="최신 데이터가 준비되면 이 영역에 표시됩니다."
            actionHref={newsTabHref("global")}
            actionLabel="글로벌 증시 전체"
            limit={2}
          />
          <CardSection
            title="주요 공시"
            description="시장 영향 가능성이 높은 공시 중심 이벤트를 선별했습니다."
            cards={disclosureCards}
            emptyTitle="표시 가능한 공시가 아직 없습니다"
            emptyDescription="공시 데이터가 준비되면 이 영역에 표시됩니다."
            actionHref={newsTabHref("disclosures")}
            actionLabel="공시 전체"
            limit={2}
          />
        </section>
      ) : null}

      {activeTab === "kr" ? (
        <CardSection
          title="한국 증시"
          description="지수, 수급, 업종 파급으로 바로 연결되는 이슈만 남겼습니다."
          cards={krCards}
          emptyTitle="한국 증시 카드가 없습니다"
          emptyDescription="아직 동기화된 데이터가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
        />
      ) : null}

      {activeTab === "global" ? (
        <CardSection
          title="글로벌 증시"
          description="한국 시장에 전이될 글로벌 변수만 별도 클러스터로 정렬했습니다."
          cards={globalCards}
          emptyTitle="글로벌 증시 카드가 없습니다"
          emptyDescription="아직 동기화된 데이터가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
        />
      ) : null}

      {activeTab === "disclosures" ? (
        <CardSection
          title="공시"
          description="공시 근거(DART)가 확인된 이벤트를 우선순위 순으로 제공합니다."
          cards={disclosureCards}
          emptyTitle="표시 가능한 공시가 없습니다"
          emptyDescription="현재 표시 가능한 공시가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
        />
      ) : null}
    </div>
  );
}
