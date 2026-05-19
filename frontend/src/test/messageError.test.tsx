import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MessageError } from "@/app/query/MessageError";

describe("MessageError", () => {
  it("uses red tone for network errors", () => {
    const { container } = render(
      <MessageError
        errorInfo={{
          kind: "network_error",
          code: "network_error",
          message: "网络断开",
        } as any}
      />,
    );

    expect(screen.getByText("网络连接异常")).toBeInTheDocument();
    expect(screen.getByText("网络断开")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("border-red-600/70");
  });

  it("uses amber tone for quota_exceeded business errors", () => {
    const { container } = render(
      <MessageError
        errorInfo={{
          code: "quota_exceeded",
          message: "API 额度不足，请联系管理员充值",
        } as any}
        isAdmin
      />,
    );

    expect(screen.getByText("API 额度不足")).toBeInTheDocument();
    expect(screen.getByText("API 额度不足，请联系管理员充值")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("border-amber-600/70");
  });

  it("uses slate tone for stream truncation errors", () => {
    const { container } = render(
      <MessageError
        errorInfo={{
          kind: "stream_truncated",
          code: "stream_truncated",
          message: "回答中断，已显示部分内容",
        } as any}
      />,
    );

    expect(screen.getByText("回答中断")).toBeInTheDocument();
    expect(screen.getByText("回答中断，已显示部分内容")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("border-slate-600/70");
  });
});
