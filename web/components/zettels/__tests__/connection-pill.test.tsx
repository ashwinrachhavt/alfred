import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConnectionPill } from "@/components/zettels/connection-pill";

describe("ConnectionPill", () => {
  it("fires onNavigate when the title button is clicked", () => {
    const onNavigate = vi.fn();
    const onEdit = vi.fn();
    render(<ConnectionPill title="Atoms of knowledge" onNavigate={onNavigate} onEdit={onEdit} />);

    fireEvent.click(screen.getByRole("button", { name: "Atoms of knowledge" }));

    expect(onNavigate).toHaveBeenCalledOnce();
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("fires only onEdit when the edit icon is clicked (stopPropagation)", () => {
    const onNavigate = vi.fn();
    const onEdit = vi.fn();
    render(<ConnectionPill title="Atoms of knowledge" onNavigate={onNavigate} onEdit={onEdit} />);

    fireEvent.click(screen.getByRole("button", { name: /edit link to atoms of knowledge/i }));

    expect(onEdit).toHaveBeenCalledOnce();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("hides the edit icon when onEdit is not provided", () => {
    const onNavigate = vi.fn();
    render(<ConnectionPill title="Inbound only" onNavigate={onNavigate} />);

    expect(
      screen.queryByRole("button", { name: /edit link to inbound only/i }),
    ).toBeNull();
  });
});
