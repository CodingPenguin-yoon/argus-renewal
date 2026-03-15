import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { EmptyState } from "@/krx/components/ui/empty-state";
import { SectionHeader } from "@/krx/components/ui/section-header";
import {
  MARKET_SIGNAL_SUBTAB_OPTIONS,
  MarketSignalSubtabKey,
  marketSignalSubtabHref,
} from "@/krx/market-signal/lib/subtabs";
import { formatKoreanDate } from "@/krx/lib/utils";
import {
  DerivativesInvestorFlow,
  DerivativesSummary,
  DerivativesTrends,
  MarketSignalCard,
  MarketSignalSummary,
} from "@/krx/types/domain";

const SOURCE_NAME_LABELS: Record<string, string> = {
  KIS_MARKET_BREADTH: "KIS 수급",
  KIS_NIGHT_FUTURES: "KIS 야간선물",
  KIS_DOMESTIC_DERIVATIVES: "KIS 국내 파생",
  KRX_DERIVATIVES_REFERENCE: "KRX 파생 기준",
  MARKET_BRIEFINGS: "시장 브리핑",
};

function toneVariant(tone: MarketSignalCard["tone"]) {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  return "neutral";
}

function coverageVariant(state: MarketSignalCard["sourceCoverage"]["state"]) {
  if (state === "full") return "positive";
  if (state === "partial") return "high";
  return "low";
}

function freshnessLabel(value: string | null) {
  if (!value) return "기준 시각 없음";
  try {
    return `기준 ${formatKoreanDate(value)}`;
  } catch {
    return `기준 ${value}`;
  }
}

function formatNumber(value: number | null, fractionDigits: number = 0) {
  if (value === null || Number.isNaN(value)) return "-";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function formatSigned(value: number | null, fractionDigits: number = 0) {
  if (value === null || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, fractionDigits)}`;
}

function formatSignedPercent(value: number | null, fractionDigits: number = 2) {
  if (value === null || Number.isNaN(value)) return "-";
  return `${formatSigned(value, fractionDigits)}%`;
}

function formatLargeNumber(value: number | null) {
  if (value === null || Number.isNaN(value)) return "-";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) {
    return `${formatSigned(value / 1_000_000_000_000, 2)}조`;
  }
  if (abs >= 100_000_000) {
    return `${formatSigned(value / 100_000_000, 1)}억`;
  }
  if (abs >= 10_000) {
    return `${formatSigned(value / 10_000, 1)}만`;
  }
  return formatSigned(value, 0);
}

function directionalBiasLabel(value: DerivativesSummary["directionalBias"]) {
  if (value === "bullish") return "상방 우위";
  if (value === "bearish") return "하방 우위";
  return "중립";
}

function gapBiasLabel(value: DerivativesSummary["gapBias"]) {
  if (value === "gap_up") return "갭상승 가능성";
  if (value === "gap_down") return "갭하락 가능성";
  return "갭 중립";
}

function volatilityBiasLabel(value: DerivativesSummary["volatilityBias"]) {
  if (value === "rising") return "변동성 확대";
  if (value === "falling") return "변동성 완화";
  return "변동성 안정";
}

function confidenceBucketLabel(value: DerivativesSummary["confidenceBucket"]) {
  if (value === "high") return "높음";
  if (value === "medium") return "중간";
  return "낮음";
}

function detailLevelLabel(level: number) {
  if (level >= 3) return "상세";
  if (level >= 2) return "중간";
  if (level >= 1) return "기본";
  return "대기";
}

function dateLabel(value: string | null) {
  if (!value) return "거래일 정보 없음";
  return value;
}

function sourceNameLabel(value: string) {
  return SOURCE_NAME_LABELS[value] ?? value.replaceAll("_", " ");
}

function sourceLabels(sourceNames: string[], limit = sourceNames.length) {
  return Array.from(new Set(sourceNames.map(sourceNameLabel))).slice(0, limit);
}

function findCard(summary: MarketSignalSummary, key: MarketSignalCard["key"]) {
  return summary.cards.find((card) => card.key === key) ?? null;
}

function SourceBadgeRow({
  sourceNames,
  limit = 3,
}: {
  sourceNames: string[];
  limit?: number;
}) {
  const labels = sourceLabels(sourceNames, limit);
  if (!labels.length) return null;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="데이터 소스">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">데이터 소스</span>
      {labels.map((label) => (
        <Badge key={label} variant="neutral">
          {label}
        </Badge>
      ))}
    </div>
  );
}

function comparisonBadgeVariant(comparison: DerivativesSummary["sourceCoverage"]["comparisons"][number]) {
  if (comparison.status === "missing") return "low";
  if (comparison.mixedSource) return "high";
  return "positive";
}

function comparisonBadgeLabel(comparison: DerivativesSummary["sourceCoverage"]["comparisons"][number]) {
  if (comparison.status === "missing") return "비교 없음";
  if (comparison.mixedSource) return "혼합 소스";
  return "동일 소스";
}

function comparisonDescription(comparison: DerivativesSummary["sourceCoverage"]["comparisons"][number]) {
  if (comparison.status === "missing") {
    return "현재값 또는 전일값 소스가 비어 있어 변화율 계산 근거를 표시할 수 없습니다.";
  }

  const currentLabel = comparison.currentSourceName ? sourceNameLabel(comparison.currentSourceName) : "현재 소스 없음";
  const previousLabel = comparison.previousSourceName ? sourceNameLabel(comparison.previousSourceName) : "전일 소스 없음";

  if (!comparison.mixedSource && comparison.currentSourceName && comparison.currentSourceName === comparison.previousSourceName) {
    return `${currentLabel} 기준으로 현재값과 전일값을 연속 비교했습니다.`;
  }

  return `현재 ${currentLabel} / 전일 ${previousLabel} 기준으로 계산했습니다.`;
}

function DerivativesComparisonPanel({
  comparisons,
}: {
  comparisons: DerivativesSummary["sourceCoverage"]["comparisons"];
}) {
  if (!comparisons.length) return null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <SectionHeader
        title="변화율 계산 소스"
        description="전일 대비 숫자가 어떤 현재값/전일값 원천을 비교한 결과인지 함께 표시합니다."
      />
      <div className="grid gap-3 xl:grid-cols-3">
        {comparisons.map((comparison) => (
          <article key={comparison.key} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="neutral">{comparison.label}</Badge>
              <Badge variant={comparisonBadgeVariant(comparison)}>{comparisonBadgeLabel(comparison)}</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700">{comparisonDescription(comparison)}</p>
            {comparison.status === "available" ? (
              <p className="mt-2 text-xs text-slate-500">
                현재 {comparison.currentTradeDate ?? "-"} · 전일 {comparison.previousTradeDate ?? "-"}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function DerivativesOneLine({
  derivativesSummary,
  fallbackLine,
}: {
  derivativesSummary: DerivativesSummary;
  fallbackLine: string | null;
}) {
  const fallback = fallbackLine?.trim();
  const hasFallback = Boolean(fallback && fallback !== "데이터가 아직 준비되지 않았습니다.");
  const line = hasFallback
    ? fallback
    : `${directionalBiasLabel(derivativesSummary.directionalBias)} · ${gapBiasLabel(derivativesSummary.gapBias)} · ${volatilityBiasLabel(
        derivativesSummary.volatilityBias,
      )}`;

  return (
    <section className="rounded-[30px] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="high">파생 한줄 결론</Badge>
        <Badge variant="neutral">{dateLabel(derivativesSummary.date)}</Badge>
        <Badge variant={coverageVariant(derivativesSummary.sourceCoverage.state)}>
          {derivativesSummary.sourceCoverage.label}
        </Badge>
      </div>
      <h2 className="mt-4 text-2xl font-black tracking-tight text-slate-900">{line}</h2>
      <p className="mt-3 text-sm leading-7 text-slate-600">
        신뢰도 {confidenceBucketLabel(derivativesSummary.confidenceBucket)} · {freshnessLabel(derivativesSummary.lastUpdatedAt)}
      </p>
      <SourceBadgeRow sourceNames={derivativesSummary.sourceCoverage.sourceNames} />
    </section>
  );
}

function DerivativesMetricCard({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-black tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </article>
  );
}

type TrendPoint = { label: string; value: number | null };

function buildTrendPath(points: TrendPoint[]) {
  const values = points.map((point) => point.value).filter((value): value is number => value !== null);
  if (!values.length) {
    return { path: "", min: 0, max: 0 };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 300;
  const height = 120;
  const paddingX = 12;
  const paddingY = 12;
  const span = Math.max(max - min, 1e-9);
  const step = points.length > 1 ? (width - paddingX * 2) / (points.length - 1) : 0;

  const coordinates = points.map((point, index) => {
    const yValue = point.value ?? min;
    const x = paddingX + step * index;
    const ratio = (yValue - min) / span;
    const y = height - paddingY - ratio * (height - paddingY * 2);
    return { x, y, missing: point.value === null };
  });

  let path = "";
  coordinates.forEach((point, index) => {
    if (point.missing) return;
    if (!path) {
      path = `M ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
      return;
    }

    let prev = index - 1;
    while (prev >= 0 && coordinates[prev].missing) {
      prev -= 1;
    }
    if (prev === index - 1 && prev >= 0) {
      path += ` L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
      return;
    }
    path += ` M ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  });

  return { path, min, max };
}

function TrendChart({
  title,
  description,
  points,
  formatter,
  emptyDescription,
}: {
  title: string;
  description: string;
  points: TrendPoint[];
  formatter: (value: number | null) => string;
  emptyDescription: string;
}) {
  const hasValue = points.some((point) => point.value !== null);
  const { path, min, max } = buildTrendPath(points);
  const firstLabel = points[0]?.label ?? "-";
  const lastLabel = points[points.length - 1]?.label ?? "-";

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-extrabold tracking-tight text-slate-900">{title}</h3>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
      {hasValue ? (
        <>
          <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <svg viewBox="0 0 300 120" className="h-32 w-full" aria-hidden>
              <path d={path} fill="none" stroke="#0f172a" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
            <span>{firstLabel}</span>
            <span>
              {formatter(min)} ~ {formatter(max)}
            </span>
            <span>{lastLabel}</span>
          </div>
        </>
      ) : (
        <EmptyState title="추이 데이터를 아직 준비하지 못했습니다" description={emptyDescription} />
      )}
    </article>
  );
}

function DetailMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function DerivativesTabPanel({
  derivativesSummary,
  derivativesTrends,
  derivativesInvestorFlow,
  fallbackCard,
}: {
  derivativesSummary: DerivativesSummary;
  derivativesTrends: DerivativesTrends;
  derivativesInvestorFlow: DerivativesInvestorFlow;
  fallbackCard: MarketSignalCard | null;
}) {
  const pcrTrend = derivativesTrends.items.map((item) => ({
    label: item.date.slice(5),
    value: item.pcr,
  }));

  const flowTrend = derivativesInvestorFlow.items.map((item) => ({
    label: item.date.slice(5),
    value: item.futuresForeignNetBuy,
  }));
  const hasFlowSeries = flowTrend.some((item) => item.value !== null);
  const oiTrend = derivativesTrends.items.map((item) => ({
    label: item.date.slice(5),
    value: item.openInterestTotal,
  }));
  const secondaryTrend = hasFlowSeries ? flowTrend : oiTrend;

  const callOpenInterest = derivativesSummary.callOpenInterest;
  const putOpenInterest = derivativesSummary.putOpenInterest;
  const oiBalanceLabel =
    callOpenInterest !== null && putOpenInterest !== null
      ? `${formatNumber(callOpenInterest, 0)} vs ${formatNumber(putOpenInterest, 0)}`
      : "-";

  const explanationText = derivativesSummary.explanationText.trim()
    ? derivativesSummary.explanationText
    : `${dateLabel(derivativesSummary.date)} 파생 지표 기준으로 ${directionalBiasLabel(derivativesSummary.directionalBias)}로 해석했습니다.`;
  const hasPreOpenSession = derivativesSummary.preOpenFutures.changeRate !== null;
  const hasNightSession = derivativesSummary.nightFutures.changeRate !== null;
  const sessionMetricLabel = hasPreOpenSession
    ? "개장 전 선물 변동률"
    : hasNightSession
      ? "야간선물 변동률"
      : "내재변동성";
  const sessionMetricValue = hasPreOpenSession
    ? formatSignedPercent(derivativesSummary.preOpenFutures.changeRate, 2)
    : hasNightSession
      ? formatSignedPercent(derivativesSummary.nightFutures.changeRate, 2)
      : formatNumber(derivativesSummary.impliedVolatility, 2);
  const sessionMetricDetail = hasPreOpenSession
    ? "개장 전 세션 선물 움직임"
    : hasNightSession
      ? "야간 세션 선물 움직임"
      : `내재변동성 변화율 ${formatSignedPercent(derivativesSummary.impliedVolatilityChange, 2)}`;

  const componentLines = derivativesSummary.components
    .map((component) => component.explanationKo?.trim())
    .filter((line): line is string => Boolean(line))
    .slice(0, 3);

  return (
    <div className="flex flex-col gap-6" data-testid="market-signal-derivatives-panel">
      <DerivativesOneLine derivativesSummary={derivativesSummary} fallbackLine={fallbackCard?.interpretationLine ?? null} />

      <section>
        <SectionHeader
          title="핵심 파생 카드"
          description="파생 포지션의 방향성과 리스크 신호를 핵심 지표로 바로 확인합니다."
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <DerivativesMetricCard
            title="Put/Call Ratio"
            value={formatNumber(derivativesSummary.pcr, 2)}
            detail={`전일 대비 ${formatSignedPercent(derivativesSummary.pcrChange, 2)}`}
          />
          <DerivativesMetricCard
            title="Call OI vs Put OI"
            value={oiBalanceLabel}
            detail={`미결제약정 변화율 ${formatSignedPercent(derivativesSummary.oiChange, 2)}`}
          />
          <DerivativesMetricCard
            title="외국인 선물 포지션"
            value={formatLargeNumber(derivativesSummary.foreignFuturesNetPosition)}
            detail="선물 순매수/순매도 강도"
          />
          <DerivativesMetricCard
            title={sessionMetricLabel}
            value={sessionMetricValue}
            detail={sessionMetricDetail}
          />
        </div>
      </section>

      <DerivativesComparisonPanel comparisons={derivativesSummary.sourceCoverage.comparisons} />

      <section>
        <SectionHeader
          title="추이 차트"
          description="최근 세션 흐름에서 방향성의 연속성과 반전 구간을 확인합니다."
        />
        <div className="grid gap-4 xl:grid-cols-2">
          <TrendChart
            title={`최근 ${derivativesTrends.items.length || 20}일 Put/Call Ratio 추이`}
            description="숫자 자체보다 추세의 기울기와 속도 변화에 집중합니다."
            points={pcrTrend}
            formatter={(value) => formatNumber(value, 2)}
            emptyDescription="Put/Call Ratio가 수집되면 자동으로 추세가 표시됩니다."
          />
          <TrendChart
            title={
              hasFlowSeries
                ? `최근 ${derivativesInvestorFlow.items.length || 20}일 외국인 선물 흐름 추이`
                : `최근 ${derivativesTrends.items.length || 20}일 미결제약정 추이`
            }
            description={
              hasFlowSeries
                ? "외국인 선물 포지션 변화로 수급 방향성을 확인합니다."
                : "외국인 흐름이 비어 있는 경우 OI 총량 추이를 대체로 제공합니다."
            }
            points={secondaryTrend}
            formatter={hasFlowSeries ? (value) => formatLargeNumber(value) : (value) => formatNumber(value, 0)}
            emptyDescription="파생 추이 데이터가 준비되면 이 영역이 채워집니다."
          />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <SectionHeader
          title="세부 지표"
          description="당일 파생 핵심 지표를 한 화면에서 요약해 확인할 수 있습니다."
        />
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <DetailMetric label="거래일" value={dateLabel(derivativesSummary.date)} />
          <DetailMetric label="데이터 커버리지" value={derivativesSummary.sourceCoverage.label} />
          <DetailMetric label="디테일 레벨" value={detailLevelLabel(derivativesSummary.detailLevel)} />
          <DetailMetric label="신뢰도" value={confidenceBucketLabel(derivativesSummary.confidenceBucket)} />
          <DetailMetric label="Put/Call Ratio" value={formatNumber(derivativesSummary.pcr, 2)} />
          <DetailMetric label="PCR 변화율" value={formatSignedPercent(derivativesSummary.pcrChange, 2)} />
          <DetailMetric label="Call OI" value={formatNumber(derivativesSummary.callOpenInterest, 0)} />
          <DetailMetric label="Put OI" value={formatNumber(derivativesSummary.putOpenInterest, 0)} />
          <DetailMetric label="외국인 선물 포지션" value={formatLargeNumber(derivativesSummary.foreignFuturesNetPosition)} />
          <DetailMetric label={sessionMetricLabel} value={sessionMetricValue} />
          <DetailMetric label="내재변동성" value={formatNumber(derivativesSummary.impliedVolatility, 2)} />
          <DetailMetric label="내재변동성 변화율" value={formatSignedPercent(derivativesSummary.impliedVolatilityChange, 2)} />
        </dl>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <SectionHeader
          title="해설"
          description="결정적 규칙 기반 또는 기존 브리핑 설명을 그대로 제공하며, 투자 결과를 단정하지 않습니다."
        />
        <p className="text-sm leading-7 text-slate-700">{explanationText}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
          <Badge variant="default">
            해설 출처 {derivativesSummary.briefingSource === "market_briefings" ? "MARKET_BRIEFINGS" : "DETERMINISTIC_RULES"}
          </Badge>
          <Badge variant="neutral">최종 기준 {freshnessLabel(derivativesSummary.lastUpdatedAt)}</Badge>
        </div>
        {componentLines.length ? (
          <ul className="mt-4 grid gap-2 text-sm text-slate-700">
            {componentLines.map((line) => (
              <li key={line} className="rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2">
                {line}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

function SignalCard({ card }: { card: MarketSignalCard }) {
  return (
    <article className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={toneVariant(card.tone)}>{card.title}</Badge>
        {card.trendBadge ? <Badge variant={toneVariant(card.trendBadge.tone)}>{card.trendBadge.label}</Badge> : null}
        <Badge variant={coverageVariant(card.sourceCoverage.state)}>{card.sourceCoverage.label}</Badge>
      </div>
      <p className="mt-4 text-lg font-black tracking-tight text-slate-900">{card.interpretationLine}</p>
      {card.detailText ? <p className="mt-3 text-sm leading-6 text-slate-600">{card.detailText}</p> : null}
      <SourceBadgeRow sourceNames={card.sourceCoverage.sourceNames} />
      <dl className="mt-5 grid gap-3 sm:grid-cols-3">
        {card.supportingMetrics.slice(0, 3).map((metric) => (
          <div key={metric.key} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{metric.label}</dt>
            <dd className="mt-2 text-xl font-black text-slate-900">{metric.formattedValue}</dd>
            <p className="mt-2 text-xs text-slate-500">{metric.provenance.sourceName ?? "소스 없음"}</p>
          </div>
        ))}
      </dl>
    </article>
  );
}

function subtabDescription(tab: MarketSignalSubtabKey) {
  if (tab === "summary") return "오늘 시장 결론, 자금 흐름, 파생상품, 체크포인트를 한 번에 요약합니다.";
  if (tab === "fund-flow") return "외국인·기관·프로그램 수급 중심으로 당일 자금 방향을 확인합니다.";
  if (tab === "derivatives") return "파생 포지션과 변동성 지표를 핵심 카드와 추이 차트로 제공합니다.";
  if (tab === "checkpoints") return "개장 전/장중 확인해야 할 리스크 체크포인트를 정리합니다.";
  return "";
}

function OverviewCard({
  title,
  description,
  tab,
}: {
  title: string;
  description: string;
  tab: MarketSignalSubtabKey;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-800">{description}</p>
      {tab !== "summary" ? (
        <Link
          href={marketSignalSubtabHref(tab)}
          className="mt-3 inline-flex rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
        >
          해당 탭 보기
        </Link>
      ) : null}
    </article>
  );
}

export function MarketSignalDashboard({
  summary,
  derivativesSummary,
  derivativesTrends,
  derivativesInvestorFlow,
  activeSubtab,
}: {
  summary: MarketSignalSummary;
  derivativesSummary: DerivativesSummary;
  derivativesTrends: DerivativesTrends;
  derivativesInvestorFlow: DerivativesInvestorFlow;
  activeSubtab: MarketSignalSubtabKey;
}) {
  const todayCard = findCard(summary, "today_conclusion");
  const fundFlowCard = findCard(summary, "fund_flow");
  const derivativesCard = findCard(summary, "futures_options");
  const checkpointsCard = findCard(summary, "checkpoints");
  const derivativesSummaryLine = `${directionalBiasLabel(derivativesSummary.directionalBias)} · ${gapBiasLabel(derivativesSummary.gapBias)} · ${volatilityBiasLabel(
    derivativesSummary.volatilityBias,
  )}`;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-6 md:py-8">
      <section className="rounded-[32px] border border-slate-200 bg-[linear-gradient(140deg,rgba(255,255,255,0.98),rgba(241,245,249,0.94))] p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-slate-900">시장 신호</h1>
            <p className="mt-1 text-sm text-slate-600">{subtabDescription(activeSubtab)}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={coverageVariant(summary.sourceCoverage.state)}>{summary.sourceCoverage.label}</Badge>
            <Badge variant="neutral">{freshnessLabel(summary.lastUpdatedAt)}</Badge>
          </div>
        </div>
        <nav className="mt-4 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="시장 신호 세부 탭" data-testid="market-signal-subtabs">
          {MARKET_SIGNAL_SUBTAB_OPTIONS.map((option) => {
            const active = option.key === activeSubtab;
            return (
              <Link
                key={option.key}
                href={marketSignalSubtabHref(option.key)}
                role="tab"
                aria-selected={active}
                className={`rounded-full border px-3 py-1.5 text-sm font-semibold whitespace-nowrap transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
                  active
                    ? "border-amber-500 bg-amber-400 text-slate-950 shadow-sm"
                    : "border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50"
                }`}
              >
                {option.label}
              </Link>
            );
          })}
        </nav>
      </section>

      {activeSubtab === "summary" ? (
        <>
          <section className="rounded-[32px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.18),_transparent_34%),linear-gradient(180deg,#fffdf7_0%,#ffffff_100%)] p-6 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="high">종합</Badge>
              <Badge variant={coverageVariant(summary.sourceCoverage.state)}>{summary.sourceCoverage.label}</Badge>
              <Badge variant="neutral">{freshnessLabel(summary.lastUpdatedAt)}</Badge>
            </div>
            <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-900">{summary.interpretationLine}</h2>
            <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-600">{summary.explanationText}</p>
            <SourceBadgeRow sourceNames={summary.sourceCoverage.sourceNames} />
          </section>
          <section className="grid gap-4 xl:grid-cols-2" data-testid="market-signal-summary-grid">
            <OverviewCard
              title="오늘 시장 결론"
              description={todayCard?.interpretationLine ?? summary.interpretationLine}
              tab="summary"
            />
            <OverviewCard
              title="자금 흐름 요약"
              description={fundFlowCard?.interpretationLine ?? "외국인·기관 수급 데이터가 준비되면 이 영역에 표시됩니다."}
              tab="fund-flow"
            />
            <OverviewCard
              title="파생상품 요약"
              description={derivativesCard?.interpretationLine ?? derivativesSummaryLine}
              tab="derivatives"
            />
            <OverviewCard
              title="오늘 체크포인트 요약"
              description={checkpointsCard?.interpretationLine ?? "개장 전 확인할 리스크 항목이 준비되면 이 영역에 표시됩니다."}
              tab="checkpoints"
            />
          </section>
        </>
      ) : null}

      {activeSubtab === "fund-flow" ? (
        fundFlowCard ? (
          <SignalCard card={fundFlowCard} />
        ) : (
          <EmptyState
            title="자금 흐름 데이터를 아직 준비하지 못했습니다"
            description="외국인·기관 수급이 수집되면 자금 흐름 카드가 표시됩니다."
          />
        )
      ) : null}

      {activeSubtab === "derivatives" ? (
        <DerivativesTabPanel
          derivativesSummary={derivativesSummary}
          derivativesTrends={derivativesTrends}
          derivativesInvestorFlow={derivativesInvestorFlow}
          fallbackCard={derivativesCard}
        />
      ) : null}

      {activeSubtab === "checkpoints" ? (
        checkpointsCard ? (
          <SignalCard card={checkpointsCard} />
        ) : (
          <EmptyState
            title="체크포인트를 아직 만들지 못했습니다"
            description="당일 변동성 경계 구간이 계산되면 체크포인트 카드가 표시됩니다."
          />
        )
      ) : null}
    </div>
  );
}
