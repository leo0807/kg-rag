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

    const headers: Record<string, string> = {
        ...(options?.headers as Record<string, string>),
    };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
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