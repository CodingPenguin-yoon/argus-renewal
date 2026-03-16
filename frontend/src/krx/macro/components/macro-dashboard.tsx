import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { formatKoreanDate } from "@/krx/lib/utils";
import type { AppHeader, MacroTabData } from "@/krx/types/domain";

function formatMaybeDate(value: string | null) {
  return value ? formatKoreanDate(value) : "업데이트 대기";
}

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

function toneClasses(tone: "positive" | "neutral" | "negative") {
  if (tone === "positive") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (tone === "negative") return "border-rose-200 bg-rose-50 text-rose-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function clampGaugeValue(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function sentimentGauge(headerData: AppHeader, derivativesSummary: MacroTabData["derivativesSummary"]) {
  const base =
    derivativesSummary.directionalBias === "bullish"
      ? 72
      : derivativesSummary.directionalBias === "bearish"
        ? 32
        : 52;
  const supportBoost = Math.min(headerData.supportingPoints.length * 4, 12);
  const coverageBoost = Math.round(headerData.sourceCoverage.coverageRatio * 10);

  return {
    label: "시장 심리",
    value: clampGaugeValue(base + supportBoost + coverageBoost - 10),
    state:
      derivativesSummary.directionalBias === "bullish"
        ? "상방 우위"
        : derivativesSummary.directionalBias === "bearish"
          ? "하방 경계"
          : "중립",
    description:
      derivativesSummary.directionalBias === "bullish"
        ? "파생 기준점과 공통 해석이 함께 버티는 구간입니다."
        : derivativesSummary.directionalBias === "bearish"
          ? "방향성보다 방어 시그널을 먼저 확인해야 합니다."
          : "명확한 추세보다 확인 신호가 더 필요합니다.",
  };
}

function volatilityGauge(derivativesSummary: MacroTabData["derivativesSummary"]) {
  const base =
    derivativesSummary.volatilityBias === "rising"
      ? 76
      : derivativesSummary.volatilityBias === "falling"
        ? 38
        : 52;
  const ivChange = derivativesSummary.impliedVolatilityChange ?? 0;

  return {
    label: "변동성 온도",
    value: clampGaugeValue(base + ivChange * 6),
    state:
      derivativesSummary.volatilityBias === "rising"
        ? "가열"
        : derivativesSummary.volatilityBias === "falling"
          ? "완화"
          : "안정",
    description:
      derivativesSummary.volatilityBias === "rising"
        ? "장중 흔들림이 커질 수 있어 추격보다 확인이 중요합니다."
        : derivativesSummary.volatilityBias === "falling"
          ? "불안이 다소 진정되며 가격 해석이 쉬워지는 구간입니다."
          : "아직 급격한 리스크 확대 신호는 제한적입니다.",
  };
}

function confidenceGauge(headerData: AppHeader, derivativesSummary: MacroTabData["derivativesSummary"]) {
  const base =
    derivativesSummary.confidenceBucket === "high"
      ? 80
      : derivativesSummary.confidenceBucket === "medium"
        ? 58
        : 36;
  const coverageBoost = Math.round(headerData.sourceCoverage.coverageRatio * 12);

  return {
    label: "AI 확신도",
    value: clampGaugeValue(base + coverageBoost - 6),
    state:
      derivativesSummary.confidenceBucket === "high"
        ? "높음"
        : derivativesSummary.confidenceBucket === "medium"
          ? "보통"
          : "낮음",
    description:
      derivativesSummary.confidenceBucket === "high"
        ? "소스 정합성이 높아 오늘 해석을 빠르게 따라가도 되는 편입니다."
        : derivativesSummary.confidenceBucket === "medium"
          ? "핵심 방향은 읽히지만 장중 확인 포인트가 남아 있습니다."
          : "데이터 커버리지 또는 시그널 정합성이 아직 약합니다.",
  };
}

function gaugeAccent(value: number) {
  if (value >= 70) return "from-emerald-300 via-emerald-400 to-lime-300";
  if (value >= 45) return "from-amber-200 via-amber-300 to-orange-300";
  return "from-rose-300 via-rose-400 to-red-300";
}

function counterpointLines(data: MacroTabData) {
  const lines = data.referenceCards
    .filter((item) => item.tone !== "positive")
    .map((item) => `${item.label}: ${item.summary}`);

  if (!lines.length && data.derivativesSummary.explanationText.trim()) {
    lines.push(data.derivativesSummary.explanationText.trim());
  }

  return lines.slice(0, 2);
}

function triggerLines(data: MacroTabData) {
  const lines: string[] = [];
  const riskCard = data.referenceCards.find((item) => item.tone === "negative");

  if (riskCard) {
    lines.push(`${riskCard.label} 신호가 더 악화되면 현재 해석 강도를 낮춰야 합니다.`);
  }
  if (data.derivativesSummary.volatilityBias === "rising") {
    lines.push("변동성 가열이 이어지면 추세 판단보다 확인 신호를 우선해야 합니다.");
  }
  if (!lines.length) {
    lines.push("환율, 금리, 파생 방향이 동시에 꺾이면 현재 해석을 다시 점검해야 합니다.");
  }

  return lines.slice(0, 2);
}

export function MacroDashboard({
  data,
  headerData,
}: {
  data: MacroTabData;
  headerData: AppHeader;
}) {
  const gauges = [
    sentimentGauge(headerData, data.derivativesSummary),
    volatilityGauge(data.derivativesSummary),
    confidenceGauge(headerData, data.derivativesSummary),
  ];
  const evidenceLines = headerData.supportingPoints.slice(0, 3);
  const counterLines = counterpointLines(data);
  const triggerItems = triggerLines(data);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:py-8">
      <section className="relative overflow-hidden rounded-[28px] border border-slate-200/80 bg-[linear-gradient(145deg,#0f172a,#172554_52%,#1d4ed8)] p-6 text-slate-100 shadow-[0_28px_80px_-44px_rgba(15,23,42,0.72)] sm:p-7">
        <div className="pointer-events-none absolute -right-8 top-0 h-36 w-36 rounded-full bg-sky-300/18 blur-3xl" />
        <div className="pointer-events-none absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-amber-300/12 blur-3xl" />
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-100/80">AI Insight Desk</p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">AI 인사이트</h1>
            <p className="max-w-3xl text-base leading-7 text-slate-200">
              공통 해석 톤과 파생 맥락, 거시 참고 신호를 한 화면에서 묶어 오늘 시장의 방향과 리스크를 빠르게 읽는 탭입니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="high">{phaseLabel(headerData.phase)}</Badge>
            <Badge variant={coverageVariant(headerData.sourceCoverage.state)}>
              소스 {headerData.sourceCoverage.availableSources}/{headerData.sourceCoverage.expectedSources}
            </Badge>
            <Badge>업데이트 {formatMaybeDate(headerData.updatedAt ?? data.updatedAt)}</Badge>
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
          <article className="rounded-[24px] border border-white/10 bg-white/8 p-5 backdrop-blur-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-100/80">주장</p>
            <h2 className="mt-3 text-2xl font-black tracking-tight text-white">오늘의 해석</h2>
            <p className="mt-4 text-base leading-8 text-slate-100">
              {headerData.marketToneLine || "시장 해석 문장이 아직 준비되지 않았습니다."}
            </p>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <section className="rounded-2xl border border-white/10 bg-slate-950/22 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-100/70">근거</p>
                {evidenceLines.length ? (
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-100">
                    {evidenceLines.map((point) => (
                      <li key={`${point.sourceKey}-${point.text}`} className="rounded-xl border border-white/10 bg-white/6 px-3 py-2">
                        {point.text}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm leading-6 text-slate-200">아직 공개할 근거 라인이 충분하지 않습니다.</p>
                )}
              </section>

              <section className="rounded-2xl border border-white/10 bg-slate-950/22 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-100/70">반대 근거</p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-100">
                  {counterLines.map((line) => (
                    <li key={line} className="rounded-xl border border-white/10 bg-white/6 px-3 py-2">
                      {line}
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/25 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-100/70">해석이 바뀌는 조건</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-100">
                {triggerItems.map((line) => (
                  <li key={line} className="rounded-xl border border-white/10 bg-white/6 px-3 py-2">
                    {line}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/25 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-100/70">소스 커버리지</p>
              <p className="mt-2 text-sm leading-6 text-slate-200">{headerData.sourceCoverage.summary}</p>
              {headerData.sourceCoverage.items.length ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {headerData.sourceCoverage.items.map((item) => (
                    <span key={item.key} className="rounded-full border border-white/10 bg-white/7 px-2.5 py-1 text-slate-100">
                      {item.label} · {coverageStatusLabel(item.status)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </article>

          <div className="space-y-4">
            <section className="rounded-[24px] border border-white/10 bg-white/8 p-5 backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-100/80">AI 계기판</p>
              <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">AI 계기판</h2>
              <div className="mt-4 space-y-3">
                {gauges.map((gauge) => (
                  <article key={gauge.label} className="rounded-2xl border border-white/10 bg-slate-950/22 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-white">{gauge.label}</h3>
                        <p className="mt-1 text-xs text-slate-300">{gauge.description}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-xl font-black text-white">{gauge.value}</p>
                        <p className="text-[11px] font-semibold text-sky-100/75">{gauge.state}</p>
                      </div>
                    </div>
                    <div
                      className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/10"
                      role="progressbar"
                      aria-label={gauge.label}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={gauge.value}
                      aria-valuetext={gauge.state}
                    >
                      <div className={`h-full rounded-full bg-gradient-to-r ${gaugeAccent(gauge.value)}`} style={{ width: `${gauge.value}%` }} />
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="rounded-[24px] border border-white/10 bg-white/8 p-5 backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-100/80">파생 해석</p>
              <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">파생 기준점</h2>
              <p className="mt-3 text-sm leading-7 text-slate-200">{data.derivativesSummary.explanationText}</p>
            </section>

            <section className="rounded-[24px] border border-white/10 bg-white/8 p-5 backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-100/80">참고 카드</p>
              <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">거시 참고 카드</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {data.referenceCards.map((item) => (
                  <article key={item.key} className="rounded-2xl border border-white/10 bg-slate-950/20 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-white">{item.label}</h3>
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses(item.tone)}`}>
                        {item.tone === "positive" ? "우호" : item.tone === "negative" ? "경계" : "중립"}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-200">{item.summary}</p>
                    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-300">
                      <span>{item.sourceLabel}</span>
                      <span>{formatMaybeDate(item.updatedAt)}</span>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>
        </div>
      </section>

      <section className="rounded-[28px] border border-slate-200/80 bg-[linear-gradient(140deg,rgba(255,255,255,0.98),rgba(241,245,249,0.94)_55%,rgba(191,219,254,0.24))] p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">거시 체크</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">거시 체크리스트</h2>
            <p className="max-w-3xl text-base leading-7 text-slate-700">
              환율, 원유, 금리, 지정학, 파생 흐름을 기준점으로 빠르게 훑는 참고 섹션입니다.
            </p>
          </div>
          <div className="inline-flex w-fit rounded-full border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-600 shadow-sm">
            기준 {formatMaybeDate(data.updatedAt)}
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {data.referenceCards.map((item) => (
            <article key={item.key} className="rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-950">{item.label}</h2>
                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneClasses(item.tone)}`}>
                  {item.tone === "positive" ? "우호" : item.tone === "negative" ? "경계" : "중립"}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">{item.summary}</p>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
                <span>{item.sourceLabel}</span>
                <span>{formatMaybeDate(item.updatedAt)}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
        <article className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)]">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 pb-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Derivatives Snapshot</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">파생 기준점</h2>
            </div>
            <p className="text-xs text-slate-500">{formatMaybeDate(data.derivativesSummary.lastUpdatedAt)}</p>
          </div>

          <p className="mt-5 text-base leading-8 text-slate-700">{data.derivativesSummary.explanationText}</p>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">PCR</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">
                {data.derivativesSummary.pcr !== null ? data.derivativesSummary.pcr.toFixed(2) : "-"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">야간 선물</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">
                {data.derivativesSummary.nightFutures.changeRate !== null
                  ? `${data.derivativesSummary.nightFutures.changeRate.toFixed(2)}%`
                  : "-"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">IV</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">
                {data.derivativesSummary.impliedVolatility !== null
                  ? data.derivativesSummary.impliedVolatility.toFixed(1)
                  : "-"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">외국인 선물</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">
                {data.derivativesSummary.foreignFuturesNetPosition !== null
                  ? data.derivativesSummary.foreignFuturesNetPosition.toLocaleString("ko-KR")
                  : "-"}
              </p>
            </div>
          </div>
        </article>

        <div className="space-y-6">
          <section className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)]">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">최근 매크로</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">최근 매크로 뉴스</h2>
            <ul className="mt-4 space-y-3">
              {data.macroNews.map((item) => (
                <li key={item.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                      {item.category}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.whyItMatters}</p>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
                    <span>{item.source}</span>
                    <span>{formatMaybeDate(item.publishedAt)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-[28px] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_70px_-50px_rgba(15,23,42,0.45)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">연결 흐름</p>
                <h2 className="mt-2 text-xl font-semibold text-slate-950">매크로 캘린더 연결</h2>
              </div>
              <Link href="/krx/macro-calendar" className="text-sm font-semibold text-amber-700">
                매크로 캘린더 보기
              </Link>
            </div>
            <ul className="mt-4 space-y-3">
              {data.globalHighlights.map((item) => (
                <li key={item.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/85 px-4 py-4">
                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.whyItMattersKo}</p>
                  <p className="mt-3 text-xs text-slate-500">
                    {item.country} · {item.source.name} · {formatMaybeDate(item.updatedAt ?? item.eventTimeKst)}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </section>
    </div>
  );
}
