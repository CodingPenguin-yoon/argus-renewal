import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { SectionHeader } from "@/krx/components/ui/section-header";
import {
  globalEventsTabHref,
  GLOBAL_EVENTS_BASE_TAB_OPTIONS,
  GLOBAL_EVENTS_EARNINGS_TAB_OPTION,
  GlobalEventsTabKey,
} from "@/krx/global-events/lib/tabs";
import { IMPORTANCE_LABELS } from "@/krx/lib/constants";
import { GlobalEventItem, GlobalEventsCoverage } from "@/krx/types/domain";

function importanceVariant(value: GlobalEventItem["importance"]) {
  if (value === "high") return "high";
  if (value === "low") return "low";
  return "medium";
}

function coverageVariant(state: GlobalEventsCoverage["state"]) {
  if (state === "full") return "positive";
  if (state === "partial") return "neutral";
  return "negative";
}

function coverageItemVariant(status: GlobalEventsCoverage["items"][number]["status"]) {
  if (status === "available") return "positive";
  if (status === "partial") return "high";
  return "low";
}

function coverageItemStatusLabel(status: GlobalEventsCoverage["items"][number]["status"]) {
  if (status === "available") return "정상";
  if (status === "partial") return "부분";
  return "지연";
}

function toneVariant(tone: NonNullable<GlobalEventItem["impact"]>["tone"]) {
  if (tone === "risk_on" || tone === "dovish") return "positive";
  if (tone === "risk_off" || tone === "hawkish") return "negative";
  return "neutral";
}

function formatDateOnly(dateText: string) {
  const [year, month, day] = dateText.split("-").map((value) => Number(value));
  if (!year || !month || !day) return dateText;
  return `${month}월 ${day}일`;
}

function formatTimeLabel(item: GlobalEventItem) {
  if (!item.eventTimeKst) {
    return `${formatDateOnly(item.eventDateKst)} · 시간 미정`;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  }).format(new Date(item.eventTimeKst));
}

function formatMaybeDate(value: string | null) {
  if (!value) return "동기화 정보 없음";
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Seoul",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function metricFallback(item: GlobalEventItem, key: "previous" | "forecast" | "actual" | "surprise") {
  if (key === "actual" && item.release.state !== "released" && item.release.state !== "revised") {
    return "발표 전";
  }
  if (key === "surprise" && (!item.release.actual || !item.release.forecast)) {
    return "계산 불가";
  }
  return "미제공";
}

function MetricPill({
  label,
  value,
  fallback,
}: {
  label: string;
  value: string | null;
  fallback: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white/75 px-3 py-2">
      <p className="text-[11px] font-semibold tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value ?? fallback}</p>
    </div>
  );
}

function EventListItem({ item }: { item: GlobalEventItem }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white/85 p-4 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.45)]">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="default">{formatTimeLabel(item)}</Badge>
        <Badge variant={importanceVariant(item.importance)}>{IMPORTANCE_LABELS[item.importance ?? "medium"]}</Badge>
        {item.revisionNote ? <Badge variant="neutral">일정 변경</Badge> : null}
        {item.release.state === "released" || item.release.state === "revised" ? <Badge variant="positive">발표 반영</Badge> : null}
      </div>

      <div className="mt-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-black tracking-tight text-slate-900">{item.title}</h3>
          <p className="mt-1 text-sm text-slate-600">
            {item.country} · {item.source.name}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        <MetricPill label="이전" value={item.release.previous} fallback={metricFallback(item, "previous")} />
        <MetricPill label="예상" value={item.release.forecast} fallback={metricFallback(item, "forecast")} />
        <MetricPill label="실제" value={item.release.actual} fallback={metricFallback(item, "actual")} />
        <MetricPill label="서프라이즈" value={item.release.surprise} fallback={metricFallback(item, "surprise")} />
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-700">{item.whyItMattersKo}</p>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {item.source.url ? (
          <Link className="font-semibold text-slate-700 underline decoration-slate-300 underline-offset-4" href={item.source.url} target="_blank">
            공식 소스
          </Link>
        ) : (
          <span>공식 소스 링크 없음</span>
        )}
        {item.release.sourceUrl ? (
          <Link className="font-semibold text-slate-700 underline decoration-slate-300 underline-offset-4" href={item.release.sourceUrl} target="_blank">
            실제값 출처
          </Link>
        ) : null}
      </div>
    </article>
  );
}

function HighlightCard({ item }: { item: GlobalEventItem }) {
  return (
    <article className="relative overflow-hidden rounded-3xl border border-slate-800/85 bg-[linear-gradient(145deg,#0f172a,#1e293b_55%,#334155)] p-5 text-slate-100 shadow-[0_24px_60px_-28px_rgba(15,23,42,0.75)]">
      <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-amber-300/12 blur-2xl" />
      <div className="flex items-center gap-2">
        <Badge variant={importanceVariant(item.importance)}>{IMPORTANCE_LABELS[item.importance ?? "medium"]}</Badge>
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">{item.eventType}</span>
      </div>
      <h3 className="mt-4 text-xl font-black tracking-tight text-white">{item.title}</h3>
      <p className="mt-2 text-sm text-slate-300">{formatTimeLabel(item)}</p>
      <p className="mt-4 text-sm leading-6 text-slate-200">{item.impact?.summaryKo ?? item.whyItMattersKo}</p>
      <div className="mt-5 flex flex-wrap gap-2 text-xs">
        {(item.impact?.impactChannels.length ? item.impact.impactChannels : ["USD/KRW", "외국인 수급"]).map((channel) => (
          <span key={channel} className="rounded-full border border-white/10 bg-white/8 px-2.5 py-1 text-slate-100">
            {channel}
          </span>
        ))}
      </div>
    </article>
  );
}

function ImpactCard({ item }: { item: GlobalEventItem }) {
  const impact = item.impact;
  if (!impact) return null;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white/88 p-4 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.45)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[0.16em] text-slate-500">영향 해석 카드</p>
          <h3 className="mt-1 text-base font-black tracking-tight text-slate-900">{item.title}</h3>
        </div>
        <Badge variant={toneVariant(impact.tone)}>
          {impact.tone === "hawkish"
            ? "매파"
            : impact.tone === "dovish"
              ? "비둘기"
              : impact.tone === "risk_on"
                ? "리스크온"
                : impact.tone === "risk_off"
                  ? "리스크오프"
                  : "중립"}
        </Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">{impact.summaryKo}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {impact.impactChannels.map((channel) => (
          <span key={channel} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
            {channel}
          </span>
        ))}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <MetricPill label="이전" value={item.release.previous} fallback={metricFallback(item, "previous")} />
        <MetricPill label="예상" value={item.release.forecast} fallback={metricFallback(item, "forecast")} />
        <MetricPill label="실제" value={item.release.actual} fallback={metricFallback(item, "actual")} />
      </div>
    </article>
  );
}

export function GlobalEventsDashboard({
  highlights,
  upcoming,
  week,
  coverage,
  activeTab,
}: {
  highlights: GlobalEventItem[];
  upcoming: GlobalEventItem[];
  week: GlobalEventItem[];
  coverage: GlobalEventsCoverage;
  activeTab: GlobalEventsTabKey;
}) {
  const uniqueEvents = [...highlights, ...upcoming, ...week].filter(
    (item, index, list) => list.findIndex((candidate) => candidate.eventKey === item.eventKey) === index,
  );
  const earningsItems = uniqueEvents.filter(
    (item) => item.eventType.toUpperCase() === "EARNINGS" || item.category.toLowerCase() === "earnings",
  );
  const hasEarningsTab = earningsItems.length > 0;
  const tabOptions = hasEarningsTab
    ? [...GLOBAL_EVENTS_BASE_TAB_OPTIONS, GLOBAL_EVENTS_EARNINGS_TAB_OPTION]
    : GLOBAL_EVENTS_BASE_TAB_OPTIONS;
  const resolvedActiveTab = activeTab === "earnings" && !hasEarningsTab ? "summary" : activeTab;
  const impactCards = [...highlights, ...week]
    .filter((item, index, list) => item.impact && list.findIndex((candidate) => candidate.eventKey === item.eventKey) === index)
    .slice(0, 4);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-6 md:py-8">
      <section className="relative overflow-hidden rounded-[2rem] border border-slate-200 bg-[linear-gradient(140deg,#f8fbff,#edf3fa_58%,#e4ecf5)] p-6 shadow-[0_28px_70px_-40px_rgba(15,23,42,0.45)]">
        <div className="pointer-events-none absolute -left-16 top-0 h-36 w-36 rounded-full bg-sky-300/18 blur-3xl" />
        <div className="pointer-events-none absolute right-0 top-6 h-32 w-32 rounded-full bg-amber-300/20 blur-3xl" />
        <SectionHeader
          title="매크로 캘린더"
          description="한국 증시에 파급력이 큰 해외 촉매와 발표 일정을 이벤트 단위로 압축했습니다."
          action={<Badge variant={coverageVariant(coverage.state)}>{coverage.summary}</Badge>}
        />
        <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-slate-600" data-testid="global-events-coverage">
          <Badge variant={coverageVariant(coverage.state)}>
            소스 커버리지 {coverage.availableSources}/{coverage.expectedSources}
          </Badge>
          <Badge variant="neutral">최종 동기화 {formatMaybeDate(coverage.updatedAt)}</Badge>
          {coverage.items.slice(0, 3).map((item) => (
            <Badge key={item.sourceKey} variant={coverageItemVariant(item.status)}>
              {item.sourceName} · {coverageItemStatusLabel(item.status)}
            </Badge>
          ))}
        </div>
        <nav className="mb-4 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="매크로 캘린더 세부 탭" data-testid="global-events-subtabs">
          {tabOptions.map((option) => {
            const active = option.key === resolvedActiveTab;
            return (
              <Link
                key={option.key}
                href={globalEventsTabHref(option.key)}
                role="tab"
                aria-selected={active}
                className={`inline-flex min-w-[68px] items-center justify-center rounded-full border px-3 py-1.5 text-sm font-semibold whitespace-nowrap transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
                  active
                    ? "border-amber-500 bg-amber-300 text-slate-950 shadow-sm"
                    : "border-slate-300 bg-white/85 text-slate-700 hover:border-slate-400 hover:bg-white"
                }`}
              >
                {option.label}
              </Link>
            );
          })}
        </nav>
      </section>

      {resolvedActiveTab === "summary" ? (
        <div className="grid gap-6 lg:grid-cols-[1.55fr_0.95fr]">
          <div className="space-y-6">
            <section className="space-y-4">
              <SectionHeader
                title="이번 주 핵심 촉매"
                description="한국 증시에 파급력이 큰 이벤트를 우선순위로 정렬했습니다."
                action={
                  <Link
                    href={globalEventsTabHref("highlights")}
                    className="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                  >
                    핵심 이벤트 전체
                  </Link>
                }
              />
              {highlights.length ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {highlights.slice(0, 4).map((item) => (
                    <HighlightCard key={item.eventKey} item={item} />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="이번 주 핵심 이벤트가 아직 없습니다"
                  description="현재 표시 가능한 이벤트가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
                />
              )}
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="다음 24시간 주목 이벤트"
                description="발표 임박 이벤트를 시간순으로 먼저 확인합니다."
                action={
                  <Link
                    href={globalEventsTabHref("next-24h")}
                    className="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                  >
                    다음 24시간 전체
                  </Link>
                }
              />
              {upcoming.length ? (
                <div className="grid gap-3">
                  {upcoming.slice(0, 4).map((item) => (
                    <EventListItem key={item.eventKey} item={item} />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="다음 24시간 내 일정이 없습니다"
                  description="현재 표시 가능한 이벤트가 없습니다."
                />
              )}
            </section>
          </div>

          <aside className="space-y-6 lg:sticky lg:top-6 lg:self-start">
            <section className="space-y-4">
              <SectionHeader
                title="한국 시장 영향 해석"
                description="달러, 금리, 외국인 수급에 연결되는 영향 경로를 우선 제공합니다."
              />
              {impactCards.length ? (
                <div className="grid gap-3">
                  {impactCards.map((item) => (
                    <ImpactCard key={item.eventKey} item={item} />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="영향 해석 카드가 아직 없습니다"
                  description="최신 데이터가 준비되면 이 영역에 표시됩니다."
                />
              )}
            </section>
          </aside>
        </div>
      ) : null}

      {resolvedActiveTab === "highlights" ? (
        <section className="space-y-4">
          <SectionHeader
            title="핵심 이벤트"
            description="이번 주 해외 촉매 중 한국 증시에 중요한 이벤트만 선별했습니다."
          />
          {highlights.length ? (
            <div className="grid gap-4 lg:grid-cols-3">
              {highlights.map((item) => (
                <HighlightCard key={item.eventKey} item={item} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="핵심 이벤트가 아직 없습니다"
              description="현재 표시 가능한 이벤트가 없습니다. 최신 데이터가 준비되면 이 영역에 표시됩니다."
            />
          )}
        </section>
      ) : null}

      {resolvedActiveTab === "next-24h" ? (
        <section className="space-y-4">
          <SectionHeader
            title="다음 24시간"
            description="발표 임박 이벤트를 시간순으로 정렬했습니다. 시간 미정 일정은 날짜 기준으로 보조 표기합니다."
          />
          {upcoming.length ? (
            <div className="grid gap-3">
              {upcoming.map((item) => (
                <EventListItem key={item.eventKey} item={item} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="다음 24시간 내 일정이 없습니다"
              description="현재 표시 가능한 이벤트가 없습니다."
            />
          )}
        </section>
      ) : null}

      {resolvedActiveTab === "week" ? (
        <section className="space-y-4">
          <SectionHeader
            title="이번 주"
            description="주간 스케줄 전체를 이어서 보며 CPI, PCE, 고용, 중앙은행, 실적 촉매를 점검합니다."
          />
          {week.length ? (
            <div className="grid gap-3">
              {week.map((item) => (
                <EventListItem key={item.eventKey} item={item} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="이번 주 일정이 없습니다"
              description="현재 표시 가능한 이벤트가 없습니다."
            />
          )}
        </section>
      ) : null}

      {resolvedActiveTab === "earnings" ? (
        <section className="space-y-4">
          <SectionHeader
            title="실적"
            description="대형 기술주 실적 및 가이던스 이벤트를 모아 한국 증시 파급 가능성을 점검합니다."
          />
          {earningsItems.length ? (
            <div className="grid gap-3">
              {earningsItems.map((item) => (
                <EventListItem key={item.eventKey} item={item} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="표시 가능한 실적 이벤트가 없습니다"
              description="현재 표시 가능한 이벤트가 없습니다."
            />
          )}
        </section>
      ) : null}
    </div>
  );
}
