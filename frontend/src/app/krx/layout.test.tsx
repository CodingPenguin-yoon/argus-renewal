import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import KrxLayout from "@/app/krx/layout";

vi.mock("@/krx/components/layout/async-header", () => ({
  AsyncMarketHeader: () => (
    <>
      <header>
        <nav>
          <a href="/krx">시장 신호</a>
          <a href="/krx/watchlist">관심종목</a>
        </nav>
      </header>
      <section>
        <h1>오늘의 시장 톤</h1>
      </section>
    </>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/krx",
}));

describe("krx layout", () => {
  it("renders the shared header shell around tab content", async () => {
    const component = await KrxLayout({ children: <div>route body</div> });
    render(component);

    expect(screen.getByRole("link", { name: "시장 신호" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "관심종목" })).toBeInTheDocument();
    expect(screen.getByText("오늘의 시장 톤")).toBeInTheDocument();
    expect(screen.getByText("route body")).toBeInTheDocument();
  });
});
