import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { formatKoreanDate } from "@/krx/lib/utils";
import { MarketNewsCardView } from "@/krx/news/components/market-news-card";
import { newsTabHref, NEWS_TAB_OPTIONS, NewsTabKey } from "@/krx/news/lib/tabs";
import {
  MarketNewsBriefing,
  MarketNewsCard,
  MarketNewsCoverage,
  MarketNewsHeaderContext,
} from "@/krx/types/domain";

type StoryClusterItem = {
  key: string;
  title: string;
  summary: string | null;
  whyItMatters: string;
  marketImpact: string | null;
  marketScope: MarketNewsCard["marketScope"];
  primaryRegion: MarketNewsCard["primaryRegion"] | null;
  importanceLabel: MarketNewsCard["importanceLabel"];
  storyState: MarketNewsCard["storyState"];
  evidenceCount: number;
  publishedAt: string | null;
  sourceLabel: string | null;
  sourceUrl: string | null;
  detailHref: string;
};

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

function marketScopeLabel(scope: MarketNewsCard["marketScope"] | null) {
  switch (scope) {
    case "kr_market":
      return "한국 증시";
    case "global_market":
      return "글로벌 변수";
    case "company":
      return "공시/종목";
    case "sector":
      return "업종/테마";
    default:
      return "시장 표면";
  }
}

function safeExternalHref(value: string | null) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function storyStateLabel(value: MarketNewsCard["storyState"]) {
  if (value === "NEW") return "새 이슈";
  if (value === "DISCLOSURE_CONFIRMED") return "공시 확인";
  return "진행 중";
}

function importanceLabelText(value: MarketNewsCard["importanceLabel"]) {
  if (value === "high") return "영향 큼";
  if (value === "low") return "보조";
  return "중간";
}

function storyDetailHref(scope: MarketNewsCard["marketScope"]) {
  if (scope === "global_market") return newsTabHref("global");
  if (scope === "company") return newsTabHref("disclosures");
  return newsTabHref("kr");
}

function dedupeBriefingPoints(items: string[]) {
  const deduped: string[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const text = item.trim();
    if (!text) continue;
    const normalized = text.replace(/\s+/g, " ").toLowerCase();
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    deduped.push(text);
  }
  return deduped;
}

function dedupeBriefingLinks(items: MarketNewsBriefing["linkedHeadlines"]) {
  const deduped: MarketNewsBriefing["linkedHeadlines"] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const key = [item.sourceUrl ?? "", item.cardId ?? "", item.title.trim().toLowerCase()].find(Boolean) ?? item.title.trim().toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  return deduped;
}

function buildStoryClusters({
  krCards,
  globalCards,
  disclosureCards,
  linkedHeadlines,
}: {
  krCards: MarketNewsCard[];
  globalCards: MarketNewsCard[];
  disclosureCards: MarketNewsCard[];
  linkedHeadlines: MarketNewsBriefing["linkedHeadlines"];
}) {
  const cardMap = new Map<string, MarketNewsCard>();
  [...krCards, ...globalCards, ...disclosureCards].forEach((card) => {
    cardMap.set(card.id, card);
  });

  const linkedClusters = linkedHeadlines.flatMap((item, index) => {
    const matchedCard = item.cardId ? cardMap.get(item.cardId) : null;
    const scope = matchedCard?.marketScope ?? item.marketScope ?? "kr_market";
    const primaryRegion = matchedCard?.primaryRegion ?? item.primaryRegion ?? "KR";
    const summary = item.summary ?? matchedCard?.oneLineSummary ?? null;
    const whyItMatters = matchedCard?.whyItMatters ?? summary ?? "핵심 스토리의 의미를 정리하는 중입니다.";
    const marketImpact = matchedCard?.marketImpact ?? null;
    const sourceLabel = item.sourceLabel ?? null;
    const sourceUrl = safeExternalHref(item.sourceUrl);
    return [
      {
        key: `${item.cardId ?? "linked"}-${index}`,
        title: item.title,
        summary,
        whyItMatters,
        marketImpact,
        marketScope: scope,
        primaryRegion,
        importanceLabel: matchedCard?.importanceLabel ?? "high",
        storyState: matchedCard?.storyState ?? "ONGOING",
        evidenceCount: matchedCard?.evidenceCount ?? (sourceUrl ? 1 : 0),
        publishedAt: item.publishedAt ?? matchedCard?.publishedAt ?? null,
        sourceLabel,
        sourceUrl,
        detailHref: storyDetailHref(scope),
      } satisfies StoryClusterItem,
    ];
  });

  if (linkedClusters.length) {
    return linkedClusters.slice(0, 3);
  }

  const rankedFallback = [...krCards, ...globalCards, ...disclosureCards]
    .sort((left, right) => right.rankingScore - left.rankingScore)
    .slice(0, 3);

  return rankedFallback.map((card) => ({
    key: card.id,
    title: card.title,
    summary: card.oneLineSummary,
    whyItMatters: card.whyItMatters,
    marketImpact: card.marketImpact,
    marketScope: card.marketScope,
    primaryRegion: card.primaryRegion,
    importanceLabel: card.importanceLabel,
    storyState: card.storyState,
    evidenceCount: card.evidenceCount,
    publishedAt: card.publishedAt,
    sourceLabel: null,
    sourceUrl: null,
    detailHref: storyDetailHref(card.marketScope),
  }));
}

function buildReportParagraphs(summary: string) {
  const normalized = summary.replace(/\r\n/g, "\n").trim();
  const explicitParagraphs = normalized
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  if (explicitParagraphs.length > 1) {
    return explicitParagraphs;
  }

  const sentences = normalized
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
  if (sentences.length <= 2) {
    return sentences.length ? [sentences.join(" ")] : [];
  }

  const paragraphs: string[] = [];
  for (let index = 0; index < sentences.length; index += 2) {
    paragraphs.push(sentences.slice(index, index + 2).join(" "));
  }
  return paragraphs;
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
  footer,
}: {
  title: string;
  description: string;
  cards: MarketNewsCard[];
  emptyTitle: string;
  emptyDescription: string;
  actionHref?: string;
  actionLabel?: string;
  limit?: number;
  footer?: ReactNode;
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
          {actionHref && actionLabel ? (
            <Link
              href={actionHref}
              className="inline-flex shrink-0 items-center rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
            >
              {actionLabel}
            </Link>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {visibleCards.length ? (
          <div className="space-y-4">
            <div className="grid gap-4">
              {visibleCards.map((card) => (
                <MarketNewsCardView key={card.id} card={card} />
              ))}
            </div>
            {footer}
          </div>
        ) : (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        )}
      </CardContent>
    </Card>
  );
}

function StoryClusterBoard({ items }: Readonly<{ items: StoryClusterItem[] }>) {
  return (
    <Card className="border-border/50 bg-card/95 shadow-lg backdrop-blur-sm">
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1.5">
            <Badge variant="outline" className="h-5 w-fit px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Today Story Board
            </Badge>
            <CardTitle className="text-xl font-bold tracking-tight">오늘 핵심 스토리</CardTitle>
            <CardDescription className="text-sm leading-relaxed">
              먼저 서사를 잡고, 아래 브리핑에서 해석을 이어서 읽는 구조로 정리했습니다.
            </CardDescription>
          </div>
          <Badge variant="outline" className="h-6 px-2.5 font-medium text-muted-foreground">
            상위 {items.length}개
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {items.length ? (
          <div className="grid gap-4 lg:grid-cols-3">
            {items.map((item) => (
              <article key={item.key} className="rounded-2xl border border-border/50 bg-card/80 p-5 ring-1 ring-border/30">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{importanceLabelText(item.importanceLabel)}</Badge>
                  <Badge variant="outline">{storyStateLabel(item.storyState)}</Badge>
                  <Badge variant="outline">{marketScopeLabel(item.marketScope)}</Badge>
                </div>
                <h3 className="mt-4 text-lg font-bold leading-7 tracking-tight text-foreground">{item.title}</h3>
                {item.summary ? <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.summary}</p> : null}

                <div className="mt-4 space-y-3 rounded-2xl border border-border/50 bg-muted/25 p-4">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">왜 중요한가</p>
                    <p className="mt-1 text-sm leading-6 text-foreground/90">{item.whyItMatters}</p>
                  </div>
                  {item.marketImpact ? (
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">KRX 영향</p>
                      <p className="mt-1 text-sm leading-6 text-foreground/90">{item.marketImpact}</p>
                    </div>
                  ) : null}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{item.primaryRegion === "GLOBAL" ? "글로벌 변수" : "한국 증시"}</span>
                  <span>·</span>
                  <span>근거 {item.evidenceCount}건</span>
                  {item.publishedAt ? (
                    <>
                      <span>·</span>
                      <span>{formatMaybeDate(item.publishedAt)}</span>
                    </>
                  ) : null}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Link
                    href={item.detailHref}
                    className="inline-flex items-center rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-primary/50 hover:bg-accent hover:text-accent-foreground"
                  >
                    관련 카드 보기
                  </Link>
                  {item.sourceUrl ? (
                    <a
                      href={item.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-semibold text-foreground underline decoration-border underline-offset-4 hover:text-primary"
                    >
                      {item.sourceLabel ?? "원문 보기"}
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="핵심 스토리를 아직 만들지 못했습니다"
            description="상위 뉴스 카드가 모이면 이 영역에 오늘 시장 서사를 먼저 정리합니다."
          />
        )}
      </CardContent>
    </Card>
  );
}

function SummaryBriefingBoard({ briefing }: Readonly<{ briefing: MarketNewsBriefing }>) {
  const summaryParagraphs = buildReportParagraphs(briefing.summary);
  const keyPoints = dedupeBriefingPoints(briefing.keyPoints);
  const linkedHeadlines = dedupeBriefingLinks(briefing.linkedHeadlines);
  const uniqueSources = Array.from(
    new Set(linkedHeadlines.map((item) => item.sourceLabel).filter((label): label is string => Boolean(label))),
  );

  return (
    <Card className="border-border/50 bg-card/95 shadow-lg backdrop-blur-sm">
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1.5">
            <Badge variant="outline" className="h-5 w-fit px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Secondary Synthesis
            </Badge>
            <CardTitle className="text-xl font-bold tracking-tight">스토리 종합 브리핑</CardTitle>
            <CardDescription className="text-sm leading-relaxed">
              위 핵심 스토리를 AI가 서술형으로 다시 묶어 현재 해석을 보조합니다.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="h-6 px-2.5 font-medium">
              {briefing.generationMethod === "llm" ? "AI 브리핑" : "규칙 기반 브리핑"}
            </Badge>
            <Badge variant="outline" className="h-6 px-2.5 font-medium text-muted-foreground">
              {formatMaybeDate(briefing.updatedAt)}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <article className="mx-auto max-w-4xl space-y-8">
          <header className="border-b border-border/40 pb-6">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">서술형 정리</p>
            <h3 className="mt-3 text-3xl font-black leading-tight tracking-tight text-foreground sm:text-4xl">{briefing.headline}</h3>
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>{formatMaybeDate(briefing.updatedAt)}</span>
              <span>·</span>
              <span>{briefing.generationMethod === "llm" ? "AI가 상위 흐름을 서술형 리포트로 정리" : "현재 카드 기준 자동 리포트"}</span>
              <span>·</span>
              <span>근거 {linkedHeadlines.length}건</span>
              {uniqueSources.length ? (
                <>
                  <span>·</span>
                  <span>{uniqueSources.join(" · ")}</span>
                </>
              ) : null}
            </div>
          </header>

          <section className="space-y-4">
            <h4 className="text-sm font-bold uppercase tracking-[0.18em] text-muted-foreground">스토리 해설</h4>
            <div className="space-y-5">
              {(summaryParagraphs.length ? summaryParagraphs : [briefing.summary]).map((paragraph, index) => (
                <p key={`${index}-${paragraph}`} className="text-[15px] leading-8 text-foreground/90 sm:text-base sm:leading-8">
                  {paragraph}
                </p>
              ))}
            </div>
          </section>

          {keyPoints.length ? (
            <section className="space-y-4 border-t border-border/40 pt-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h4 className="text-sm font-bold uppercase tracking-[0.18em] text-muted-foreground">오늘 체크할 변수</h4>
                {briefing.aiProvider ? (
                  <Badge variant="outline" className="h-6 px-2.5 font-medium text-muted-foreground">
                    {briefing.aiProvider}
                    {briefing.aiModel ? ` · ${briefing.aiModel}` : ""}
                  </Badge>
                ) : null}
              </div>
              <ol className="space-y-3">
                {keyPoints.map((point, index) => (
                  <li key={`${index}-${point}`} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-3">
                    <span className="mt-0.5 flex size-7 items-center justify-center rounded-full bg-primary/12 text-sm font-bold text-primary">
                      {index + 1}
                    </span>
                    <span className="text-sm leading-7 text-foreground/90">{point}</span>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <section className="space-y-4 border-t border-border/40 pt-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold uppercase tracking-[0.18em] text-muted-foreground">참고 기사와 공시</h4>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  아래 원문은 종합 리포트가 근거로 삼은 기사와 공시입니다. 전체 사건을 나열하기보다, 지금 해석에 직접 연결되는 항목만 남깁니다.
                </p>
              </div>
              <Badge variant="outline" className="h-6 px-2.5 font-medium">
                {linkedHeadlines.length}건
              </Badge>
            </div>
            <div className="space-y-4">
              {linkedHeadlines.length ? (
                linkedHeadlines.map((item, index) => {
                  const safeHref = safeExternalHref(item.sourceUrl);
                  return (
                    <article key={`${index}-${item.cardId ?? item.title}-${item.sourceUrl ?? "no-url"}`} className="border-l-2 border-border pl-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary" className="h-5 px-2 text-[10px] font-semibold">
                          {marketScopeLabel(item.marketScope)}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{item.primaryRegion ?? "KR"}</span>
                        <span className="text-xs text-muted-foreground">{formatMaybeDate(item.publishedAt)}</span>
                        {item.sourceLabel ? <span className="text-xs text-muted-foreground">{item.sourceLabel}</span> : null}
                      </div>
                      {safeHref ? (
                        <a
                          href={safeHref}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 block text-base font-semibold leading-7 text-foreground underline-offset-4 hover:text-primary hover:underline"
                        >
                          {item.title}
                        </a>
                      ) : (
                        <p className="mt-2 text-base font-semibold leading-7 text-foreground">{item.title}</p>
                      )}
                      {item.summary ? <p className="mt-2 text-sm leading-7 text-muted-foreground">{item.summary}</p> : null}
                    </article>
                  );
                })
              ) : (
                <EmptyState title="링크할 핵심 뉴스가 없습니다" description="대표 기사와 공시가 준비되면 이 영역이 자동으로 갱신됩니다." />
              )}
            </div>
          </section>
        </article>

        <div className="mt-8 rounded-2xl border border-border/50 bg-card/60 p-5 ring-1 ring-border/30">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="text-sm font-bold tracking-tight text-foreground">브리핑 메모</h4>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                이 리포트는 상위 뉴스 카드와 공시를 묶어 현재 해석에 필요한 맥락만 다시 서술합니다.
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-xl border border-border/50 bg-card px-4 py-3">
              <p className="text-xs text-muted-foreground">브리핑 방식</p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {briefing.generationMethod === "llm" ? "장문 서술형 AI 리포트" : "규칙 기반 서술형 리포트"}
              </p>
            </div>
            <div className="rounded-xl border border-border/50 bg-card px-4 py-3">
              <p className="text-xs text-muted-foreground">현재 근거 범위</p>
              <p className="mt-1 text-sm font-semibold text-foreground">{linkedHeadlines.length}건의 기사·공시를 참조 중</p>
            </div>
            <div className="rounded-xl border border-border/50 bg-card px-4 py-3">
              <p className="text-xs text-muted-foreground">주요 소스</p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {uniqueSources.length ? uniqueSources.join(" · ") : "표시 가능한 소스 정보 없음"}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
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
        <Badge variant="outline" className="h-6 px-2.5 font-medium text-muted-foreground">
          백엔드 갱신 추적 중
        </Badge>
      </div>
    </div>
  );
}

function ColumnPulseContent({ headerContext }: Readonly<{ headerContext: MarketNewsHeaderContext }>) {
  return (
    <div className="space-y-3">
      {headerContext.columns.map((column) => (
        <div
          key={column.key}
          className="rounded-xl border border-border/50 bg-muted/40 p-4 ring-1 ring-border/30 transition-colors hover:bg-muted/60"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <Badge variant="outline" className="mb-2 h-5 px-2 text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground">
                {column.label}
              </Badge>
              <p className="text-base font-semibold tracking-tight text-foreground">{column.leadTitle ?? "선두 카드 없음"}</p>
            </div>
            <Badge variant="secondary" className="h-6 px-2.5 font-semibold">
              {column.count}건
            </Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {column.leadScope ? `대표 범위: ${column.leadScope}` : "대표 범위 정보 없음"}
          </p>
        </div>
      ))}
    </div>
  );
}

function SourceCoverageContent({ coverage }: Readonly<{ coverage: MarketNewsCoverage }>) {
  return coverage.items.length ? (
    coverage.items.map((item) => (
      <div
        key={item.provider}
        className="flex items-start justify-between gap-3 rounded-xl border border-border/50 bg-card p-4 ring-1 ring-border/30 transition-colors hover:bg-muted/20"
      >
        <div>
          <p className="text-sm font-semibold text-foreground">{item.provider}</p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            문서 {item.documentCount}건 · 이벤트 {item.eventCount}건 · 근거 {item.evidenceCount}건
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            {item.lastSyncedAt ? `최근 동기화 ${formatMaybeDate(item.lastSyncedAt)}` : "최근 동기화 정보 없음"}
          </p>
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
  briefing,
  headerContext,
  coverage,
  activeTab,
  krPage,
  krPageSize,
  krPageCount,
  onKrPagePrevious,
  onKrPageNext,
}: {
  krCards: MarketNewsCard[];
  globalCards: MarketNewsCard[];
  disclosureCards: MarketNewsCard[];
  briefing: MarketNewsBriefing;
  headerContext: MarketNewsHeaderContext;
  coverage: MarketNewsCoverage;
  activeTab: NewsTabKey;
  krPage: number;
  krPageSize: number;
  krPageCount: number;
  onKrPagePrevious: () => void;
  onKrPageNext: () => void;
}) {
  const krPageStart = krCards.length ? krPage * krPageSize + 1 : 0;
  const krPageEnd = Math.min((krPage + 1) * krPageSize, krCards.length);
  const pagedKrCards = krCards.slice(krPage * krPageSize, krPage * krPageSize + krPageSize);
  const storyClusters = buildStoryClusters({
    krCards,
    globalCards,
    disclosureCards,
    linkedHeadlines: dedupeBriefingLinks(briefing.linkedHeadlines),
  });
  const activeSummary =
    activeTab === "summary"
      ? "핵심 스토리를 먼저 보여주고, AI 브리핑은 그 뒤에서 현재 해석을 다시 묶습니다."
      : activeTab === "kr"
        ? "국내 시장 직접 영향 뉴스를 시간순으로 누적한 피드"
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
              <CardTitle className="text-3xl font-black tracking-tight">시장 뉴스</CardTitle>
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
            <Badge variant="outline" className="h-7 px-3 font-medium">
              {coverage.summary}
            </Badge>
            <Badge variant="outline" className="h-7 px-3 font-medium text-muted-foreground">
              {formatMaybeDate(coverage.updatedAt)}
            </Badge>
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
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="space-y-5">
            <StoryClusterBoard items={storyClusters} />
            <SummaryBriefingBoard briefing={briefing} />
          </div>

          <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
            <RailSection title="시장 표면 상태" eyebrow="표면 스냅샷">
              <SurfaceSnapshotContent coverage={coverage} />
            </RailSection>

            <RailSection title="현재 컬럼 리드" eyebrow="컬럼 흐름">
              <ColumnPulseContent headerContext={headerContext} />
            </RailSection>

            <RailSection title="소스 반영 상태" eyebrow="소스 커버리지">
              <SourceCoverageContent coverage={coverage} />
            </RailSection>
          </aside>
        </section>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.9fr)]">
          <div className="space-y-5">
            {activeTab === "kr" ? (
              <CardSection
                title="한국 증시"
                description="한국 증시에 직접 연결되는 카드를 최신 시각 순으로 누적하고, 5개씩 넘겨 보도록 구성했습니다."
                cards={pagedKrCards}
                emptyTitle="한국 증시 카드가 없습니다"
                emptyDescription="아직 동기화된 데이터가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
                footer={
                  krCards.length > krPageSize ? (
                    <div className="flex flex-col gap-3 border-t border-border/50 pt-4 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-xs text-muted-foreground">
                        {krPageStart}-{krPageEnd} / {krCards.length}건
                      </p>
                      <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={onKrPagePrevious} disabled={krPage <= 0}>
                          이전 5개
                        </Button>
                        <Badge variant="outline" className="h-7 px-3 font-medium">
                          {krPage + 1} / {krPageCount}
                        </Badge>
                        <Button variant="outline" size="sm" onClick={onKrPageNext} disabled={krPage >= krPageCount - 1}>
                          다음 5개
                        </Button>
                      </div>
                    </div>
                  ) : null
                }
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
            <RailSection title="시장 표면 상태" eyebrow="표면 스냅샷">
              <SurfaceSnapshotContent coverage={coverage} />
            </RailSection>

            <RailSection title="현재 컬럼 리드" eyebrow="컬럼 흐름">
              <ColumnPulseContent headerContext={headerContext} />
            </RailSection>

            <RailSection title="소스 반영 상태" eyebrow="소스 커버리지">
              <SourceCoverageContent coverage={coverage} />
            </RailSection>
          </aside>
        </div>
      )}
    </div>
  );
}
