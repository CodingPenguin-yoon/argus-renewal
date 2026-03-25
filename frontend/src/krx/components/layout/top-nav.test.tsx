import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopNav } from "@/krx/components/layout/top-nav";

vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean | null;
    children: React.ReactNode;
  }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/krx/news",
}));

describe("krx top nav", () => {
  it("renders the app-wide krx tabs", () => {
    render(<TopNav market="krx" />);

    expect(screen.getByRole("link", { name: "대시보드" })).toHaveAttribute("href", "/krx/dashboard");
    expect(screen.getByRole("link", { name: "AI 인사이트" })).toHaveAttribute("href", "/krx/insights");
    expect(screen.getByRole("link", { name: "파생·수급" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "시장 뉴스" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "매크로 캘린더" })).toHaveAttribute("href", "/krx/macro-calendar");
    expect(screen.queryByRole("link", { name: "파생" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "대시보드" })).toHaveAttribute("data-prefetch", "true");
    expect(screen.getByRole("link", { name: "AI 인사이트" })).toHaveAttribute("data-prefetch", "true");
    expect(screen.getByRole("link", { name: "파생·수급" })).toHaveAttribute("data-prefetch", "true");
    expect(screen.getByRole("link", { name: "시장 뉴스" })).toHaveAttribute("data-prefetch", "false");
    expect(screen.getByRole("link", { name: "매크로 캘린더" })).toHaveAttribute("data-prefetch", "true");
  });
});
