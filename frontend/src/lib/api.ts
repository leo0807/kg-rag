/**
 * 统一的 API 请求工具
 * 自动处理 FastAPI 的错误格式 {"detail": "..."}
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "";
}

function headersToRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) return Object.fromEntries(headers.entries());
  if (Array.isArray(headers)) return Object.fromEntries(headers);
  return { ...headers };
}

async function readErrorResponse(
  res: Response,
): Promise<string | { detail?: string | { msg: string }[] }> {
  if (res.status === 204) return "";

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as {
      detail?: string | { msg: string }[];
    };
  }

  const text = await res.text();
  if (!text.trim()) return "";

  try {
    return JSON.parse(text) as { detail?: string | { msg: string }[] };
  } catch {
    return text;
  }
}

export async function getAuthHeaders(
  headers?: HeadersInit,
): Promise<Record<string, string>> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  if (token && shouldRefreshToken(token)) {
    await refreshToken();
  }

  const nextHeaders = headersToRecord(headers);
  const currentToken =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  if (currentToken) {
    nextHeaders.Authorization = `Bearer ${currentToken}`;
  }

  return nextHeaders;
}

export interface FetchApiOptions extends RequestInit {
  /** 设为 true 时，401 响应只抛出错误，不自动跳转登录页 */
  noLogout?: boolean;
}

export async function fetchApi<T>(
  url: string,
  options?: FetchApiOptions,
): Promise<T> {
  try {
    const headers = await getAuthHeaders(options?.headers);

    const res = await fetch(url, { ...options, headers });

    if (!res.ok) {
      // token 过期或无效，跳转登录（除非调用方设置了 noLogout）
      if (res.status === 401 && !options?.noLogout) {
        if (typeof window !== "undefined") {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          window.location.href = "/login";
        }
      }

      let message = `请求失败 (${res.status})`;
      try {
        const err = await readErrorResponse(res);
        if (typeof err === "string") {
          if (err.trim()) message = err.trim();
        } else if (err.detail) {
          message =
            typeof err.detail === "string"
              ? err.detail
              : JSON.stringify(err.detail);
        }
        console.error("[FRONTEND_ERROR_RESPONSE]", {
          url,
          status: res.status,
          body: err,
        });
      } catch (parseError) {
        console.error("[FRONTEND_ERROR_RESPONSE_PARSE_FAILED]", {
          url,
          status: res.status,
          error: parseError instanceof Error ? parseError.message : parseError,
        });
      }
      throw new ApiError(res.status, message);
    }

    // 204 No Content (e.g. DELETE) has no body — skip JSON parsing
    if (res.status === 204 || res.headers.get("content-length") === "0") {
      return null as T;
    }

    return res.json();
  } catch (error) {
    if (error instanceof ApiError) {
      console.error("[FRONTEND_ERROR]", {
        url,
        status: error.status,
        message: error.message,
      });
    } else {
      console.error("[FRONTEND_ERROR]", {
        url,
        error: error instanceof Error ? error.message : error,
      });
    }
    throw error;
  }
}

// token 过期前1小时自动刷新
function shouldRefreshToken(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const exp = payload.exp * 1000;
    const now = Date.now();
    // 距离过期不足1小时
    return exp - now < 60 * 60 * 1000;
  } catch {
    return false;
  }
}

async function refreshToken(): Promise<void> {
  const token = localStorage.getItem("token");
  if (!token) return;

  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem("token", data.access_token);
    }
  } catch {}
}
