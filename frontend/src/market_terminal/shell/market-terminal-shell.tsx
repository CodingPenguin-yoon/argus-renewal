"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import styles from "./market-terminal-shell.module.css";

const NAV_ITEMS = [
  { href: "/market", label: "대시보드", exact: true },
  { href: "/market/stocks", label: "종목", exact: false },
  { href: "/market/derivatives", label: "파생", exact: false },
];

export function MarketTerminalShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link className={styles.brand} href="/market">
            <span className={styles.brandMark}>A</span>
            <span>
              <strong>ARGUS</strong>
              <small>MARKET TERMINAL</small>
            </span>
          </Link>
          <nav aria-label="시장 터미널 주요 메뉴" className={styles.nav}>
            {NAV_ITEMS.map((item) => {
              const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={active ? styles.navLinkActive : styles.navLink}
                  href={item.href}
                  key={item.href}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className={styles.buildState}>
            <span />
            MOCK-FIRST
          </div>
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}

