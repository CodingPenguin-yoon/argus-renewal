import { MacroCategory, StockCategory } from "@/types/domain";

export const MACRO_CATEGORIES: MacroCategory[] = [
  "금리",
  "인플레이션",
  "고용",
  "환율",
  "유가/에너지",
  "전쟁/지정학",
  "규제",
  "AI/반도체",
];

export const STOCK_CATEGORIES: StockCategory[] = [
  "실적",
  "가이던스",
  "M&A",
  "제품 출시",
  "규제/소송",
  "경영진 변화",
  "수주/계약",
];

export const SENTIMENT_LABELS = {
  positive: "긍정",
  neutral: "중립",
  negative: "부정",
} as const;

export const IMPORTANCE_LABELS = {
  high: "높음",
  medium: "중간",
  low: "낮음",
} as const;

export const DISCLAIMER_TEXT =
  "본 서비스는 투자 권유가 아닌 정보 제공 목적의 뉴스 해석 서비스입니다.";
