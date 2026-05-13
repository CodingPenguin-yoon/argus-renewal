import Link from "next/link";
import type { ReactNode } from "react";

import type { DataPoint, MarketDashboard } from "@/argus_v2/contracts/dashboard";

type Tone = "positive" | "neutral" | "negative";
type ArgusTab = "judgement" | "derivatives" | "reaction" | "triggers";

const ARGUS_TABS: Array<{ key: ArgusTab; label: string; href: string; description: string }> = [
  { key: "judgement", label: "시장 판단", href: "/argus", description: "결론과 근거" },
  { key: "derivatives", label: "옵션·선물", href: "/argus/derivatives", description: "포지셔닝" },
  { key: "reaction", label: "현물 반응", href: "/argus/reaction", description: "검증" },
  { key: "triggers", label: "뉴스 트리거", href: "/argus/triggers", description: "원인" },
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
      <div className="mx-auto max-w-7xl px-5 py-5">
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
                <p className="mt-1 text-xs font-bold text-[#181816]/48">{provider.error ?? `${provider.observed_count}건 수신`}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
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
      <DerivativesPanel data={data} detail />
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
      <TriggersPanel data={data} detail />
    </ArgusShell>
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
      <SectionTitle eyebrow="Causality" title="뉴스 트리거" />
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
