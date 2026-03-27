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
    const res = await fetch(url, options);

    if (!res.ok) {
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