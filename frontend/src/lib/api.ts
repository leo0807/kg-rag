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

export async function fetchApi<T>(
    url: string,
    options?: RequestInit,
): Promise<T> {


    // 自动附加 token
    const token = typeof window !== "undefined"
        ? localStorage.getItem("token")
        : null;

    if (token && shouldRefreshToken(token)) {
        await refreshToken();
    }

    const headers: Record<string, string> = {
        ...(options?.headers as Record<string, string>),
    };

    // Re-read after potential refresh so we always use the latest token
    const currentToken = typeof window !== "undefined"
        ? localStorage.getItem("token")
        : null;

    if (currentToken) {
        headers["Authorization"] = `Bearer ${currentToken}`;
    }

    const res = await fetch(url, { ...options, headers });

    if (!res.ok) {
        // token 过期或无效，跳转登录
        if (res.status === 401) {
            if (typeof window !== "undefined") {
                localStorage.removeItem("token");
                localStorage.removeItem("user");
                window.location.href = "/login";
            }
        }

        let message = `请求失败 (${res.status})`;
        try {
            const err = await res.json() as { detail?: string | { msg: string }[] };
            if (err.detail) {
                message = typeof err.detail === "string"
                    ? err.detail
                    : JSON.stringify(err.detail);
            }
        } catch { }
        throw new ApiError(res.status, message);
    }

    return res.json();
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
            headers: { "Authorization": `Bearer ${token}` },
        });
        if (res.ok) {
            const data = await res.json();
            localStorage.setItem("token", data.access_token);
        }
    } catch { }
}