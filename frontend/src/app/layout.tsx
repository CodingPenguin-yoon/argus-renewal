import type { Metadata } from "next";

import { AppShellHeader } from "@/components/layout/app-shell";
import "./globals.css";
import { getSearchIndex } from "@/lib/server/data-service";

export const metadata: Metadata = {
  title: "Argus 금융 뉴스",
  description: "거시/종목 뉴스를 쉬운 문장으로 해석해주는 금융 뉴스 서비스",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const searchIndex = await getSearchIndex();

  return (
    <html lang="ko">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AppShellHeader stocks={searchIndex.stocks} news={searchIndex.news} />
        <main>{children}</main>
      </body>
    </html>
  );
}
