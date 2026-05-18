import Link from "next/link";
import type { ReactNode } from "react";

import type { DataPoint, FuturesQuoteResponse, MarketDashboard, NewsFeedResponse, OptionQuoteRow, OptionQuotesResponse } from "@/argus_v2/contracts/dashboard";
import { OptionQuotesTable } from "@/argus_v2/components/option-quotes-table";

type Tone = "positive" | "neutral" | "negative";
type ArgusTab = "judgement" | "derivatives" | "reaction" | "triggers";
type DerivativesAnalysisTab = "main" | "futures" | "option-quotes" | "option-layer" | "positions";
type NewsAnalysisTab = "main" | "news";

const ARGUS_TABS: Array<{ key: ArgusTab; label: string; href: string; description: string }> = [
  { key: "judgement", label: "시장 판단", href: "/argus", description: "결론과 근거" },
  { key: "derivatives", label: "옵션·선물", href: "/argus/derivatives", description: "포지셔닝" },
  { key: "reaction", label: "현물 반응", href: "/argus/reaction", description: "검증" },
  { key: "triggers", label: "뉴스 분석", href: "/argus/triggers", description: "트리거·피드" },
];

const NEWS_ANALYSIS_TABS: Array<{ key: NewsAnalysisTab; label: string; href: string; description: string }> = [
  { key: "main", label: "메인", href: "/argus/triggers", description: "시장 판단 연결" },
  { key: "news", label: "뉴스", href: "/argus/triggers/news", description: "실시간 원천 피드" },
];

const DERIVATIVES_ANALYSIS_TABS: Array<{ key: DerivativesAnalysisTab; label: string; href: string; description: string }> = [
  { key: "main", label: "메인", href: "/argus/derivatives", description: "옵션·선물 핵심" },
  { key: "futures", label: "선물", href: "/argus/derivatives/futures", description: "KOSPI200 근월" },
  { key: "option-quotes", label: "옵션 시세표", href: "/argus/derivatives/option-quotes", description: "HTS형 체인" },
  { key: "option-layer", label: "풋콜 레이어", href: "/argus/derivatives/option-layer", description: "콜·풋 압력" },
  { key: "positions", label: "포지션", href: "/argus/derivatives/positions", description: "주체별 수급" },
];

function formatValue(point: DataPoint, fractionDigits = 2) {
  if (point.value === null) return "미수신";
  if (typeof point.value === "string") return point.value;
  return point.value.toLocaleString("ko-KR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function formatPoint(point: DataPoint, fractionDigits = 2) {
  const value = formatValue(point, fractionDigits);
  if (point.value === null || point.unit === "count") return value;
  if (point.unit === "pct") return `${value}%`;
  if (point.unit === "pt") return `${value}pt`;
  if (point.unit === "KRW" && typeof point.value === "number") return formatKrw(point.value);
  return value;
}

function formatPercentValue(value: number | null | undefined) {
  if (typeof value !== "number") return "미수신";
  return `${value.toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function formatQuoteValue(value: number | null | undefined, fractionDigits = 2) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  });
}

function formatNullableValue(value: number | null | undefined, fractionDigits = 2) {
  if (typeof value !== "number") return "미수신";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  });
}

function formatNullableWithSuffix(value: number | null | undefined, suffix: string, fractionDigits = 2) {
  const formatted = formatNullableValue(value, fractionDigits);
  return typeof value === "number" ? `${formatted}${suffix}` : formatted;
}

function formatStrike(value: number | null) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: value % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

function formatKrw(value: number) {
  const absValue = Math.abs(value);
  if (absValue >= 100_000_000) {
    return `${(value / 100_000_000).toLocaleString("ko-KR", {
      maximumFractionDigits: 1,
    })}억원`;
  }
  if (absValue >= 10_000) {
    return `${(value / 10_000).toLocaleString("ko-KR", {
      maximumFractionDigits: 0,
    })}만원`;
  }
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`;
}

function formatDateTime(value: string | null) {
  if (!value) return "시간 미수신";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(date);
}

function freshnessLabel(value: MarketDashboard["provider_health"][number]["status"]) {
  if (value === "fresh") return "정상";
  if (value === "partial") return "부분";
  if (value === "stale") return "지연";
  return "미수신";
}

function confidenceLabel(value: MarketDashboard["judgement"]["confidence"]) {
  if (value === "high") return "확신도 높음";
  if (value === "medium") return "확신도 보통";
  return "확신도 낮음";
}

function triggerConfidenceLabel(value: MarketDashboard["triggers"][number]["ai_confidence"]) {
  if (value === "high") return "AI 확신 높음";
  if (value === "medium") return "AI 확신 보통";
  if (value === "low") return "AI 확신 낮음";
  return "AI 확신 미수신";
}

function toneClass(value: Tone) {
  if (value === "positive") return "argus-red";
  if (value === "negative") return "argus-blue";
  return "text-[#181816]/70";
}

function pointTone(point: DataPoint): Tone {
  if (typeof point.value !== "number") return "neutral";
  if (point.value > 0) return "positive";
  if (point.value < 0) return "negative";
  return "neutral";
}

function valueTone(value: number | null | undefined): Tone {
  if (typeof value !== "number") return "neutral";
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

function optionPressureTone(value: MarketDashboard["derivatives"]["option_pressure"]): Tone {
  if (value === "CALL") return "positive";
  if (value === "PUT") return "negative";
  return "neutral";
}

function MetricCard({ label, point, tone, fractionDigits = 2 }: { label: string; point: DataPoint; tone?: Tone; fractionDigits?: number }) {
  return (
    <div className="argus-tile px-4 py-3">
      <p className="argus-label">{label}</p>
      <p className={`mt-2 text-2xl font-black tracking-tight ${toneClass(tone ?? pointTone(point))}`}>{formatPoint(point, fractionDigits)}</p>
      <p className="mt-1 text-xs font-bold text-[#181816]/48">{point.source}</p>
    </div>
  );
}

function SignalTile({ label, value, caption, tone = "neutral" }: { label: string; value: string; caption: string; tone?: Tone }) {
  return (
    <div className="argus-tile px-4 py-3">
      <p className="argus-label">{label}</p>
      <p className={`mt-2 text-xl font-black tracking-tight ${toneClass(tone)}`}>{value}</p>
      <p className="mt-1 text-xs font-bold leading-4 text-[#181816]/48">{caption}</p>
    </div>
  );
}

function EmptyNote({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-dashed border-[#181816]/20 bg-[#f5f2e8] px-4 py-3">
      <p className="text-sm font-black">{title}</p>
      <p className="mt-1 text-xs font-bold leading-5 text-[#181816]/52">{body}</p>
    </div>
  );
}

function SectionTitle({ eyebrow, title, right }: { eyebrow: string; title: string; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="argus-label">{eyebrow}</p>
        <h2 className="mt-1 text-2xl font-black tracking-tight">{title}</h2>
      </div>
      {right}
    </div>
  );
}

function ArgusShell({ data, activeTab, children }: { data: MarketDashboard; activeTab: ArgusTab; children: ReactNode }) {
  return (
    <main className="market-shell market-shell-argus min-h-screen text-[#181816]">
      <div className="mx-auto max-w-[1600px] px-5 py-5">
        <header className="argus-frame animate-market-rise overflow-hidden">
          <div className="grid gap-5 border-b border-[#181816]/16 bg-[#fffdf7]/80 px-5 py-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <div>
              <p className="argus-label">Argus v2 market cockpit</p>
              <div className="mt-2 flex flex-wrap items-end gap-3">
                <h1 className="text-4xl font-black tracking-[-0.06em] md:text-6xl">{data.judgement.label}</h1>
                <span className="mb-2 border border-[#181816]/18 bg-white px-3 py-1 text-xs font-black">
                  {confidenceLabel(data.judgement.confidence)}
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs font-black lg:min-w-72">
              <span className="border border-[#181816]/16 bg-white px-3 py-2">신뢰도 {freshnessLabel(data.judgement.data_reliability)}</span>
              <span className="border border-[#181816]/16 bg-white px-3 py-2">as of {data.as_of}</span>
            </div>
          </div>

          <nav aria-label="Argus v2 tabs" className="grid border-b border-[#181816]/16 bg-[#f6f3e9]/88 md:grid-cols-4">
            {ARGUS_TABS.map((tab) => {
              const isActive = tab.key === activeTab;
              return (
                <Link
                  key={tab.key}
                  href={tab.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`border-b border-r border-[#181816]/12 px-4 py-3 transition hover:bg-white md:border-b-0 ${isActive ? "bg-[#181816] text-[#fffdf7]" : "bg-transparent"}`}
                >
                  <p className="text-sm font-black">{tab.label}</p>
                  <p className={`mt-1 text-[11px] font-bold ${isActive ? "text-[#fffdf7]/62" : "text-[#181816]/44"}`}>{tab.description}</p>
                </Link>
              );
            })}
          </nav>

          <div className="grid gap-5 bg-[#fffdf7]/72 px-5 py-5 lg:grid-cols-[1.25fr_0.75fr]">
            <p className="text-xl font-black leading-8 md:text-2xl">{data.judgement.summary}</p>
            <div className="border-l border-[#181816]/14 pl-4">
              <p className="argus-label">Primary Driver</p>
              <p className="mt-2 text-lg font-black">{data.judgement.primary_driver}</p>
            </div>
          </div>
        </header>

        <div className="mt-4">{children}</div>

        <section className="argus-frame mt-4 p-5">
          <SectionTitle eyebrow="Status" title="데이터 수신 상태" />
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {data.provider_health.map((provider) => (
              <div key={provider.key} className="argus-tile px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-black">{provider.label}</p>
                  <span className="text-xs font-black">{freshnessLabel(provider.status)}</span>
                </div>
                <p className="mt-1 text-xs font-bold text-[#181816]/48">
                  {provider.error ?? providerHealthDetail(provider)}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

function providerHealthDetail(provider: MarketDashboard["provider_health"][number]) {
  const parts = [`${provider.observed_count}건 수신`];
  if (provider.state) {
    parts.push(provider.state);
  }
  if (provider.next_scheduled_run) {
    parts.push(`다음 ${formatDateTime(provider.next_scheduled_run)}`);
  }
  return parts.join(" · ");
}

export function ArgusV2Dashboard({ data }: { data: MarketDashboard }) {
  return (
    <ArgusShell data={data} activeTab="judgement">
      <MarketJudgementPanel data={data} />
    </ArgusShell>
  );
}

export function ArgusV2DerivativesView({ data }: { data: MarketDashboard }) {
  return (
    <ArgusShell data={data} activeTab="derivatives">
      <DerivativesAnalysisLayout activeSubtab="main">
        <DerivativesPanel data={data} detail />
      </DerivativesAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2OptionQuotesView({ data, optionQuotes }: { data: MarketDashboard; optionQuotes: OptionQuotesResponse }) {
  return (
    <ArgusShell data={data} activeTab="derivatives">
      <DerivativesAnalysisLayout activeSubtab="option-quotes">
        <OptionQuotesPanel optionQuotes={optionQuotes} />
      </DerivativesAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2FuturesView({ data, futures }: { data: MarketDashboard; futures: FuturesQuoteResponse }) {
  return (
    <ArgusShell data={data} activeTab="derivatives">
      <DerivativesAnalysisLayout activeSubtab="futures">
        <FuturesPanel data={data} futures={futures} />
      </DerivativesAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2OptionLayerView({ data }: { data: MarketDashboard }) {
  return (
    <ArgusShell data={data} activeTab="derivatives">
      <DerivativesAnalysisLayout activeSubtab="option-layer">
        <OptionPutCallLayerPanel data={data} />
      </DerivativesAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2PositionsView({ data, optionQuotes, futures }: { data: MarketDashboard; optionQuotes: OptionQuotesResponse; futures: FuturesQuoteResponse }) {
  return (
    <ArgusShell data={data} activeTab="derivatives">
      <DerivativesAnalysisLayout activeSubtab="positions">
        <PositionsPanel data={data} optionQuotes={optionQuotes} futures={futures} />
      </DerivativesAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2ReactionView({ data }: { data: MarketDashboard }) {
  return (
    <ArgusShell data={data} activeTab="reaction">
      <ReactionPanel data={data} detail />
    </ArgusShell>
  );
}

export function ArgusV2TriggersView({ data }: { data: MarketDashboard }) {
  return (
    <ArgusShell data={data} activeTab="triggers">
      <NewsAnalysisLayout activeSubtab="main">
        <TriggersPanel data={data} detail />
      </NewsAnalysisLayout>
    </ArgusShell>
  );
}

export function ArgusV2NewsFeedView({ data, newsFeed }: { data: MarketDashboard; newsFeed: NewsFeedResponse }) {
  return (
    <ArgusShell data={data} activeTab="triggers">
      <NewsAnalysisLayout activeSubtab="news">
        <NewsFeedPanel newsFeed={newsFeed} />
      </NewsAnalysisLayout>
    </ArgusShell>
  );
}

function DerivativesAnalysisLayout({ activeSubtab, children }: { activeSubtab: DerivativesAnalysisTab; children: ReactNode }) {
  return (
    <div className="grid gap-4">
      <nav aria-label="옵션·선물 내부 탭" className="grid border border-[#181816]/16 bg-[#f6f3e9]/88 sm:grid-cols-2 xl:grid-cols-5">
        {DERIVATIVES_ANALYSIS_TABS.map((tab) => {
          const isActive = tab.key === activeSubtab;
          return (
            <Link
              key={tab.key}
              href={tab.href}
              aria-current={isActive ? "page" : undefined}
              className={`border-b border-[#181816]/12 px-4 py-3 transition hover:bg-white sm:border-b-0 sm:border-r ${isActive ? "bg-[#181816] text-[#fffdf7]" : "bg-transparent"}`}
            >
              <p className="text-sm font-black">{tab.label}</p>
              <p className={`mt-1 text-[11px] font-bold ${isActive ? "text-[#fffdf7]/62" : "text-[#181816]/44"}`}>{tab.description}</p>
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}

function NewsAnalysisLayout({ activeSubtab, children }: { activeSubtab: NewsAnalysisTab; children: ReactNode }) {
  return (
    <div className="grid gap-4">
      <nav aria-label="뉴스 분석 내부 탭" className="grid border border-[#181816]/16 bg-[#f6f3e9]/88 sm:grid-cols-2">
        {NEWS_ANALYSIS_TABS.map((tab) => {
          const isActive = tab.key === activeSubtab;
          return (
            <Link
              key={tab.key}
              href={tab.href}
              aria-current={isActive ? "page" : undefined}
              className={`border-b border-[#181816]/12 px-4 py-3 transition hover:bg-white sm:border-b-0 sm:border-r ${isActive ? "bg-[#181816] text-[#fffdf7]" : "bg-transparent"}`}
            >
              <p className="text-sm font-black">{tab.label}</p>
              <p className={`mt-1 text-[11px] font-bold ${isActive ? "text-[#fffdf7]/62" : "text-[#181816]/44"}`}>{tab.description}</p>
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}

function NullableMetricTile({
  label,
  value,
  suffix = "",
  caption,
  tone = "neutral",
  fractionDigits = 2,
}: {
  label: string;
  value: number | null | undefined;
  suffix?: string;
  caption: string;
  tone?: Tone;
  fractionDigits?: number;
}) {
  return (
    <div className="argus-tile px-4 py-3">
      <p className="argus-label">{label}</p>
      <p className={`mt-2 text-xl font-black tracking-tight ${toneClass(tone)}`}>
        {formatNullableValue(value, fractionDigits)}{typeof value === "number" ? suffix : ""}
      </p>
      <p className="mt-1 text-xs font-bold leading-4 text-[#181816]/48">{caption}</p>
    </div>
  );
}

function FuturesPanel({ data, futures }: { data: MarketDashboard; futures: FuturesQuoteResponse }) {
  const dashboardBasis = typeof data.derivatives.basis.value === "number" ? data.derivatives.basis.value : null;
  const displayedBasis = futures.basis ?? dashboardBasis;
  const rows = [
    { label: "종목", value: futures.instrument_name ?? futures.instrument_code ?? "미수신", detail: futures.instrument_code ?? futures.source },
    { label: "현재가", value: formatNullableWithSuffix(futures.price, "pt"), detail: futures.source },
    { label: "전일 대비", value: formatNullableWithSuffix(futures.price_change, "pt"), detail: "KIS 선물 현재가 snapshot" },
    { label: "등락률", value: `${formatPercentValue(futures.change_rate ?? null)}`, detail: "dashboard 판단 선물 변동률 원천" },
    { label: "거래량", value: formatNullableValue(futures.volume, 0), detail: "계약 수 기준" },
    { label: "미결제약정", value: formatNullableValue(futures.open_interest, 0), detail: "계약 수 기준" },
    { label: "미결제약정 변화", value: formatNullableValue(futures.open_interest_change, 0), detail: `${formatPercentValue(futures.open_interest_change_rate ?? null)} 변화율` },
    { label: "Basis", value: formatNullableWithSuffix(futures.basis, "pt"), detail: "선물가와 현물/이론가 차이 확인" },
    { label: "Market Basis", value: formatNullableWithSuffix(futures.market_basis, "pt"), detail: "KIS 제공 market basis" },
    { label: "이론가", value: formatNullableWithSuffix(futures.theoretical_price, "pt"), detail: "KIS 제공 시 표시" },
    { label: "괴리율", value: formatPercentValue(futures.disparity_rate ?? null), detail: "KIS 제공 시 표시" },
    { label: "호가", value: `${formatNullableValue(futures.bid)} / ${formatNullableValue(futures.ask)}`, detail: "매수 / 매도" },
  ];

  return (
    <section className="argus-frame p-5">
      <SectionTitle
        eyebrow="Futures"
        title="선물"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{freshnessLabel(futures.status)}</span>}
      />
      <div className="mt-3 grid gap-2 text-xs font-black text-[#181816]/62 md:grid-cols-5">
        <span className="border border-[#181816]/14 bg-white px-3 py-2">종목 {futures.instrument_name ?? futures.instrument_code ?? "미수신"}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">거래일 {futures.trade_date ?? "-"}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">세션 {futures.session_type ?? "-"}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">수신 {futures.observed_count}건</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">as of {formatDateTime(futures.as_of)}</span>
      </div>

      {futures.status === "missing" ? (
        <div className="mt-4">
          <EmptyNote title="선물 snapshot 미수신" body="KIS 국내파생 선물 snapshot이 저장되면 현재가, 거래량, 미결제약정, basis를 이 탭에 채웁니다." />
        </div>
      ) : null}

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <NullableMetricTile label="현재가" value={futures.price} suffix="pt" caption={futures.source} />
        <NullableMetricTile label="등락률" value={futures.change_rate} suffix="%" caption={formatDateTime(futures.as_of)} tone={valueTone(futures.change_rate)} />
        <NullableMetricTile label="Basis" value={displayedBasis} suffix="pt" caption="선물 프리미엄/디스카운트" tone={valueTone(displayedBasis)} />
        <NullableMetricTile label="미결제약정 변화" value={futures.open_interest_change_rate} suffix="%" caption={`계약 ${formatNullableValue(futures.open_interest_change, 0)}`} tone={valueTone(futures.open_interest_change_rate)} />
      </div>

      <div className="mt-4 overflow-x-auto border border-[#181816]/16 bg-white">
        <table className="w-full min-w-[840px] border-collapse text-xs font-bold">
          <caption className="sr-only">선물 수집 snapshot 상세</caption>
          <thead className="bg-[#f6f3e9] text-[#181816]/62">
            <tr>
              {["항목", "값", "비고"].map((header) => (
                <th key={header} scope="col" className="border border-[#181816]/12 px-3 py-2 text-left">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row" className="border border-[#181816]/10 px-3 py-2 text-left font-black">{row.label}</th>
                <td className="border border-[#181816]/10 px-3 py-2 font-black text-[#181816]/80">{row.value}</td>
                <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/52">{row.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function OptionQuotesPanel({ optionQuotes }: { optionQuotes: OptionQuotesResponse }) {
  return (
    <section className="argus-frame p-4 lg:p-5">
      <SectionTitle
        eyebrow="Option Quotes"
        title="옵션 시세표"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{optionQuotes.observed_count}행 · {freshnessLabel(optionQuotes.status)}</span>}
      />
      <div className="mt-3 grid gap-2 text-xs font-black text-[#181816]/62 md:grid-cols-5">
        <span className="border border-[#181816]/14 bg-white px-3 py-2">기초 {optionQuotes.underlying_name ?? optionQuotes.underlying_code ?? "KOSPI200"}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">현재 {formatQuoteValue(optionQuotes.underlying_price)}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">만기 {optionQuotes.expiry_date ?? optionQuotes.contract_month ?? "-"}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">ATM {formatStrike(optionQuotes.atm_strike ?? null)}</span>
        <span className="border border-[#181816]/14 bg-white px-3 py-2">as of {formatDateTime(optionQuotes.as_of)}</span>
      </div>
      <OptionQuotesTable optionQuotes={optionQuotes} />
      <div className="mt-4 grid gap-2 lg:grid-cols-[1fr_0.75fr]">
        <EmptyNote title="호가 컬럼 미제공" body="현재 KIS 옵션체인 저장값에는 매수·매도 호가가 없어 표시하지 않습니다. API에 호가 필드가 추가되면 같은 표에 바로 확장합니다." />
        <div className="argus-tile px-4 py-3">
          <p className="argus-label">Source</p>
          <p className="mt-2 text-sm font-black">{optionQuotes.source}</p>
          <p className="mt-1 text-xs font-bold text-[#181816]/48">{optionQuotes.trade_date ?? "-"} · {formatDateTime(optionQuotes.as_of)}</p>
        </div>
      </div>
    </section>
  );
}

function OptionPutCallLayerPanel({ data }: { data: MarketDashboard }) {
  const change = data.derivatives.option_open_interest_change;
  const netTone = typeof change.net_change_rate === "number" ? (change.net_change_rate > 0 ? "positive" : change.net_change_rate < 0 ? "negative" : "neutral") : "neutral";

  return (
    <section className="argus-frame p-5">
      <SectionTitle
        eyebrow="Option Layer"
        title="당일 옵션 풋콜 레이어"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{change.dominant_side}</span>}
      />
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SignalTile
          label="CALL OI 변화"
          value={formatPercentValue(change.call_change_rate)}
          caption={change.source}
          tone="positive"
        />
        <SignalTile
          label="PUT OI 변화"
          value={formatPercentValue(change.put_change_rate)}
          caption={change.source}
          tone="negative"
        />
        <SignalTile
          label="순 OI 변화"
          value={formatPercentValue(change.net_change_rate)}
          caption={change.observed_at ? formatDateTime(change.observed_at) : "시간 미수신"}
          tone={netTone}
        />
        <SignalTile
          label="PCR"
          value={formatPoint(data.derivatives.put_call_ratio)}
          caption={data.derivatives.put_call_ratio.source}
          tone={optionPressureTone(data.derivatives.option_pressure)}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_0.85fr]">
        <div className="grid gap-2">
          <SectionTitle eyebrow="Strike Map" title="핵심 행사가" />
          {data.derivatives.key_levels.length > 0 ? (
            data.derivatives.key_levels.map((level) => (
              <div key={`${level.role}-${level.strike_price}`} className="argus-tile px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-black">{level.label} {level.strike_price ? `${level.strike_price}pt` : ""}</p>
                  <span className={`text-xs font-black ${toneClass(optionPressureTone(level.side))}`}>{level.side}</span>
                </div>
                <p className="mt-1 text-sm font-bold text-[#181816]/58">{level.summary}</p>
                <p className="mt-2 text-xs font-bold text-[#181816]/42">{level.source} · {formatDateTime(level.observed_at)}</p>
              </div>
            ))
          ) : (
            <EmptyNote title="행사가 레이어 미수신" body="옵션체인 snapshot이 쌓이면 ATM, 콜/풋 OI 집중 레벨, 순 OI 압력이 표시됩니다." />
          )}
        </div>

        <div className="grid gap-2 content-start">
          <SectionTitle eyebrow="Position" title="주체별 포지션" />
          <Link href="/argus/derivatives/positions" className="argus-tile px-4 py-3 transition hover:bg-white">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="argus-label">종합 포지션</p>
                <p className="mt-2 text-sm font-black">외국인·기관·개인 수급 한 화면</p>
              </div>
              <span className="border border-[#181816]/16 bg-white px-2 py-1 text-xs font-black">열기</span>
            </div>
          </Link>
          <div className="overflow-x-auto border border-[#181816]/16 bg-white">
            <table className="w-full min-w-[560px] border-collapse text-xs font-bold">
              <caption className="sr-only">주체별 선물 포지션 요약</caption>
              <thead className="bg-[#f6f3e9] text-[#181816]/62">
                <tr>
                  {["주체", "선물 순매수", "현물 순매수"].map((header) => (
                    <th key={header} scope="col" className="border border-[#181816]/12 px-3 py-2 text-left">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positionRows(data).map((row) => (
                  <tr key={row.key}>
                    <th scope="row" className="border border-[#181816]/10 px-3 py-2 text-left font-black">{row.label}</th>
                    <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(pointTone(row.futures))}`}>{formatPoint(row.futures, 0)}</td>
                    <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(pointTone(row.spot))}`}>{formatPoint(row.spot, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <EmptyNote title="포지션 탭에서 통합 확인" body="외국인·기관·개인의 옵션 매수·매도·순계약은 한 탭에서 종합창 형태로 비교합니다." />
        </div>
      </div>
    </section>
  );
}

function positionRows(data: MarketDashboard) {
  return [
    {
      key: "foreign",
      label: "외국인",
      futures: data.derivatives.foreign_futures_net_buy,
      spot: data.reaction.spot_foreign_net_buy,
    },
    {
      key: "institution",
      label: "기관",
      futures: data.derivatives.institution_futures_net_buy,
      spot: data.reaction.spot_institution_net_buy,
    },
    {
      key: "individual",
      label: "개인",
      futures: data.derivatives.individual_futures_net_buy,
      spot: data.reaction.spot_individual_net_buy,
    },
  ];
}

type PositionRow = ReturnType<typeof positionRows>[number];

function pointNumber(point: DataPoint) {
  return typeof point.value === "number" ? point.value : null;
}

function combinedPositionValue(row: PositionRow) {
  const futures = pointNumber(row.futures);
  const spot = pointNumber(row.spot);
  if (futures === null && spot === null) return null;
  return (futures ?? 0) + (spot ?? 0);
}

function combinedPositionLabel(row: PositionRow) {
  const value = combinedPositionValue(row);
  if (value === null) return "미수신";
  if (value > 0) return "순매수 우위";
  if (value < 0) return "순매도 우위";
  return "중립";
}

function combinedPositionTone(row: PositionRow): Tone {
  const value = combinedPositionValue(row);
  if (typeof value !== "number") return "neutral";
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

function optionTradingSide(row: OptionQuoteRow) {
  const callValue = row.call_trading_value ?? 0;
  const putValue = row.put_trading_value ?? 0;
  if (callValue > putValue) return "CALL";
  if (putValue > callValue) return "PUT";
  return "BALANCED";
}

function optionTradingRows(optionQuotes: OptionQuotesResponse) {
  return [...optionQuotes.rows]
    .map((row) => {
      const callTradingValue = row.call_trading_value ?? 0;
      const putTradingValue = row.put_trading_value ?? 0;
      return {
        strike_price: row.strike_price,
        call_volume: row.call_volume ?? 0,
        put_volume: row.put_volume ?? 0,
        callTradingValue,
        putTradingValue,
        totalTradingValue: callTradingValue + putTradingValue,
        netTradingValue: callTradingValue - putTradingValue,
        side: optionTradingSide(row),
      };
    })
    .sort((first, second) => second.totalTradingValue - first.totalTradingValue);
}

function optionTradingSummary(optionQuotes: OptionQuotesResponse) {
  const rows = optionTradingRows(optionQuotes);
  const callTradingValue = rows.reduce((total, row) => total + row.callTradingValue, 0);
  const putTradingValue = rows.reduce((total, row) => total + row.putTradingValue, 0);
  const netTradingValue = callTradingValue - putTradingValue;
  const dominantSide = netTradingValue > 0 ? "CALL" : netTradingValue < 0 ? "PUT" : "BALANCED";
  return {
    rows,
    focusRow: rows[0] ?? null,
    callTradingValue,
    putTradingValue,
    netTradingValue,
    dominantSide,
  };
}

function PositionsPanel({ data, optionQuotes, futures }: { data: MarketDashboard; optionQuotes: OptionQuotesResponse; futures: FuturesQuoteResponse }) {
  const participantRows = positionRows(data);
  const keyLevelRows = [...data.derivatives.key_levels].sort((first, second) => (first.strike_price ?? Number.MAX_SAFE_INTEGER) - (second.strike_price ?? Number.MAX_SAFE_INTEGER));
  const tradingSummary = optionTradingSummary(optionQuotes);
  const topTradingRows = tradingSummary.rows.slice(0, 10);
  const futuresTradingValue = typeof futures.price === "number" && typeof futures.volume === "number" ? futures.price * futures.volume * 250_000 : null;

  return (
    <section className="argus-frame p-5">
      <SectionTitle
        eyebrow="Investor Position"
        title="주체별 포지션"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">외국인·기관·개인 통합</span>}
      />
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {participantRows.map((row) => (
          <MetricCard key={row.key} label={`${row.label} 선물`} point={row.futures} fractionDigits={0} />
        ))}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SignalTile label="옵션 압력" value={data.derivatives.option_pressure} caption="CALL은 상방, PUT은 하방 압력" tone={optionPressureTone(data.derivatives.option_pressure)} />
        <MetricCard label="Basis" point={data.derivatives.basis} />
        <MetricCard label="OI 변화" point={data.derivatives.open_interest_change_rate} />
        <MetricCard label="KOSPI200 선물" point={data.derivatives.kospi200_futures_change_rate} />
      </div>
      <div className="mt-4 overflow-x-auto border border-[#181816]/16 bg-white">
        <table className="w-full min-w-[760px] border-collapse text-xs font-bold">
          <caption className="sr-only">주체별 현물 선물 수급</caption>
          <thead className="bg-[#f6f3e9] text-[#181816]/62">
            <tr>
              {["주체", "선물 순매수대금", "현물 순매수대금", "현물·선물 방향", "자료 상태"].map((header) => (
                <th key={header} scope="col" className="border border-[#181816]/12 px-3 py-2 text-left">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {participantRows.length > 0 ? (
              participantRows.map((row) => (
                <tr key={row.key}>
                  <th scope="row" className="border border-[#181816]/10 px-3 py-2 text-left font-black">{row.label}</th>
                  <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(pointTone(row.futures))}`}>{formatPoint(row.futures, 0)}</td>
                  <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(pointTone(row.spot))}`}>{formatPoint(row.spot, 0)}</td>
                  <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(combinedPositionTone(row))}`}>{combinedPositionLabel(row)}</td>
                  <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/52">
                    선물 {freshnessLabel(row.futures.freshness)} · 현물 {freshnessLabel(row.spot.freshness)}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="border border-[#181816]/10 px-4 py-6 text-center text-[#181816]/52">주체별 포지션 원천 데이터가 아직 수신되지 않았습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-4">
        <EmptyNote title="옵션 주체별 포지션 미수신" body="외국인·기관·개인의 CALL/PUT 매수·매도·순계약 원천이 연결되면 현물·선물 수급과 분리된 옵션 종합 표로 채웁니다." />
      </div>
      <div className="mt-4">
        <SectionTitle
          eyebrow="Futures Layer"
          title="선물 시장 레이어"
          right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{freshnessLabel(futures.status)}</span>}
        />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <NullableMetricTile label="선물 현재가" value={futures.price} suffix="pt" caption={futures.instrument_name ?? futures.instrument_code ?? futures.source} />
        <NullableMetricTile label="선물 등락률" value={futures.change_rate} suffix="%" caption={formatDateTime(futures.as_of)} tone={valueTone(futures.change_rate)} />
        <NullableMetricTile label="선물 미결제약정" value={futures.open_interest} caption={`변화 ${formatNullableValue(futures.open_interest_change, 0)}계약`} fractionDigits={0} />
        <SignalTile
          label="선물 거래대금 추정"
          value={futuresTradingValue === null ? "미수신" : formatKrw(futuresTradingValue)}
          caption="현재가 x 거래량 x KOSPI200 승수"
          tone="neutral"
        />
      </div>
      <div className="mt-4">
        <SectionTitle
          eyebrow="Option Turnover"
          title="옵션 거래대금 레이어"
          right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{optionQuotes.observed_count}행</span>}
        />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SignalTile label="CALL 거래대금" value={formatKrw(tradingSummary.callTradingValue)} caption={optionQuotes.source} tone="positive" />
        <SignalTile label="PUT 거래대금" value={formatKrw(tradingSummary.putTradingValue)} caption={optionQuotes.trade_date ?? "거래일 미수신"} tone="negative" />
        <SignalTile
          label="거래대금 우위"
          value={tradingSummary.dominantSide}
          caption={`순 ${formatKrw(Math.abs(tradingSummary.netTradingValue))}`}
          tone={tradingSummary.dominantSide === "CALL" ? "positive" : tradingSummary.dominantSide === "PUT" ? "negative" : "neutral"}
        />
        <SignalTile
          label="최대 거래대금 행사가"
          value={tradingSummary.focusRow ? formatStrike(tradingSummary.focusRow.strike_price) : "미수신"}
          caption={tradingSummary.focusRow ? formatKrw(tradingSummary.focusRow.totalTradingValue) : "옵션 거래대금 미수신"}
          tone={tradingSummary.focusRow?.side === "CALL" ? "positive" : tradingSummary.focusRow?.side === "PUT" ? "negative" : "neutral"}
        />
      </div>
      <div className="mt-4 overflow-x-auto border border-[#181816]/16 bg-white">
        <table className="w-full min-w-[980px] border-collapse text-xs font-bold">
          <caption className="sr-only">행사가별 옵션 거래대금 레이어</caption>
          <thead className="bg-[#f6f3e9] text-[#181816]/62">
            <tr>
              {["행사가", "CALL 거래대금", "PUT 거래대금", "순 거래대금", "CALL 거래량", "PUT 거래량", "우위"].map((header) => (
                <th key={header} scope="col" className="border border-[#181816]/12 px-3 py-2 text-left">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topTradingRows.length > 0 ? (
              topTradingRows.map((row) => (
                <tr key={`trading-${row.strike_price}`}>
                  <th scope="row" className="border border-[#181816]/10 px-3 py-2 text-left font-black">{formatStrike(row.strike_price)}</th>
                  <td className="border border-[#181816]/10 px-3 py-2 font-black argus-red">{formatKrw(row.callTradingValue)}</td>
                  <td className="border border-[#181816]/10 px-3 py-2 font-black argus-blue">{formatKrw(row.putTradingValue)}</td>
                  <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(row.netTradingValue > 0 ? "positive" : row.netTradingValue < 0 ? "negative" : "neutral")}`}>
                    {formatKrw(row.netTradingValue)}
                  </td>
                  <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/58">{formatQuoteValue(row.call_volume, 0)}</td>
                  <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/58">{formatQuoteValue(row.put_volume, 0)}</td>
                  <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(row.side === "CALL" ? "positive" : row.side === "PUT" ? "negative" : "neutral")}`}>{row.side}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="border border-[#181816]/10 px-4 py-6 text-center text-[#181816]/52">옵션 거래대금 원천 데이터가 아직 수신되지 않았습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-4 overflow-x-auto border border-[#181816]/16 bg-white">
        <table className="w-full min-w-[820px] border-collapse text-xs font-bold">
          <caption className="sr-only">행사가별 옵션 레이어 참고</caption>
          <thead className="bg-[#f6f3e9] text-[#181816]/62">
            <tr>
              {["행사가", "방향", "역할", "근거"].map((header) => (
                <th key={header} scope="col" className="border border-[#181816]/12 px-3 py-2 text-left">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {keyLevelRows.length > 0 ? (
              keyLevelRows.map((level, index) => (
                  <tr key={`${level.role}-${level.strike_price ?? index}`}>
                    <th scope="row" className="border border-[#181816]/10 px-3 py-2 text-left font-black">{formatStrike(level.strike_price)}</th>
                    <td className={`border border-[#181816]/10 px-3 py-2 font-black ${toneClass(optionPressureTone(level.side))}`}>{level.side}</td>
                    <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/58">{level.label}</td>
                    <td className="border border-[#181816]/10 px-3 py-2 text-[#181816]/58">{level.summary}</td>
                  </tr>
                ))
            ) : (
              <tr>
                <td colSpan={4} className="border border-[#181816]/10 px-4 py-6 text-center text-[#181816]/52">행사가별 레이어 원천 데이터가 아직 수신되지 않았습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MarketJudgementPanel({ data }: { data: MarketDashboard }) {
  const leadingTrigger = data.triggers[0];
  const leadingStrongSector = data.reaction.strong_sectors[0];
  const leadingWeakSector = data.reaction.weak_sectors[0];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.12fr_0.88fr]">
      <section className="argus-frame p-5">
        <SectionTitle eyebrow="Read First" title="시장 판단" />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="argus-tile p-4">
            <p className="argus-label">Conclusion</p>
            <p className="mt-2 text-3xl font-black tracking-tight">{data.judgement.label}</p>
            <p className="mt-3 text-sm font-bold leading-6 text-[#181816]/62">{data.judgement.transition_condition}</p>
          </div>
          <div className="argus-tile p-4">
            <p className="argus-label">Watch</p>
            <ul className="mt-2 space-y-2">
              {data.judgement.watch_points.map((point) => (
                <li key={point} className="text-sm font-black leading-5">{point}</li>
              ))}
            </ul>
          </div>
        </div>
        <EvidenceGrid data={data} />
      </section>

      <div className="grid gap-4">
        <section className="argus-frame p-5">
          <SectionTitle
            eyebrow="Core Tape"
            title="핵심 수급"
            right={<Link href="/argus/derivatives" className="border border-[#181816]/18 px-2 py-1 text-xs font-black hover:bg-white">상세</Link>}
          />
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <SignalTile
              label="외국인 선물"
              value={formatPoint(data.derivatives.foreign_futures_net_buy, 0)}
              caption={data.derivatives.foreign_futures_net_buy.source}
              tone={pointTone(data.derivatives.foreign_futures_net_buy)}
            />
            <SignalTile
              label="외국인 현물"
              value={formatPoint(data.reaction.spot_foreign_net_buy, 0)}
              caption={data.reaction.spot_foreign_net_buy.source}
              tone={pointTone(data.reaction.spot_foreign_net_buy)}
            />
            <SignalTile
              label="옵션 압력"
              value={data.derivatives.option_pressure}
              caption="CALL은 상방, PUT은 하방 압력"
              tone={optionPressureTone(data.derivatives.option_pressure)}
            />
            <SignalTile
              label="Basis"
              value={formatPoint(data.derivatives.basis)}
              caption={data.derivatives.basis.source}
              tone={pointTone(data.derivatives.basis)}
            />
            <SignalTile
              label="OI 변화"
              value={formatPoint(data.derivatives.open_interest_change_rate)}
              caption={data.derivatives.open_interest_change_rate.source}
              tone={pointTone(data.derivatives.open_interest_change_rate)}
            />
          </div>
        </section>

        <section className="argus-frame p-5">
          <SectionTitle
            eyebrow="Cause And Check"
            title="뉴스·현물 검증"
            right={<Link href="/argus/triggers" className="border border-[#181816]/18 px-2 py-1 text-xs font-black hover:bg-white">뉴스</Link>}
          />
          <div className="mt-4 grid gap-2">
            {leadingTrigger ? (
              <article className="argus-tile px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-black">{leadingTrigger.title}</h3>
                  <span className={`text-xs font-black ${toneClass(leadingTrigger.impact)}`}>{leadingTrigger.impact}</span>
                </div>
                <p className="mt-2 text-sm font-bold leading-5 text-[#181816]/58">{leadingTrigger.summary}</p>
                {leadingTrigger.ai_reason ? (
                  <p className="mt-2 border-l-2 border-[#181816]/20 pl-3 text-xs font-bold leading-5 text-[#181816]/54">{leadingTrigger.ai_reason}</p>
                ) : null}
              </article>
            ) : (
              <EmptyNote title="대표 뉴스 없음" body="Gemini 판단이 꺼져 있거나 실패하면 실뉴스를 임의 분류하지 않고 파생 데이터 중심으로 보수적으로 판단합니다." />
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {leadingStrongSector ? (
                <SignalTile
                  label="버티는 섹터"
                  value={leadingStrongSector.name}
                  caption={leadingStrongSector.reason}
                  tone="positive"
                />
              ) : (
                <EmptyNote title="강한 섹터 없음" body="KIS 현물 반응이 연결되면 표시됩니다." />
              )}
              {leadingWeakSector ? (
                <SignalTile
                  label="눌리는 섹터"
                  value={leadingWeakSector.name}
                  caption={leadingWeakSector.reason}
                  tone="negative"
                />
              ) : (
                <EmptyNote title="약한 섹터 없음" body="KIS 현물 반응이 연결되면 표시됩니다." />
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function EvidenceGrid({ data }: { data: MarketDashboard }) {
  return (
    <div className="mt-4 grid gap-4 md:grid-cols-2">
      <div>
        <p className="argus-label">Reasons</p>
        <ul className="mt-2 space-y-2">
          {data.judgement.reasons.map((reason) => (
            <li key={reason} className="border-l-2 border-[#181816] pl-3 text-sm font-bold leading-6">{reason}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="argus-label">Counter Evidence</p>
        <ul className="mt-2 space-y-2">
          {data.judgement.counter_evidence.map((reason) => (
            <li key={reason} className="border-l-2 border-[#1d4ed8] pl-3 text-sm font-bold leading-6">{reason}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DerivativesPanel({ data, detail = false }: { data: MarketDashboard; detail?: boolean }) {
  return (
    <section className="argus-frame p-5">
      <SectionTitle
        eyebrow="Positioning"
        title="옵션·선물"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{data.derivatives.option_pressure}</span>}
      />
      <p className="mt-3 text-sm font-bold leading-6 text-[#181816]/62">{data.derivatives.summary}</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="외국인 선물" point={data.derivatives.foreign_futures_net_buy} fractionDigits={0} />
        <MetricCard label="KOSPI200 선물" point={data.derivatives.kospi200_futures_change_rate} />
        <MetricCard label="PCR" point={data.derivatives.put_call_ratio} tone="negative" />
        <MetricCard label="OI 변화" point={data.derivatives.open_interest_change_rate} />
        {detail ? <MetricCard label="기관 선물" point={data.derivatives.institution_futures_net_buy} fractionDigits={0} /> : null}
        {detail ? <MetricCard label="개인 선물" point={data.derivatives.individual_futures_net_buy} fractionDigits={0} /> : null}
        {detail ? <MetricCard label="Basis" point={data.derivatives.basis} /> : null}
      </div>
      <div className="mt-4 grid gap-2">
        {data.derivatives.key_levels.length > 0 ? (
          data.derivatives.key_levels.map((level) => (
            <div key={`${level.role}-${level.strike_price}`} className="argus-tile px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-black">{level.label} {level.strike_price ? `${level.strike_price}pt` : ""}</p>
                <span className="text-xs font-black">{level.side}</span>
              </div>
              <p className="mt-1 text-sm font-bold text-[#181816]/58">{level.summary}</p>
            </div>
          ))
        ) : (
          <EmptyNote title="옵션 레벨 미수신" body="옵션체인 snapshot이 쌓이면 ATM, 콜/풋 OI 집중 레벨, 순 OI 압력이 여기에 표시됩니다." />
        )}
      </div>
    </section>
  );
}

function ReactionPanel({ data, detail = false }: { data: MarketDashboard; detail?: boolean }) {
  const sectorMoves = [...data.reaction.strong_sectors, ...data.reaction.weak_sectors];
  return (
    <section className="argus-frame p-5">
      <SectionTitle eyebrow="Confirmation" title="현물 반응" />
      <p className="mt-3 text-sm font-bold leading-6 text-[#181816]/62">{data.reaction.summary}</p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="KOSPI" point={data.reaction.kospi_change_rate} />
        <MetricCard label="KOSDAQ" point={data.reaction.kosdaq_change_rate} />
        <MetricCard label="상승 종목" point={data.reaction.advancing_count} tone="positive" fractionDigits={0} />
        <MetricCard label="하락 종목" point={data.reaction.declining_count} tone="negative" fractionDigits={0} />
        {detail ? <MetricCard label="KOSPI200 선물" point={data.reaction.kospi200_futures_change_rate} /> : null}
        {detail ? <MetricCard label="외국인 현물" point={data.reaction.spot_foreign_net_buy} fractionDigits={0} /> : null}
        {detail ? <MetricCard label="기관 현물" point={data.reaction.spot_institution_net_buy} fractionDigits={0} /> : null}
        {detail ? <MetricCard label="개인 현물" point={data.reaction.spot_individual_net_buy} fractionDigits={0} /> : null}
      </div>
      <div className="mt-4 grid gap-2">
        {sectorMoves.length > 0 ? (
          sectorMoves.map((sector) => (
            <div key={sector.name} className="flex items-center justify-between gap-3 argus-tile px-4 py-3">
              <div>
                <p className={`text-sm font-black ${toneClass(sector.tone)}`}>{sector.name}</p>
                <p className="mt-1 text-xs font-bold text-[#181816]/52">{sector.reason}</p>
              </div>
              <span className={`text-sm font-black ${toneClass(sector.tone)}`}>{sector.change_rate?.toFixed(2) ?? "-"}%</span>
            </div>
          ))
        ) : (
          <EmptyNote title="섹터 반응 미연결" body="현물 반응 provider가 연결되면 강한 섹터와 약한 섹터를 여기서 비교합니다." />
        )}
      </div>
    </section>
  );
}

function TriggersPanel({ data, detail = false }: { data: MarketDashboard; detail?: boolean }) {
  return (
    <section className="argus-frame p-5">
      <SectionTitle eyebrow="Causality" title="뉴스 분석 메인" />
      <div className="mt-4 grid gap-2">
        {data.triggers.length > 0 ? (
          data.triggers.map((trigger) => (
            <article key={trigger.id} className="argus-tile px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-black">{trigger.title}</h3>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`text-xs font-black ${toneClass(trigger.impact)}`}>{trigger.impact}</span>
                  <span className="text-xs font-black text-[#181816]/42">{trigger.connection_strength}</span>
                </div>
              </div>
              <p className="mt-2 text-sm font-bold leading-6 text-[#181816]/58">{trigger.summary}</p>
              {trigger.ai_reason ? (
                <p className="mt-3 border-l-2 border-[#181816]/20 pl-3 text-sm font-bold leading-6 text-[#181816]/58">{trigger.ai_reason}</p>
              ) : null}
              {(trigger.affected_factors ?? []).length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1">
                  {(trigger.affected_factors ?? []).map((factor) => (
                    <span key={factor} className="border border-[#181816]/14 bg-white px-2 py-1 text-[11px] font-black text-[#181816]/54">{factor}</span>
                  ))}
                </div>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold text-[#181816]/42">
                <span>{trigger.source}</span>
                <span>{triggerConfidenceLabel(trigger.ai_confidence)}</span>
              </div>
              {detail ? <p className="mt-1 text-xs font-bold text-[#181816]/42">{trigger.published_at ?? "published time missing"}</p> : null}
            </article>
          ))
        ) : (
          <EmptyNote title="뉴스 트리거 없음" body="Gemini 판단이 꺼져 있거나 실패하면 실뉴스를 임의 분류하지 않습니다. provider 상태와 smoke-news-ai 결과를 확인하세요." />
        )}
      </div>
    </section>
  );
}

function NewsFeedPanel({ newsFeed }: { newsFeed: NewsFeedResponse }) {
  return (
    <section className="argus-frame p-5">
      <SectionTitle
        eyebrow="Live Feed"
        title="실시간 뉴스"
        right={<span className="border border-[#181816]/18 px-2 py-1 text-xs font-black">{newsFeed.provider} · {freshnessLabel(newsFeed.status)}</span>}
      />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold text-[#181816]/48">
        <span>{newsFeed.observed_count}건</span>
        <span>as of {formatDateTime(newsFeed.as_of)}</span>
      </div>
      {newsFeed.error ? (
        <div className="mt-4">
          <EmptyNote title="뉴스 수신 오류" body={newsFeed.error} />
        </div>
      ) : null}
      <div className="mt-4 grid gap-2">
        {newsFeed.items.length > 0 ? (
          newsFeed.items.map((item) => (
            <article key={item.id} className="argus-tile px-4 py-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-start">
                <div>
                  <h3 className="font-black leading-6">{item.title}</h3>
                  {item.summary ? (
                    <p className="mt-2 text-sm font-bold leading-6 text-[#181816]/58">{item.summary}</p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs font-black text-[#181816]/42 sm:justify-end">
                  <span>{formatDateTime(item.published_at)}</span>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" className="border border-[#181816]/14 bg-white px-2 py-1 text-[#181816] hover:bg-[#f6f3e9]">
                      원문
                    </a>
                  ) : null}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold text-[#181816]/42">
                <span>{item.source}</span>
                <span>{freshnessLabel(item.freshness)}</span>
              </div>
            </article>
          ))
        ) : (
          <EmptyNote title="실시간 뉴스 없음" body="RSS 또는 외부 provider가 아직 수신한 경제 뉴스가 없습니다." />
        )}
      </div>
    </section>
  );
}
