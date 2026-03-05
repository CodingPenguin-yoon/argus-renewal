import {
  Importance,
  MacroCategory,
  NewsType,
  Sector,
  Sentiment,
  StockCategory,
} from "@/types/domain";
import { MACRO_CATEGORIES, STOCK_CATEGORIES } from "@/lib/constants";

const macroRules: Record<MacroCategory, string[]> = {
  금리: ["금리", "연준", "기준금리", "fomc", "동결", "인하", "인상"],
  인플레이션: ["cpi", "물가", "인플레이션", "소비자물가", "pce"],
  고용: ["고용", "실업률", "비농업", "nfp", "임금"],
  환율: ["환율", "달러", "원화", "엔화", "달러인덱스"],
  "유가/에너지": ["유가", "원유", "opec", "천연가스", "에너지"],
  "전쟁/지정학": ["전쟁", "지정학", "중동", "제재", "분쟁"],
  규제: ["규제", "법안", "관세", "승인", "감독"],
  "AI/반도체": ["ai", "반도체", "gpu", "hbm", "파운드리"],
};

const stockRules: Record<StockCategory, string[]> = {
  실적: ["실적", "매출", "영업이익", "순이익", "어닝"],
  가이던스: ["가이던스", "전망", "목표", "연간"],
  "M&A": ["인수", "합병", "m&a", "지분"],
  "제품 출시": ["출시", "신제품", "서비스", "플랫폼"],
  "규제/소송": ["소송", "규제", "조사", "벌금", "리콜"],
  "경영진 변화": ["ceo", "사임", "선임", "교체"],
  "수주/계약": ["수주", "계약", "공급", "파트너십"],
};

const positiveWords = ["상향", "호조", "개선", "성장", "수주", "돌파", "강세", "확대"];
const negativeWords = ["하향", "부진", "둔화", "감소", "적자", "약세", "리스크", "지연"];

const highImportanceWords = ["연준", "기준금리", "전쟁", "가이던스", "실적", "규제", "관세", "소송"];
const lowImportanceWords = ["루머", "단기", "소규모", "시범", "예비"];

const sectorMap: Array<{ sector: Sector; words: string[] }> = [
  { sector: "반도체", words: ["반도체", "hbm", "gpu", "파운드리"] },
  { sector: "테크", words: ["ai", "클라우드", "소프트웨어", "플랫폼"] },
  { sector: "자동차", words: ["ev", "전기차", "자율주행", "배터리"] },
  { sector: "에너지", words: ["원유", "유가", "천연가스", "정유"] },
  { sector: "금융", words: ["금리", "은행", "채권", "보험"] },
  { sector: "헬스케어", words: ["제약", "임상", "바이오", "의료기기"] },
  { sector: "소비재", words: ["소비", "유통", "리테일", "브랜드"] },
  { sector: "산업재", words: ["수주", "인프라", "설비", "방산"] },
  { sector: "커뮤니케이션", words: ["광고", "미디어", "콘텐츠", "네트워크"] },
];

function normalize(text: string) {
  return text.toLowerCase();
}

export function classifyCategory(text: string, type: NewsType): MacroCategory | StockCategory {
  const target = normalize(text);
  const ruleSet = type === "macro" ? macroRules : stockRules;
  const fallback = type === "macro" ? MACRO_CATEGORIES[0] : STOCK_CATEGORIES[0];

  for (const [category, keywords] of Object.entries(ruleSet)) {
    if (keywords.some((keyword) => target.includes(keyword))) {
      return category as MacroCategory | StockCategory;
    }
  }

  return fallback;
}

export function inferSentiment(text: string): Sentiment {
  const target = normalize(text);
  const positive = positiveWords.filter((w) => target.includes(w)).length;
  const negative = negativeWords.filter((w) => target.includes(w)).length;

  if (positive > negative) return "positive";
  if (negative > positive) return "negative";
  return "neutral";
}

export function inferImportance(text: string): Importance {
  const target = normalize(text);
  if (highImportanceWords.some((w) => target.includes(w))) {
    return "high";
  }
  if (lowImportanceWords.some((w) => target.includes(w))) {
    return "low";
  }
  return "medium";
}

export function inferRelatedSectors(text: string): Sector[] {
  const target = normalize(text);
  const matched = sectorMap
    .filter(({ words }) => words.some((word) => target.includes(word)))
    .map(({ sector }) => sector);

  return matched.length ? matched : ["테크"];
}

export function inferRelatedTickers(text: string, knownTickers: string[]): string[] {
  const target = normalize(text);
  return knownTickers.filter((ticker) => target.includes(ticker.toLowerCase()));
}
