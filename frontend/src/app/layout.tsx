import type { Metadata } from "next";

import "./globals.css";
import { Geist } from "next/font/google";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Argus Renewal",
  description: "한국 시장 수급, KOSPI200 종목과 파생 상태를 확인하는 시장 데이터 터미널",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={`font-sans ${geist.variable}`}>
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
