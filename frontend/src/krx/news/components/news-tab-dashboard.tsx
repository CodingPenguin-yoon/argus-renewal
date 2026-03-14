import Link from "next/link";
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { SectionHeader } from "@/krx/components/ui/section-header";
import { newsTabHref, NEWS_TAB_OPTIONS, NewsTabKey } from "@/krx/news/lib/tabs";
import { MarketNewsCardView } from "@/krx/news/components/market-news-card";
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

function formatCoverageRatio(value: number) {
  return `${Math.round(value * 100)}%`;
}

function SourceStatusChip({ status }: { status: MarketNewsCoverage["items"][number]["status"] }) {
  const variant = status === "available" ? "success" : status === "partial" ? "warning" : "muted";
  return (
    <Badge variant={variant} className="h-6 px-2.5 text-[11px] font-semibold uppercase tracking-[0.12em]">
      {status}
    </Badge>
  );
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
    <Card className="border-border/50 bg-card/80 shadow-lg backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <CardTitle className="text-xl font-bold tracking-tight">{title}</CardTitle>
            <CardDescription className="text-sm leading-relaxed">{description}</CardDescription>
          </div>
          {actionHref && actionLabel && (
            <Link
              href={actionHref}
              className="inline-flex shrink-0 items-center rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
            >
              {actionLabel}
            </Link>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {visibleCards.length ? (
          <div className="grid gap-4">
            {visibleCards.map((card) => (
              <MarketNewsCardView key={card.id} card={card} />
            ))}
          </div>
        ) : (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        )}
      </CardContent>
    </Card>
  );
}

function SummaryLeadStory({
  card,
  tone,
}: Readonly<{
  card: MarketNewsCard;
  tone: "primary" | "secondary";
}>) {
  return (
    <Card className={tone === "primary" ? "border-border/50 bg-gradient-to-br from-card to-accent/10 shadow-lg" : "border-border/40 bg-muted/50"}>
      <CardContent className={tone === "primary" ? "p-5" : "p-4"}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="h-6 px-2.5 text-[10px] font-bold uppercase tracking-[0.15em]">
            {card.primaryRegion === "KR" ? "KR" : "GLOBAL"}
          </Badge>
          <Badge variant="secondary" className="h-6 px-2.5 text-[10px] font-semibold">
            {card.marketScope === "kr_market"
              ? "한국 증시"
              : card.marketScope === "global_market"
                ? "글로벌 변수"
                : card.marketScope === "company"
                  ? "공시 중심"
                  : "시장 표면"}
          </Badge>
          <Badge variant="muted" className="h-6 px-2.5 text-[10px] font-medium">
            {formatMaybeDate(card.updatedAt ?? card.publishedAt)}
          </Badge>
        </div>
        <h3 className="mt-4 text-lg font-bold leading-snug tracking-tight text-foreground">{card.title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{card.oneLineSummary}</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-xl bg-muted/50 p-4 ring-1 ring-border/50">
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Why Important</p>
            <p className="mt-2 text-sm leading-relaxed text-foreground/90">{card.whyItMatters}</p>
          </div>
          <div className="rounded-xl bg-muted/50 p-4 ring-1 ring-border/50">
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Market Impact</p>
            <p className="mt-2 text-sm leading-relaxed text-foreground/90">{card.marketImpact}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge variant="outline" className="h-6 px-2.5 font-medium">랭킹 {card.rankingScore.toFixed(2)}</Badge>
          <Badge variant="outline" className="h-6 px-2.5 font-medium">근거 {card.evidenceCount}건</Badge>
          <Badge variant="default" className="h-6 px-2.5 font-semibold">{card.importanceLabel.toUpperCase()}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryMiniStoryList({
  cards,
}: Readonly<{
  cards: MarketNewsCard[];
}>) {
  if (!cards.length) {
    return null;
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {cards.map((card) => (
        <Card key={card.id} className="border-border/40 bg-card/90 transition-all hover:shadow-md">
          <CardContent className="p-4">
            <div className="flex items-center justify-between gap-3">
              <Badge variant="outline" className="h-5 px-2 text-[10px] font-bold uppercase tracking-[0.15em]">
                {card.primaryRegion}
              </Badge>
              <span className="text-[10px] font-medium text-muted-foreground">{formatMaybeDate(card.updatedAt ?? card.publishedAt)}</span>
            </div>
            <h4 className="mt-3 text-sm font-semibold leading-snug text-foreground">{card.title}</h4>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{card.oneLineSummary}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function SummaryDigestGroup({
  title,
  caption,
  cards,
  actionHref,
  actionLabel,
}: Readonly<{
  title: string;
  caption: string;
  cards: MarketNewsCard[];
  actionHref: string;
  actionLabel: string;
}>) {
  const leadCard = cards[0];
  const moreCards = cards.slice(1, 3);

  return (
    <div className="rounded-2xl border border-border/50 bg-card/60 p-4 ring-1 ring-border/30 backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Badge variant="outline" className="mb-2 h-5 px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            {caption}
          </Badge>
          <h3 className="text-lg font-bold tracking-tight text-foreground">{title}</h3>
        </div>
        <Link
          href={actionHref}
          className="inline-flex shrink-0 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
        >
          {actionLabel}
        </Link>
      </div>

      {leadCard ? (
        <div className="mt-4 space-y-3">
          <article className="rounded-xl bg-muted/60 p-4 ring-1 ring-border/40">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="muted" className="h-5 px-2 text-[10px] font-medium">
                {formatMaybeDate(leadCard.updatedAt ?? leadCard.publishedAt)}
              </Badge>
              <Badge variant="outline" className="h-5 px-2 text-[10px] font-medium">
                근거 {leadCard.evidenceCount}건
              </Badge>
            </div>
            <h4 className="mt-2 text-base font-semibold leading-snug text-foreground">{leadCard.title}</h4>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{leadCard.oneLineSummary}</p>
          </article>

          {moreCards.length ? (
            <div className="grid gap-2">
              {moreCards.map((card) => (
                <article key={card.id} className="rounded-lg border border-border/50 bg-card px-4 py-3 transition-colors hover:bg-muted/30">
                  <p className="text-sm font-medium leading-relaxed text-foreground/90">{card.title}</p>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="mt-4">
          <EmptyState title={`${title} 카드가 없습니다`} description="최신 데이터가 준비되면 이 영역에 표시됩니다." />
        </div>
      )}
    </div>
  );
}

function SurfaceSnapshotContent({ coverage }: Readonly<{ coverage: MarketNewsCoverage }>) {
  return (
    <div className="rounded-xl border border-border/50 bg-gradient-to-br from-card to-muted/30 p-4 ring-1 ring-border/30">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{coverage.summary}</p>
          <p className="mt-1 text-xs text-muted-foreground">{formatMaybeDate(coverage.updatedAt)}</p>
        </div>
        <div className="rounded-xl bg-foreground px-3 py-2 text-right">
          <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted">Coverage</p>
          <p className="mt-0.5 text-xl font-bold text-background">{formatCoverageRatio(coverage.coverageRatio)}</p>
        </div>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-gradient-to-r from-foreground to-primary transition-all"
          style={{ width: `${Math.max(8, Math.round(coverage.coverageRatio * 100))}%` }}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="secondary" className="h-6 px-2.5 font-medium">
          사용 가능 소스 {coverage.availableSources}/{coverage.expectedSources}
        </Badge>
        <Badge variant="outline" className="h-6 px-2.5 font-medium text-muted-foreground">백엔드 갱신 추적 중</Badge>
      </div>
    </div>
  );
}

function ColumnPulseContent({ headerContext }: Readonly<{ headerContext: MarketNewsHeaderContext }>) {
  return (
    <div className="space-y-3">
      {headerContext.columns.map((column) => (
        <div key={column.key} className="rounded-xl border border-border/50 bg-muted/40 p-4 ring-1 ring-border/30 transition-colors hover:bg-muted/60">
          <div className="flex items-center justify-between gap-3">
            <div>
              <Badge variant="outline" className="mb-2 h-5 px-2 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">
                {column.label}
              </Badge>
              <p className="text-base font-semibold tracking-tight text-foreground">{column.leadTitle ?? "선두 카드 없음"}</p>
            </div>
            <Badge variant="secondary" className="h-6 px-2.5 font-semibold">{column.count}건</Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{column.leadScope ? `대표 범위: ${column.leadScope}` : "대표 범위 정보 없음"}</p>
        </div>
      ))}
    </div>
  );
}

function SourceCoverageContent({ coverage }: Readonly<{ coverage: MarketNewsCoverage }>) {
  return coverage.items.length ? (
    coverage.items.map((item) => (
      <div key={item.provider} className="flex items-start justify-between gap-3 rounded-xl border border-border/50 bg-card p-4 ring-1 ring-border/30 transition-colors hover:bg-muted/20">
        <div>
          <p className="text-sm font-semibold text-foreground">{item.provider}</p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            문서 {item.documentCount}건 · 이벤트 {item.eventCount}건 · 근거 {item.evidenceCount}건
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">{item.lastSyncedAt ? `최근 동기화 ${formatMaybeDate(item.lastSyncedAt)}` : "최근 동기화 정보 없음"}</p>
        </div>
        <SourceStatusChip status={item.status} />
      </div>
    ))
  ) : (
    <EmptyState title="반영 상태가 아직 없습니다" description="소스 커버리지가 준비되면 이 영역에 표시됩니다." />
  );
}

function RailSection({
  title,
  eyebrow,
  children,
}: Readonly<{
  title: string;
  eyebrow: string;
  children: ReactNode;
}>) {
  return (
    <Card className="border-border/50 bg-card/90 shadow-lg backdrop-blur-sm">
      <CardHeader className="pb-3">
        <Badge variant="outline" className="mb-2 h-5 w-fit px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          {eyebrow}
        </Badge>
        <CardTitle className="text-lg font-bold tracking-tight">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">{children}</CardContent>
    </Card>
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
  const activeSummary =
    activeTab === "summary"
      ? "실시간으로 다시 정렬된 메인 카드"
      : activeTab === "kr"
        ? "국내 시장 직접 영향 카드"
        : activeTab === "global"
          ? "한국 시장에 전이되는 글로벌 변수"
          : "공시로 확인된 이벤트 중심 카드";

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:py-8">
      <Card className="overflow-hidden border-0 bg-gradient-to-br from-card via-card to-accent/20 shadow-xl ring-1 ring-border/50">
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between">
            <div className="space-y-3">
              <Badge variant="outline" className="h-5 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                Event-First Market News
              </Badge>
              <CardTitle className="text-3xl font-black tracking-tight">뉴스</CardTitle>
              <CardDescription className="max-w-2xl text-base leading-relaxed text-foreground/80">
                {headerContext.summaryLine}
              </CardDescription>
              <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{activeSummary}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-0">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="h-7 gap-1.5 px-3 font-medium">
              <span className="size-1.5 rounded-full bg-primary" />
              한국 증시 {krCards.length}건
            </Badge>
            <Badge variant="secondary" className="h-7 gap-1.5 px-3 font-medium">
              <span className="size-1.5 rounded-full bg-chart-2" />
              글로벌 증시 {globalCards.length}건
            </Badge>
            <Badge variant="secondary" className="h-7 gap-1.5 px-3 font-medium">
              <span className="size-1.5 rounded-full bg-chart-4" />
              공시 {disclosureCards.length}건
            </Badge>
            <Badge variant="outline" className="h-7 px-3 font-medium">{coverage.summary}</Badge>
            <Badge variant="outline" className="h-7 px-3 font-medium text-muted-foreground">{formatMaybeDate(coverage.updatedAt)}</Badge>
          </div>
          <nav className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="뉴스 세부 탭" data-testid="news-subtabs">
            {NEWS_TAB_OPTIONS.map((option) => {
              const active = option.key === activeTab;
              return (
                <Link
                  key={option.key}
                  href={newsTabHref(option.key)}
                  role="tab"
                  aria-selected={active}
                  className={`inline-flex min-w-[72px] items-center justify-center rounded-lg border px-4 py-2 text-sm font-semibold whitespace-nowrap transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    active
                      ? "border-primary bg-primary text-primary-foreground shadow-md"
                      : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
                  }`}
                >
                  {option.label}
                </Link>
              );
            })}
          </nav>
        </CardContent>
      </Card>

      {activeTab === "summary" ? (
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
          <Card className="border-border/50 bg-gradient-to-br from-card to-muted/20 shadow-lg backdrop-blur-sm">
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1.5">
                  <CardTitle className="text-xl font-bold tracking-tight">오늘의 한국 증시 이벤트</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    국내 시장에 직접 이어지는 카드만 한 번에 읽히도록 메인보드로 정리했습니다.
                  </CardDescription>
                </div>
                <Link
                  href={newsTabHref("kr")}
                  className="inline-flex shrink-0 items-center rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
                >
                  한국 증시 전체
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {krCards.length ? (
                <div className="space-y-4">
                  <SummaryLeadStory card={krCards[0]} tone="primary" />
                  <SummaryMiniStoryList cards={krCards.slice(1, 3)} />
                </div>
              ) : (
                <EmptyState
                  title="한국 증시 이벤트가 아직 없습니다"
                  description="최신 데이터가 준비되면 이 영역에 표시됩니다."
                />
              )}
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/90 shadow-lg backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-xl font-bold tracking-tight">글로벌·공시 브리프</CardTitle>
              <CardDescription className="text-sm leading-relaxed">
                글로벌 변수, 공시, 시장 표면 상태를 한 박스에서 비교하도록 합쳤습니다.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <SummaryDigestGroup
                title="글로벌 변수"
                caption="Global Pulse"
                cards={globalCards}
                actionHref={newsTabHref("global")}
                actionLabel="글로벌 증시 전체"
              />
              <SummaryDigestGroup
                title="주요 공시"
                caption="Disclosure Focus"
                cards={disclosureCards}
                actionHref={newsTabHref("disclosures")}
                actionLabel="공시 전체"
              />
              <div className="grid gap-4">
                <div className="rounded-xl border border-border/50 bg-card/60 p-4 ring-1 ring-border/30 backdrop-blur-sm">
                  <Badge variant="outline" className="mb-2 h-5 px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    Surface Snapshot
                  </Badge>
                  <h3 className="text-lg font-bold tracking-tight text-foreground">시장 표면 상태</h3>
                  <div className="mt-4">
                    <SurfaceSnapshotContent coverage={coverage} />
                  </div>
                </div>
                <div className="rounded-xl border border-border/50 bg-card/60 p-4 ring-1 ring-border/30 backdrop-blur-sm">
                  <Badge variant="outline" className="mb-2 h-5 px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    Column Pulse
                  </Badge>
                  <h3 className="text-lg font-bold tracking-tight text-foreground">현재 컬럼 리드</h3>
                  <div className="mt-4">
                    <ColumnPulseContent headerContext={headerContext} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.9fr)]">
          <div className="space-y-5">
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

          <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
            <RailSection title="시장 표면 상태" eyebrow="Surface Snapshot">
              <SurfaceSnapshotContent coverage={coverage} />
            </RailSection>

            <RailSection title="현재 컬럼 리드" eyebrow="Column Pulse">
              <ColumnPulseContent headerContext={headerContext} />
            </RailSection>

            <RailSection title="소스 반영 상태" eyebrow="Source Coverage">
              <SourceCoverageContent coverage={coverage} />
            </RailSection>
          </aside>
        </div>
      )}
    </div>
  );
}
