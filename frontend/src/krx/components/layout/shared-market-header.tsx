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
  if (relatedTabLink.includes("/macro-calendar") || relatedTabLink.includes("/global-events")) return "매크로 캘린더";
  if (relatedTabLink.includes("/news")) return "시장 뉴스";
  if (relatedTabLink.includes("/insights") || relatedTabLink.includes("/macro")) return "AI 인사이트";
  return "시장 신호";
}

export function SharedMarketHeader({ data }: { data: AppHeader }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-6 md:pt-8">
      <section
        aria-labelledby="market-status-title"
        className="rounded-[28px] border border-slate-200/80 bg-white/92 p-4 shadow-[0_18px_48px_-32px_rgba(15,23,42,0.35)]"
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-slate-500">MARKET STATUS</p>
            <h1 id="market-status-title" className="mt-2 text-lg font-black tracking-tight text-slate-950 md:text-xl">
              실시간 상태
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">{data.sourceCoverage.summary}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2 md:justify-end">
            <Badge variant="high">{phaseLabel(data.phase)}</Badge>
            <Badge variant={coverageVariant(data.sourceCoverage.state)}>
              소스 {data.sourceCoverage.availableSources}/{data.sourceCoverage.expectedSources}
            </Badge>
            {data.updatedAt ? <Badge>업데이트 {formatKoreanDate(data.updatedAt)}</Badge> : <Badge variant="low">업데이트 대기</Badge>}
          </div>
        </div>

        {data.sourceCoverage.items.length ? (
          <div className="mt-4 flex flex-wrap gap-2 text-xs" data-testid="source-coverage">
            {data.sourceCoverage.items.map((item) => (
              <span key={item.key} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-700">
                {item.label} · {coverageStatusLabel(item.status)}
              </span>
            ))}
          </div>
        ) : (
          <EmptyState
            title="공통 헤더 데이터를 준비 중입니다"
            description="장 상태와 속보 정보는 소스 연결이 완료되면 자동으로 표시됩니다."
          />
        )}
      </section>

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
