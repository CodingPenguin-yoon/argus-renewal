import type { Metadata } from "next";

import "./globals.css";
import { Geist } from "next/font/google";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Argus v2 Cockpit",
  description: "파생/옵션, 뉴스 트리거, 시장 반응을 함께 읽는 한국장 상황판",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={`font-sans ${geist.variable}`}>
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
