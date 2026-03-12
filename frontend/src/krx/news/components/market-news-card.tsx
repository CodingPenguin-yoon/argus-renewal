import Link from "next/link";

import { Badge } from "@/krx/components/ui/badge";
import { formatKoreanDate } from "@/krx/lib/utils";
import { MarketNewsCard } from "@/krx/types/domain";

const SCOPE_LABELS: Record<MarketNewsCard["marketScope"], string> = {
  kr_market: "한국 증시",
  global_market: "글로벌 변수",
  sector: "업종 파급(제외 대상)",
  company: "개별 종목(제외 대상)",
  ignore: "보조 맥락(제외 대상)",
};

const PROVIDER_LABELS: Record<MarketNewsCard["evidence"][number]["provider"], string> = {
  DART: "DART",
  BIGKINDS: "BIGKinds",
  MK_RSS: "매일경제 RSS",
  NAVER_NEWS: "Naver 탐색",
};

function evidenceRoleLabel(role: MarketNewsCard["evidence"][number]["role"]) {
  if (role === "PRIMARY") return "핵심 근거";
  if (role === "CONFIRMING") return "교차 확인";
  return "탐색 신호";
}

function formatMaybeDate(value: string | null) {
  if (!value) return "시간 미상";
  try {
    return formatKoreanDate(value);
  } catch {
    return value;
  }
}

export function MarketNewsCardView({ card }: { card: MarketNewsCard }) {
  const representativeEvidence = card.evidence.slice(0, 2);

  return (
    <article className="rounded-[28px] border border-slate-200 bg-white/96 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.07)]">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="default">{SCOPE_LABELS[card.marketScope]}</Badge>
        <Badge variant="neutral">{card.primaryRegion === "KR" ? "한국 증시" : "글로벌 증시"}</Badge>
        <Badge variant="neutral">
          <time dateTime={card.publishedAt ?? undefined}>{formatMaybeDate(card.publishedAt)}</time>
        </Badge>
      </div>

      <h3 className="mt-4 text-[1.05rem] font-black leading-snug text-slate-950">{card.title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">{card.oneLineSummary}</p>

      <div className="mt-4 grid gap-3 rounded-2xl bg-slate-50 p-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">WHY IMPORTANT</p>
          <p className="mt-1 text-sm leading-6 text-slate-800">{card.whyItMatters}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">MARKET IMPACT</p>
          <p className="mt-1 text-sm leading-6 text-slate-800">{card.marketImpact}</p>
        </div>
      </div>

      {representativeEvidence.length ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">대표 근거</p>
          <div className="mt-2 grid gap-2">
            {representativeEvidence.map((evidence, index) => (
              <article key={`${evidence.provider}-${evidence.sourceUrl ?? index}`} className="rounded-xl bg-slate-50/80 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="default">{PROVIDER_LABELS[evidence.provider]}</Badge>
                  <Badge variant="neutral">{evidenceRoleLabel(evidence.role)}</Badge>
                </div>
                <p className="mt-2 text-sm leading-5 text-slate-800">{evidence.title ?? evidence.snippet ?? "근거 제목 없음"}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  {evidence.publisher ? <span>{evidence.publisher}</span> : null}
                  {evidence.sourceUrl ? (
                    <Link
                      href={evidence.sourceUrl}
                      target="_blank"
                      className="font-semibold text-slate-700 underline decoration-slate-300 underline-offset-4"
                    >
                      원문
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}
