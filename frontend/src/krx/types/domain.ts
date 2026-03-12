export type MarketCode = "krx";

export type NewsType = "macro" | "stock";

export type Sentiment = "positive" | "neutral" | "negative";

export type Importance = "high" | "medium" | "low";

export type MacroCategory =
  | "금리"
  | "인플레이션"
  | "고용"
  | "환율"
  | "유가/에너지"
  | "전쟁/지정학"
  | "규제"
  | "AI/반도체";

export type StockCategory =
  | "실적"
  | "가이던스"
  | "M&A"
  | "제품 출시"
  | "규제/소송"
  | "경영진 변화"
  | "수주/계약";

export type NewsCategory = MacroCategory | StockCategory;

export type Sector =
  | "테크"
  | "반도체"
  | "자동차"
  | "에너지"
  | "금융"
  | "헬스케어"
  | "소비재"
  | "산업재"
  | "커뮤니케이션";

export type Stock = {
  ticker: string;
  name: string;
  market: "US" | "KR";
  sector: Sector;
};

export type NewsBase = {
  id: string;
  type: NewsType;
  title: string;
  summary: string;
  whyItMatters: string;
  source: string;
  sourceUrl: string;
  publishedAt: string;
  sentiment: Sentiment;
  importance: Importance;
  relatedSectors: Sector[];
  relatedTickers: string[];
  category: NewsCategory;
  tags: string[];
};

export type MacroNews = NewsBase & {
  type: "macro";
  category: MacroCategory;
};

export type StockNews = NewsBase & {
  type: "stock";
  category: StockCategory;
};

export type News = MacroNews | StockNews;

export type GlobalEventRelease = {
  metricCode: string | null;
  state: string;
  unit: string | null;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
  surprise: string | null;
  previousValue: number | null;
  forecastValue: number | null;
  actualValue: number | null;
  surpriseValue: number | null;
  sourceName: string | null;
  sourceUrl: string | null;
  sourceRecordId: string | null;
  actualReleasedAt: string | null;
};

export type GlobalEventImpact = {
  summaryKo: string;
  tone: "risk_on" | "risk_off" | "hawkish" | "dovish" | "neutral" | "mixed";
  impactChannels: string[];
  generationMethod: "rule_based" | "llm";
  providerName: string | null;
  modelName: string | null;
};

export type GlobalEventItem = {
  id: string;
  eventKey: string;
  title: string;
  eventType: string;
  category: string;
  country: string;
  status: string;
  importance: Importance | null;
  importanceSource: string | null;
  eventDateKst: string;
  eventTimeKst: string | null;
  eventTimePrecision: "time" | "date";
  previousEventTimeKst: string | null;
  revisionNote: string | null;
  whyItMattersKo: string;
  source: {
    key: string;
    name: string;
    url: string | null;
    updatedAt: string | null;
  };
  release: GlobalEventRelease;
  impact: GlobalEventImpact | null;
  provenance: Record<string, unknown>;
  updatedAt: string | null;
};

export type GlobalEventsCoverageItem = {
  sourceKey: string;
  sourceName: string;
  sourceKind: "schedule" | "release" | "vendor";
  isRequired: boolean;
  status: "available" | "partial" | "missing";
  availableCount: number;
  expectedCount: number;
  coverageRatio: number;
  eventTypes: string[];
  lastSyncedAt: string | null;
  lastSuccessAt: string | null;
  sourceUrl: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
};

export type GlobalEventsCoverage = {
  state: "full" | "partial" | "empty";
  coverageRatio: number;
  availableSources: number;
  expectedSources: number;
  summary: string;
  updatedAt: string | null;
  items: GlobalEventsCoverageItem[];
};

export type AppHeaderPhase = "pre-open" | "live" | "post-close";

export type AppHeaderCoverageState = "full" | "partial" | "empty";

export type AppHeaderCoverageItemStatus = "available" | "partial" | "missing";

export type AppHeaderSupportingPoint = {
  text: string;
  sourceKey: string;
  sourceLabel: string;
  sourceUrl: string | null;
};

export type AppHeaderCoverageItem = {
  key: string;
  label: string;
  status: AppHeaderCoverageItemStatus;
  sourceName: string | null;
  sourceUrl: string | null;
  updatedAt: string | null;
};

export type AppHeaderSourceCoverage = {
  state: AppHeaderCoverageState;
  coverageRatio: number;
  availableSources: number;
  expectedSources: number;
  summary: string;
  items: AppHeaderCoverageItem[];
};

export type AppBreakingNews = {
  label: string;
  headline: string;
  whyItMattersOneLine: string;
  impactScope: string;
  relatedTabLink: string;
  sourceName: string | null;
  sourceUrl: string | null;
  publishedAt: string | null;
};

export type AppHeader = {
  market: MarketCode;
  marketToneLine: string;
  supportingPoints: AppHeaderSupportingPoint[];
  phase: AppHeaderPhase;
  updatedAt: string | null;
  sourceCoverage: AppHeaderSourceCoverage;
  breakingNews: AppBreakingNews | null;
};

export type MarketNewsEvidenceRole = "PRIMARY" | "CONFIRMING" | "DISCOVERY";

export type MarketNewsEvidenceProvider = "DART" | "BIGKINDS" | "NAVER_NEWS" | "MK_RSS";

export type MarketNewsEvidence = {
  role: MarketNewsEvidenceRole;
  provider: MarketNewsEvidenceProvider;
  title: string | null;
  snippet: string | null;
  publisher: string | null;
  sourceUrl: string | null;
  canonicalUrl: string | null;
  storagePolicy: "CANONICAL_EVENT" | "PERSISTENT_EVIDENCE" | "TRANSIENT_DISCOVERY";
  publishedAt: string | null;
};

export type MarketNewsCard = {
  id: string;
  title: string;
  oneLineSummary: string;
  whyItMatters: string;
  marketImpact: string;
  marketScope: "kr_market" | "global_market" | "sector" | "company" | "ignore";
  primaryRegion: "KR" | "GLOBAL";
  trustScore: number;
  noveltyScore: number;
  attentionScore: number;
  rankingScore: number;
  evidenceCount: number;
  crossSourceScore: number;
  publishedAt: string | null;
  updatedAt: string | null;
  evidence: MarketNewsEvidence[];
  provenance: Record<string, unknown>;
};

export type MarketNewsCoverageItem = {
  provider: "DART" | "BIGKINDS" | "NAVER_NEWS" | "MK_RSS" | "NAVER_DATALAB";
  status: "available" | "partial" | "missing";
  documentCount: number;
  eventCount: number;
  evidenceCount: number;
  lastPublishedAt: string | null;
  lastSyncedAt: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
};

export type MarketNewsCoverage = {
  state: "full" | "partial" | "empty";
  coverageRatio: number;
  availableSources: number;
  expectedSources: number;
  summary: string;
  updatedAt: string | null;
  items: MarketNewsCoverageItem[];
};

export type MarketNewsHeaderContext = {
  updatedAt: string | null;
  summaryLine: string;
  coverage: {
    state: "full" | "partial" | "empty";
    coverageRatio: number;
    availableSources: number;
    expectedSources: number;
    summary: string;
  };
  columns: Array<{
    key: "KR" | "GLOBAL";
    label: string;
    count: number;
    leadTitle: string | null;
    leadScope: string | null;
  }>;
};

export type MarketSignalCoverageState = "full" | "partial" | "missing";

export type MarketSignalTone = "positive" | "neutral" | "negative";

export type MarketSignalTrendBadge = {
  label: string;
  tone: MarketSignalTone;
};

export type MarketSignalMetricProvenance = {
  sourceTable: string | null;
  sourceName: string | null;
  sourceUrl: string | null;
  sourceRecordId: string | null;
  tradeDate: string | null;
  metricKey: string | null;
};

export type MarketSignalMetric = {
  key: string;
  label: string;
  rawValue: unknown;
  formattedValue: string;
  provenance: MarketSignalMetricProvenance;
};

export type MarketSignalCardCoverage = {
  state: MarketSignalCoverageState;
  coverageRatio: number;
  label: string;
  sourceNames: string[];
};

export type MarketSignalCard = {
  key: string;
  title: string;
  tone: MarketSignalTone;
  interpretationLine: string;
  detailText: string | null;
  trendBadge: MarketSignalTrendBadge | null;
  sourceCoverage: MarketSignalCardCoverage;
  supportingMetrics: MarketSignalMetric[];
};

export type MarketSignalCoverageSectionStatus = "available" | "missing" | "rule_based";

export type MarketSignalCoverageSection = {
  key: string;
  label: string;
  status: MarketSignalCoverageSectionStatus;
  sourceName: string | null;
  updatedAt: string | null;
};

export type MarketSignalSourceCoverage = MarketSignalCardCoverage & {
  tradeDate: string | null;
  sections: MarketSignalCoverageSection[];
};

export type MarketSignalSummary = {
  requestedDate: string | null;
  date: string | null;
  requestedDateAvailable: boolean;
  isLatestFallback: boolean;
  interpretationLine: string;
  explanationText: string;
  explanationSource: "market_briefings" | "rule_based";
  directionalBias: "bullish" | "bearish" | "neutral";
  gapBias: "gap_up" | "gap_down" | "flat";
  volatilityBias: "rising" | "stable" | "falling";
  confidenceBucket: "low" | "medium" | "high";
  sourceCoverage: MarketSignalSourceCoverage;
  cards: MarketSignalCard[];
  lastUpdatedAt: string | null;
  missingFields: string[];
};

export type DerivativesSourceCoverageState = "full" | "partial" | "missing";

export type DerivativesCoverageSectionStatus = "available" | "missing" | "rule_based";

export type DerivativesCoverageSection = {
  key: string;
  label: string;
  status: DerivativesCoverageSectionStatus;
  sourceName: string | null;
  updatedAt: string | null;
};

export type DerivativesSourceCoverage = {
  tradeDate: string | null;
  state: DerivativesSourceCoverageState;
  coverageRatio: number;
  label: string;
  sourceNames: string[];
  sections: DerivativesCoverageSection[];
};

export type DerivativesBias = "bullish" | "bearish" | "neutral";

export type DerivativesGapBias = "gap_up" | "gap_down" | "flat";

export type DerivativesVolatilityBias = "rising" | "stable" | "falling";

export type DerivativesConfidenceBucket = "low" | "medium" | "high";

export type DerivativesBriefingSource = "market_briefings" | "rule_based";

export type DerivativesNightSignal = "gap_up" | "gap_down" | "flat";

export type DerivativesParticipantSummaryItem = {
  participant: string;
  futuresNetBuy: number | null;
  optionsNetBuy: number | null;
};

export type DerivativesComponent = {
  componentKey: string;
  componentLabel: string;
  componentGroup: string | null;
  rawValue: unknown;
  score: number | null;
  explanationKo: string | null;
  sourceTable: string | null;
  sourceName: string | null;
  sourceUrl: string | null;
  sourceRecordId: string | null;
  sourceMetricKey: string | null;
  dataAvailable: boolean;
};

export type DerivativesSummary = {
  requestedDate: string | null;
  date: string | null;
  requestedDateAvailable: boolean;
  isLatestFallback: boolean;
  sourceCoverage: DerivativesSourceCoverage;
  pcr: number | null;
  pcrChange: number | null;
  callNotional: number | null;
  putNotional: number | null;
  callOpenInterest: number | null;
  putOpenInterest: number | null;
  openInterestTotal: number | null;
  oiChange: number | null;
  foreignFuturesNetPosition: number | null;
  impliedVolatility: number | null;
  impliedVolatilityChange: number | null;
  directionalBias: DerivativesBias;
  gapBias: DerivativesGapBias;
  volatilityBias: DerivativesVolatilityBias;
  confidenceBucket: DerivativesConfidenceBucket;
  explanationText: string;
  briefingSource: DerivativesBriefingSource;
  participantSummary: DerivativesParticipantSummaryItem[];
  detailLevel: number;
  components: DerivativesComponent[];
  lastUpdatedAt: string | null;
  missingFields: string[];
  nightFutures: {
    signal: DerivativesNightSignal | null;
    changeRate: number | null;
    price: number | null;
    priceChange: number | null;
    instrumentCode: string | null;
    instrumentName: string | null;
    snapshotTime: string | null;
    sourceName: string | null;
    sourceUrl: string | null;
  };
};

export type DerivativesTrendItem = {
  date: string;
  pcr: number | null;
  callOpenInterest: number | null;
  putOpenInterest: number | null;
  openInterestTotal: number | null;
  impliedVolatility: number | null;
  sourceName: string | null;
};

export type DerivativesTrends = {
  preset: string;
  date: string | null;
  items: DerivativesTrendItem[];
  missingFields: string[];
};

export type DerivativesInvestorFlowItem = {
  date: string;
  futuresForeignNetBuy: number | null;
  futuresInstitutionNetBuy: number | null;
  futuresIndividualNetBuy: number | null;
  optionsForeignNetBuy: number | null;
  optionsInstitutionNetBuy: number | null;
  optionsIndividualNetBuy: number | null;
  sourceName: string | null;
};

export type DerivativesInvestorFlow = {
  preset: string;
  date: string | null;
  items: DerivativesInvestorFlowItem[];
  missingFields: string[];
};
