"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "홈" },
  { href: "/watchlist", label: "관심종목" },
  { href: "/stocks/NVDA", label: "종목 예시" },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="주요 메뉴" className="flex items-center gap-2 overflow-x-auto">
      {navItems.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              active ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-100"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
