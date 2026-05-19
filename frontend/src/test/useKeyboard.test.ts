import "@testing-library/jest-dom";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGlobalKeyboard } from "@/hooks/useKeyboard";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

describe("useGlobalKeyboard", () => {
  beforeEach(() => {
    push.mockClear();
  });

  it("pushes /search when Cmd/Ctrl+K is pressed", () => {
    renderHook(() => useGlobalKeyboard());

    act(() => {
      document.body.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "k",
          metaKey: true,
          bubbles: true,
        }),
      );
    });

    expect(push).toHaveBeenCalledWith("/search");
  });

  it("pushes /query when Cmd/Ctrl+/ is pressed", () => {
    renderHook(() => useGlobalKeyboard());

    act(() => {
      document.body.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "/",
          ctrlKey: true,
          bubbles: true,
        }),
      );
    });

    expect(push).toHaveBeenCalledWith("/query");
  });

  it("ignores ? hotkey when focus is inside an input", () => {
    const { result } = renderHook(() => useGlobalKeyboard());
    const input = document.createElement("input");
    document.body.appendChild(input);

    act(() => {
      input.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "?",
          bubbles: true,
        }),
      );
    });

    expect(result.current.showShortcuts).toBe(false);
    input.remove();
  });
});
