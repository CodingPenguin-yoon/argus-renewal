import { describe, expect, it } from "vitest";

import {
  classifyCategory,
  inferImportance,
  inferRelatedSectors,
  inferSentiment,
} from "@/lib/analysis/heuristics";

describe("heuristics", () => {
  it("classifies macro category by keywords", () => {
    expect(classifyCategory("연준 기준금리 동결", "macro")).toBe("금리");
    expect(classifyCategory("유가 급등과 OPEC 회의", "macro")).toBe("유가/에너지");
  });

  it("classifies stock category by keywords", () => {
    expect(classifyCategory("분기 실적 매출 상회", "stock")).toBe("실적");
    expect(classifyCategory("신제품 출시 일정 공개", "stock")).toBe("제품 출시");
  });

  it("infers sentiment", () => {
    expect(inferSentiment("가이던스 상향과 성장 확대")).toBe("positive");
    expect(inferSentiment("실적 둔화와 매출 감소")).toBe("negative");
    expect(inferSentiment("회의 결과 발표")).toBe("neutral");
  });

  it("infers importance", () => {
    expect(inferImportance("연준 기준금리 결정")).toBe("high");
    expect(inferImportance("소규모 시범 프로젝트")).toBe("low");
    expect(inferImportance("산업 동향 요약")).toBe("medium");
  });

  it("infers related sectors", () => {
    expect(inferRelatedSectors("AI 서버와 GPU 투자 확대")).toContain("반도체");
    expect(inferRelatedSectors("원유 가격 상승")).toContain("에너지");
  });
});
