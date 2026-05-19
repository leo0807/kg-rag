import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ShortcutsModal from "@/components/ShortcutsModal";

describe("ShortcutsModal", () => {
  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(<ShortcutsModal open onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<ShortcutsModal open onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("关闭"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(<ShortcutsModal open onClose={onClose} />);

    fireEvent.click(container.firstElementChild as HTMLElement);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
