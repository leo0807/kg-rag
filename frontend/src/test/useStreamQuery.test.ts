import "@testing-library/jest-dom";
import {
  classifyFetchException,
  classifyHttpError,
  classifySseError,
  classifyStreamEndError,
} from "@/app/query/useStreamQuery";
import { describe, expect, it } from "vitest";

describe("useStreamQuery error classification", () => {
  it("classifyFetchException returns network kind when fetch throws TypeError", () => {
    const error = classifyFetchException(new TypeError("fetch failed"));

    expect(error.kind).toBe("network");
    expect(error.retryable).toBe(true);
    expect(error.message).toContain("网络连接失败");
  });

  it("classifyHttpError returns auth kind for 401 responses", () => {
    const error = classifyHttpError(401, { detail: "登录已过期，请重新登录" });

    expect(error.kind).toBe("auth");
    expect(error.httpStatus).toBe(401);
    expect(error.message).toBe("登录已过期，请重新登录");
  });

  it("classifyHttpError returns business kind for quota_exceeded 403 body", () => {
    const error = classifyHttpError(403, {
      code: "quota_exceeded",
      message: "API 额度不足，请联系管理员充值",
    });

    expect(error.kind).toBe("business");
    expect(error.code).toBe("quota_exceeded");
    expect(error.message).toBe("API 额度不足，请联系管理员充值");
  });

  it("classifySseError returns business kind for SSE quota_exceeded event", () => {
    const error = classifySseError({
      code: "quota_exceeded",
      status_code: 403,
      message: "API 额度不足，请联系管理员充值",
    });

    expect(error.kind).toBe("business");
    expect(error.httpStatus).toBe(403);
    expect(error.message).toBe("AI 服务额度不足，请联系管理员充值");
  });

  it("classifyStreamEndError returns stream_truncated when some delta already arrived", () => {
    const error = classifyStreamEndError(true);

    expect(error.kind).toBe("stream_truncated");
    expect(error.retryable).toBe(false);
    expect(error.message).toBe("回答中断，已显示部分内容");
  });

  it("classifyStreamEndError returns stream_empty when no delta arrived", () => {
    const error = classifyStreamEndError(false);

    expect(error.kind).toBe("stream_empty");
    expect(error.retryable).toBe(false);
    expect(error.message).toBe("服务暂时不可用，请稍后重试");
  });
});
