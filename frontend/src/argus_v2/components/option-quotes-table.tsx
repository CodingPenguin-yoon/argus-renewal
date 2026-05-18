"use client";

import { useEffect, useMemo, useRef } from "react";

import type { OptionQuoteRow, OptionQuotesResponse } from "@/argus_v2/contracts/dashboard";

const ROW_HEIGHT_PX = 36;
const FOCUS_ABOVE_ROWS = 5;

type Tone = "positive" | "neutral" | "negative";

function toneClass(value: Tone) {
  if (value === "positive") return "argus-red";
  if (value === "negative") return "argus-blue";
  return "text-[#181816]/70";
}

function quotePressureTone(value: OptionQuoteRow["pressure_side"]): Tone {
  if (value === "CALL") return "positive";
  if (value === "PUT") return "negative";
  return "neutral";
}

function formatQuoteValue(value: number | null | undefined, fractionDigits = 2) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  });
}

function formatTradingValue(value: number | null | undefined) {
  if (typeof value !== "number") return "-";
  const absValue = Math.abs(value);
  if (absValue >= 100_000_000) {
    return `${(value / 100_000_000).toLocaleString("ko-KR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    })}억`;
  }
  if (absValue >= 10_000) {
    return `${(value / 10_000).toLocaleString("ko-KR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}만`;
  }
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
}

function formatStrike(value: number | null | undefined) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: value % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

function rowTradingValue(row: OptionQuoteRow) {
  const callValue = row.call_trading_value ?? (row.call_last_price ?? 0) * (row.call_volume ?? 0);
  const putValue = row.put_trading_value ?? (row.put_last_price ?? 0) * (row.put_volume ?? 0);
  return callValue + putValue;
}

export function OptionQuotesTable({ optionQuotes }: { optionQuotes: OptionQuotesResponse }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => [...optionQuotes.rows].sort((first, second) => first.strike_price - second.strike_price), [optionQuotes.rows]);
  const focusIndex = useMemo(() => {
    if (rows.length === 0) return -1;
    return rows.reduce((bestIndex, row, index) => (rowTradingValue(row) > rowTradingValue(rows[bestIndex]) ? index : bestIndex), 0);
  }, [rows]);
  const focusRow = focusIndex >= 0 ? rows[focusIndex] : null;
  const topSpacerRows = Math.max(FOCUS_ABOVE_ROWS - focusIndex, 0);
  const bottomSpacerRows = focusIndex >= 0 ? Math.max(FOCUS_ABOVE_ROWS - (rows.length - 1 - focusIndex), 0) : 0;

  useEffect(() => {
    const scrollNode = scrollRef.current;
    if (!scrollNode || focusIndex < 0) return;
    const topRowIndex = Math.max(focusIndex + topSpacerRows - FOCUS_ABOVE_ROWS, 0);
    scrollNode.scrollTop = topRowIndex * ROW_HEIGHT_PX;
  }, [focusIndex, topSpacerRows]);

  return (
    <div className="mt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs font-black text-[#181816]/54">
        <span>초기 포커스 {focusRow ? `${formatStrike(focusRow.strike_price)} 행사가 · 거래대금 ${formatTradingValue(rowTradingValue(focusRow))}` : "미수신"}</span>
        <span>기준: KIS 거래대금 CALL+PUT</span>
      </div>
      <div ref={scrollRef} className="max-h-[480px] overflow-auto border border-[#181816]/16 bg-white" data-testid="option-quotes-scroll-window">
        <table className="w-full min-w-[1660px] border-collapse text-[11px] font-bold">
          <caption className="sr-only">풋과 콜을 행사가 기준으로 좌우에 배치한 옵션 시세표</caption>
          <thead className="sticky top-0 z-20 bg-[#f6f3e9] text-[#181816]/62">
            <tr>
              <th colSpan={7} scope="colgroup" className="border border-[#181816]/12 px-2 py-2 text-center">풋</th>
              <th rowSpan={2} scope="col" className="sticky left-0 z-30 border border-[#181816]/12 bg-[#181816] px-3 py-2 text-center text-[#fffdf7]">행사가</th>
              <th colSpan={7} scope="colgroup" className="border border-[#181816]/12 px-2 py-2 text-center">콜</th>
              <th colSpan={3} scope="colgroup" className="border border-[#181816]/12 px-2 py-2 text-center">OI 압력</th>
            </tr>
            <tr>
              {["거래량", "거래대금", "I.V", "OI", "OI 증감", "대비", "현재가"].map((label) => (
                <th key={`put-${label}`} scope="col" className="border border-[#181816]/12 px-2 py-2 text-right">{label}</th>
              ))}
              {["현재가", "대비", "OI 증감", "OI", "I.V", "거래량", "거래대금"].map((label) => (
                <th key={`call-${label}`} scope="col" className="border border-[#181816]/12 px-2 py-2 text-right">{label}</th>
              ))}
              {["순 OI", "C/P OI", "방향"].map((label) => (
                <th key={`pressure-${label}`} scope="col" className="border border-[#181816]/12 px-2 py-2 text-right">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              <>
                {topSpacerRows > 0 ? (
                  <tr aria-hidden="true" style={{ height: topSpacerRows * ROW_HEIGHT_PX }}>
                    <td colSpan={18} className="border border-[#181816]/10 bg-[#f8f6ef]" />
                  </tr>
                ) : null}
                {rows.map((row, index) => {
                  const isAtm = row.moneyness === "ATM" || row.strike_price === optionQuotes.atm_strike;
	                  const isFocus = index === focusIndex;
	                  return (
	                    <tr key={row.strike_price} className={`h-9 ${isAtm ? "bg-[#fff8df]" : "bg-white"} ${isFocus ? "outline outline-2 outline-[#181816]" : ""}`}>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatQuoteValue(row.put_volume, 0)}</td>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatTradingValue(row.put_trading_value)}</td>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatQuoteValue(row.put_implied_volatility)}</td>
                      <td className="border border-[#181816]/10 px-2 py-2 text-right font-black text-[#181816]">{formatQuoteValue(row.put_open_interest, 0)}</td>
                      <td className={`border border-[#181816]/10 px-2 py-2 text-right ${toneClass(row.put_open_interest_change && row.put_open_interest_change > 0 ? "negative" : "neutral")}`}>
                        {formatQuoteValue(row.put_open_interest_change, 0)}
                      </td>
                      <td className={`border border-[#181816]/10 px-2 py-2 text-right ${toneClass(row.put_change_rate && row.put_change_rate > 0 ? "positive" : row.put_change_rate && row.put_change_rate < 0 ? "negative" : "neutral")}`}>
                        {formatQuoteValue(row.put_change_rate)}
                      </td>
                      <td className="border border-[#181816]/10 px-2 py-2 text-right font-black argus-blue">{formatQuoteValue(row.put_last_price)}</td>
                      <th scope="row" className="sticky left-0 z-10 border border-[#181816]/12 bg-[#181816] px-3 py-2 text-center font-black text-[#fffdf7]">{formatStrike(row.strike_price)}</th>
                      <td className="border border-[#181816]/10 px-2 py-2 text-right font-black argus-red">{formatQuoteValue(row.call_last_price)}</td>
                      <td className={`border border-[#181816]/10 px-2 py-2 text-right ${toneClass(row.call_change_rate && row.call_change_rate > 0 ? "positive" : row.call_change_rate && row.call_change_rate < 0 ? "negative" : "neutral")}`}>
                        {formatQuoteValue(row.call_change_rate)}
                      </td>
                      <td className={`border border-[#181816]/10 px-2 py-2 text-right ${toneClass(row.call_open_interest_change && row.call_open_interest_change > 0 ? "positive" : "neutral")}`}>
                        {formatQuoteValue(row.call_open_interest_change, 0)}
                      </td>
                      <td className="border border-[#181816]/10 px-2 py-2 text-right font-black text-[#181816]">{formatQuoteValue(row.call_open_interest, 0)}</td>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatQuoteValue(row.call_implied_volatility)}</td>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatQuoteValue(row.call_volume, 0)}</td>
	                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatTradingValue(row.call_trading_value)}</td>
	                      <td className={`border border-[#181816]/10 px-2 py-2 text-right font-black ${toneClass(row.net_call_put_oi && row.net_call_put_oi > 0 ? "positive" : row.net_call_put_oi && row.net_call_put_oi < 0 ? "negative" : "neutral")}`}>
                        {formatQuoteValue(row.net_call_put_oi, 0)}
                      </td>
                      <td className="border border-[#181816]/10 px-2 py-2 text-right text-[#181816]/70">{formatQuoteValue(row.call_put_oi_ratio)}</td>
                      <td className={`border border-[#181816]/10 px-2 py-2 text-right font-black ${toneClass(quotePressureTone(row.pressure_side))}`}>{row.pressure_side}</td>
                    </tr>
                  );
	                })}
	                {bottomSpacerRows > 0 ? (
	                  <tr aria-hidden="true" style={{ height: bottomSpacerRows * ROW_HEIGHT_PX }}>
	                    <td colSpan={18} className="border border-[#181816]/10 bg-[#f8f6ef]" />
	                  </tr>
	                ) : null}
              </>
            ) : (
              <tr>
                <td colSpan={18} className="border border-[#181816]/10 px-4 py-6 text-center text-[#181816]/52">옵션 시세표 원천 데이터가 아직 수신되지 않았습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
