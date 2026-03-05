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

export type MarketEvent = {
  id: string;
  title: string;
  eventDate: string;
  country: "KR" | "US" | "GLOBAL";
  description: string;
  impactLevel: Importance;
  relatedTickers: string[];
};
