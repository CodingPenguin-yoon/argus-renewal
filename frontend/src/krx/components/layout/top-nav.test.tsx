import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopNav } from "@/krx/components/layout/top-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/krx/news",
}));

describe("krx top nav", () => {
  it("renders the three interpretation tabs", () => {
    render(<TopNav market="krx" />);

    expect(screen.getByRole("link", { name: "시장 신호" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "뉴스" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "글로벌 이벤트" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "파생" })).not.toBeInTheDocument();
  });
});

