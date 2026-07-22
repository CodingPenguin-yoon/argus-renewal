import type { Metadata } from "next";
import type { ReactNode } from "react";

import { MarketTerminalShell } from "@/market_terminal/shell/market-terminal-shell";

export const metadata: Metadata = {
  title: "Argus Market Terminal",
  description: "KRX 시장 수급, KOSPI200 종목과 파생 상태를 확인하는 시장 데이터 터미널",
};

export default function MarketLayout({ children }: { children: ReactNode }) {
  return <MarketTerminalShell>{children}</MarketTerminalShell>;
}

