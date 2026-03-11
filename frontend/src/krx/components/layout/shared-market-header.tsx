import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { formatKoreanDate } from "@/krx/lib/utils";
import { AppHeader } from "@/krx/types/domain";

function phaseLabel(phase: AppHeader["phase"]) {
  if (phase === "live") return "장중";
  if (phase === "post-close") return "장후";
  return "장전";
}

function coverageVariant(state: AppHeader["sourceCoverage"]["state"]) {
  if (state === "full") return "positive";
  if (state === "partial") return "high";
  return "low";
}

function coverageStatusLabel(status: AppHeader["sourceCoverage"]["items"][number]["status"]) {
  if (status === "available") return "정상";
  if (status === "partial") return "부분";
  return "지연";
}

function relatedTabLabel(relatedTabLink: string) {
  if (relatedTabLink.includes("/global-events")) return "글로벌 이벤트";
  if (relatedTabLink.includes("/news")) return "뉴스";
  return "시장 신호";
}

export function SharedMarketHeader({ data }: { data: AppHeader }) {
  const hasToneLine = data.marketToneLine.trim().length > 0;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-6 md:pt-8">
      {hasToneLine ? (
        <section
          aria-labelledby="market-tone-title"
          className="relative overflow-hidden rounded-[28px] border border-amber-200/18 bg-gradient-to-br from-slate-950 via-slate-900 to-stone-900 p-6 text-slate-100 shadow-xl"
        >
          <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-amber-200/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-16 -left-10 h-44 w-44 rounded-full bg-white/6 blur-3xl" />

          <div className="relative flex flex-col gap-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl">
                <p className="text-xs font-semibold tracking-[0.18em] text-amber-100/90">MARKET INTERPRETATION</p>
                <h1 id="market-tone-title" className="mt-2 text-2xl font-black tracking-tight text-slate-50 md:text-3xl">
                  오늘의 시장 톤
                </h1>
                <p className="mt-3 text-sm leading-7 text-slate-200/92 md:text-base">{data.marketToneLine}</p>
              </div>

              <div className="flex flex-wrap items-center gap-2 xl:max-w-sm xl:justify-end">
                <Badge variant="high">{phaseLabel(data.phase)}</Badge>
                <Badge variant={coverageVariant(data.sourceCoverage.state)}>
                  소스 {data.sourceCoverage.availableSources}/{data.sourceCoverage.expectedSources}
                </Badge>
                {data.updatedAt ? <Badge>업데이트 {formatKoreanDate(data.updatedAt)}</Badge> : <Badge variant="low">업데이트 대기</Badge>}
              </div>
            </div>

            {data.supportingPoints.length ? (
              <div className="flex flex-wrap gap-2" data-testid="supporting-points">
                {data.supportingPoints.slice(0, 3).map((point) => (
                  <span
                    key={`${point.sourceKey}-${point.text}`}
                    title={point.sourceLabel}
                    className="inline-flex rounded-full border border-white/10 bg-white/7 px-3 py-1.5 text-sm text-slate-100/92 backdrop-blur"
                  >
                    {point.text}
                  </span>
                ))}
              </div>
            ) : null}

            <div
              className="rounded-2xl border border-white/12 bg-white/6 px-4 py-3 text-sm text-slate-200/90"
              data-testid="source-coverage"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">소스 커버리지</p>
              <p className="mt-1">{data.sourceCoverage.summary}</p>
              {data.sourceCoverage.items.length ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {data.sourceCoverage.items.map((item) => (
                    <span
                      key={item.key}
                      className="rounded-full border border-white/15 bg-white/8 px-2.5 py-1 text-slate-100/90"
                    >
                      {item.label} · {coverageStatusLabel(item.status)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </section>
      ) : (
        <EmptyState
          title="공통 헤더 데이터를 준비 중입니다"
          description="시장 톤과 속보 정보는 소스 연결이 완료되면 자동으로 표시됩니다."
        />
      )}

      {data.breakingNews ? (
        <section className="mt-4 rounded-2xl border border-amber-300/30 bg-amber-50/90 px-4 py-3 text-slate-900 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="high">{data.breakingNews.label}</Badge>
                <p className="truncate text-sm font-bold text-slate-900 md:text-base">{data.breakingNews.headline}</p>
              </div>
              <p className="mt-1 text-sm text-slate-700">{data.breakingNews.whyItMattersOneLine}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <span>{data.breakingNews.impactScope}</span>
                <span aria-hidden>•</span>
                <span>연결 탭: {relatedTabLabel(data.breakingNews.relatedTabLink)}</span>
                {data.breakingNews.publishedAt ? (
                  <>
                    <span aria-hidden>•</span>
                    <time dateTime={data.breakingNews.publishedAt}>{formatKoreanDate(data.breakingNews.publishedAt)}</time>
                  </>
                ) : null}
                {data.breakingNews.sourceName ? (
                  <>
                    <span aria-hidden>•</span>
                    <span>{data.breakingNews.sourceName}</span>
                  </>
                ) : null}
              </div>
            </div>

            <Link
              href={data.breakingNews.relatedTabLink}
              className="inline-flex h-10 min-w-[128px] shrink-0 items-center justify-center rounded-full border border-amber-500 bg-amber-300 px-4 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
            >
              관련 탭 보기
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  );
}
