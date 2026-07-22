import type {
  MarketFlowDashboard,
  MarketFlowFact,
} from "@/market_terminal/contracts/market-flow";

import styles from "./market-flow-panel.module.css";

type Props = {
  data?: MarketFlowDashboard;
  error?: string;
};

const STATUS_LABELS = {
  fresh: "정상",
  partial: "일부 누락",
  stale: "갱신 지연",
  missing: "데이터 없음",
} as const;

function formatAmount(value: number): string {
  const amount = value / 100_000_000;
  const formatted = new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: Math.abs(amount) < 10 ? 1 : 0,
  }).format(Math.abs(amount));
  if (value === 0) return "0억";
  return `${value > 0 ? "+" : "-"}${formatted}억`;
}

function amountTone(value: number): string {
  if (value > 0) return styles.positive;
  if (value < 0) return styles.negative;
  return styles.neutral;
}

function formatObservedAt(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function FlowFact({ fact, title }: { fact: MarketFlowFact | null; title: string }) {
  if (!fact) {
    return (
      <section className={styles.factEmpty}>
        <div className={styles.factTitle}>{title}</div>
        <p>아직 저장된 fact가 없습니다.</p>
      </section>
    );
  }

  return (
    <section className={styles.fact}>
      <div className={styles.factHeader}>
        <div>
          <span className={styles.factTitle}>{title}</span>
          <span className={fact.freshness === "fresh" ? styles.fresh : styles.stale}>
            {fact.freshness === "fresh" ? "FRESH" : "STALE"}
          </span>
        </div>
        <span>{formatObservedAt(fact.observed_at)}</span>
      </div>
      <div className={styles.investorGrid}>
        <div>
          <span>개인</span>
          <strong className={amountTone(fact.individual_net)}>{formatAmount(fact.individual_net)}</strong>
        </div>
        <div>
          <span>외국인</span>
          <strong className={amountTone(fact.foreign_net)}>{formatAmount(fact.foreign_net)}</strong>
        </div>
        <div>
          <span>기관</span>
          <strong className={amountTone(fact.institution_net)}>{formatAmount(fact.institution_net)}</strong>
        </div>
      </div>
      <div className={styles.provenance}>
        <span>{fact.source}</span>
        <span>{fact.market_scope}</span>
        <span>{fact.quality.toUpperCase()}</span>
      </div>
    </section>
  );
}

export function MarketFlowPanel({ data, error }: Props) {
  if (error) {
    return (
      <section className={styles.emptyState} role="alert">
        <span>API ERROR</span>
        <h1>시장 수급 API에 연결할 수 없습니다.</h1>
        <p>{error}</p>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <section aria-labelledby="market-flow-title">
      <div className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>MARKET FLOW / {data.market_scope}</div>
          <h1 id="market-flow-title">시장 주체별 수급</h1>
          <p>장중 추정치와 장 마감 확정 fixture를 섞지 않고 나란히 확인합니다.</p>
        </div>
        <div className={styles.heroMeta}>
          {!data.is_live && <strong className={styles.demoBadge}>DEMO · NOT LIVE</strong>}
          <span className={styles[`status_${data.status}`]}>{STATUS_LABELS[data.status]}</span>
        </div>
      </div>

      {data.status === "missing" && (
        <div className={styles.seedNotice}>
          mock fact가 비어 있습니다. <code>pnpm seed:market-flow</code> 실행 후 다시 확인하세요.
        </div>
      )}

      <div className={styles.grid}>
        {data.rows.map((row) => (
          <article className={styles.card} key={row.segment}>
            <header className={styles.cardHeader}>
              <div>
                <span>{row.segment.replaceAll("_", " ")}</span>
                <h2>{row.label}</h2>
              </div>
              <span className={styles[`status_${row.status}`]}>{STATUS_LABELS[row.status]}</span>
            </header>
            <FlowFact fact={row.estimate} title="장중 추정" />
            <FlowFact fact={row.confirmed} title="마감 확정 · SIMULATED" />
          </article>
        ))}
      </div>
    </section>
  );
}

