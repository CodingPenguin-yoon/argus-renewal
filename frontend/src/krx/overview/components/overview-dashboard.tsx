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

function driverToneClasses(index: number) {
  if (index === 0) return "border-amber-200 bg-amber-50 text-amber-800";
  if (index === 1) return "border-sky-200 bg-sky-50 text-sky-800";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export function OverviewDashboard({ data }: { data: OverviewTabData }) {
  const keyDrivers = data.keyTakeaways.slice(0, 3);
  const warningPoint = data.keyTakeaways[3] ?? data.keyTakeaways[data.keyTakeaways.length - 1] ?? null;
  const shortEvidence = data.reportLinks.slice(0, 3);
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:py-8">
      <section className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
        <article className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)] sm:p-7">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 pb-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Overview Desk</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-[2.1rem]">대시보드</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">지금 뭐가 중요한지 60초 안에 먼저 정리하는 cockpit입니다.</p>
            </div>
            <p className="text-xs text-slate-500">{formatMaybeDate(data.reportUpdatedAt)}</p>
          </div>

          <div className="mt-5 space-y-5">
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/90 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">지금 뭐가 중요하지?</p>
              <p className="mt-2 text-base leading-7 text-slate-800">{data.marketToneLine}</p>
            </div>

            {keyDrivers.length ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-slate-950">핵심 드라이버 3개</h2>
                  <span className="text-xs text-slate-500">30초 안에 먼저 볼 이유</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {keyDrivers.map((item, index) => (
                    <article key={`${index}-${item}`} className={`rounded-2xl border px-4 py-4 ${driverToneClasses(index)}`}>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">driver {index + 1}</p>
                      <p className="mt-3 text-sm leading-6">{item}</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

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
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">한 줄 브리프</h2>
                <span className="text-xs text-slate-500">허브 판단</span>
              </div>
              <p className="text-base leading-7 text-slate-700">{data.reportSummary}</p>
            </div>

            {warningPoint ? (
              <div className="rounded-2xl border border-rose-200/80 bg-rose-50/85 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-rose-900">경고 포인트</h3>
                  <span className="rounded-full border border-rose-200 bg-white/80 px-2.5 py-1 text-[11px] font-semibold text-rose-700">
                    체크 필요
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-rose-900/90">{warningPoint}</p>
              </div>
            ) : null}

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-950">짧은 근거 링크</h3>
                <span className="text-xs text-slate-500">상세 해석은 각 탭에서 이어집니다</span>
              </div>
              <ul className="space-y-3">
                {shortEvidence.map((item, index) => (
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
            <h2 className="mt-2 text-lg font-semibold text-slate-950">오늘 먼저 볼 탭</h2>
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
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Next Catalyst</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">다음 확인 포인트</h2>
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
