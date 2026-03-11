"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { marketHref } from "@/krx/lib/market";
import { MarketCode } from "@/krx/types/domain";

export function TopNav({ market }: { market: MarketCode }) {
  const pathname = usePathname();
  const navItems = [
    { href: marketHref(market), label: "시장 신호" },
    { href: marketHref(market, "/news"), label: "뉴스" },
    { href: marketHref(market, "/global-events"), label: "글로벌 이벤트" },
  ];

  return (
    <nav aria-label="메인 해석 탭" className="flex items-center gap-2 overflow-x-auto">
      {navItems.map((item) => {
        const active = item.href === marketHref(market) ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200 ${
              active
                ? "border-amber-500 bg-amber-400 text-slate-950 shadow-sm"
                : "border-amber-200/35 bg-slate-800/60 text-amber-50 hover:border-amber-300/60 hover:bg-slate-700/70"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
