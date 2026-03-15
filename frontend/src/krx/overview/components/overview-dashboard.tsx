import Link from "next/link";

import { formatKoreanDate } from "@/krx/lib/utils";
import type { OverviewTabData } from "@/krx/types/domain";

function formatMaybeDate(value: string | null) {
  return value ? formatKoreanDate(value) : "업데이트 대기";
}

function toneClasses(tone: "positive" | "neutral" | "negative") {
  if (tone === "positive") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (tone === "negative") return "border-rose-200 bg-rose-50 text-rose-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

export function OverviewDashboard({ data }: { data: OverviewTabData }) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:py-8">
      <section className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
        <article className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)] sm:p-7">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 pb-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Overview Desk</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.1rem]">대시보드</h1>
            </div>
            <p className="text-xs text-slate-500">{formatMaybeDate(data.reportUpdatedAt)}</p>
          </div>

          <div className="mt-5 space-y-5">
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/90 px-4 py-4">
              <p className="text-sm leading-7 text-slate-700">{data.marketToneLine}</p>
            </div>

            {data.macroWidgets.length ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-slate-950">거시 미니 위젯</h2>
                  <span className="text-xs text-slate-500">환율 · 에너지 · 금리</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {data.macroWidgets.map((item) => (
                    <article
                      key={item.key}
                      className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold text-slate-950">{item.label}</h3>
                        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses(item.tone)}`}>
                          {item.tone === "positive" ? "우호" : item.tone === "negative" ? "경계" : "중립"}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-700">{item.summary}</p>
                      <p className="mt-3 text-xs text-slate-500">
                        {item.sourceLabel} · {formatMaybeDate(item.updatedAt)}
                      </p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-tight text-slate-950">{data.reportHeadline}</h2>
              <p className="text-base leading-8 text-slate-700">{data.reportSummary}</p>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-950">체크포인트</h3>
              <ul className="space-y-2.5">
                {data.keyTakeaways.map((item, index) => (
                  <li
                    key={`${index}-${item}`}
                    className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-3"
                  >
                    <span className="mt-2 inline-flex h-2 w-2 shrink-0 rounded-full bg-amber-400" />
                    <p className="text-sm leading-6 text-slate-700">{item}</p>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-950">핵심 링크</h3>
              <ul className="space-y-3">
                {data.reportLinks.map((item, index) => (
                  <li
                    key={`${index}-${item.title}`}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4"
                  >
                    {item.href ? (
                      <Link
                        href={item.href}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-semibold text-slate-900 underline decoration-slate-300 underline-offset-4 transition hover:text-amber-700"
                      >
                        {item.title}
                      </Link>
                    ) : (
                      <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    )}
                    <p className="mt-2 text-xs text-slate-500">
                      {item.sourceLabel ?? "출처 미상"} · {formatMaybeDate(item.publishedAt)}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </article>

        <aside className="space-y-6">
          <section className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)]">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Gateway</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">다음 탭 한눈에 보기</h2>
            <div className="mt-4 space-y-3">
              {data.gatewayPanels.map((item) => (
                <Link
                  key={item.key}
                  href={item.href}
                  className="block rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4 transition hover:border-amber-300 hover:bg-amber-50/70"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-slate-950">{item.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{item.summary}</p>
                    </div>
                    <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                      {item.metricValue}
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    {item.metricLabel} · {formatMaybeDate(item.updatedAt)}
                  </p>
                </Link>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)]">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Global Pulse</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">지금 체크할 매크로 캘린더</h2>
            <ul className="mt-4 space-y-3">
              {data.globalHighlights.map((item) => (
                <li key={item.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.whyItMattersKo}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {item.country} · {formatMaybeDate(item.updatedAt ?? item.eventTimeKst)}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </section>
    </div>
  );
}
