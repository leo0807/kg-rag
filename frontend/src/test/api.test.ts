import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchApi, ApiError } from "@/lib/api";

function makeResponse({
    ok,
    status,
    json,
    text,
    contentLength,
}: {
    ok: boolean;
    status: number;
    json: () => Promise<unknown>;
    text?: () => Promise<string>;
    contentLength?: string;
}) {
    return {
        ok,
        status,
        headers: {
            get: vi.fn((name: string) =>
                name.toLowerCase() === "content-length" ? contentLength ?? null : null,
            ),
        },
        json,
        text: text ?? (async () => ""),
    } as unknown as Response;
}

describe("fetchApi", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.stubGlobal("localStorage", {
            getItem: vi.fn().mockReturnValue(null),
            setItem: vi.fn(),
            removeItem: vi.fn(),
        });
    });

    it("returns data on success", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: true,
                status: 200,
                json: async () => ({ status: "OK" }),
                contentLength: "12",
            }),
        );

        const result = await fetchApi<{ status: string }>("/api/health");
        expect(result.status).toBe("OK");
    });

    it("throws ApiError on 400", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: false,
                status: 400,
                json: async () => ({ detail: "question 不能为空" }),
            }),
        );

        await expect(fetchApi("/api/query", { method: "POST" }))
            .rejects
            .toThrow("question 不能为空");
    });

    it("ApiError has correct status code", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: false,
                status: 404,
                json: async () => ({ detail: "文档不存在" }),
            }),
        );

        try {
            await fetchApi("/api/documents/INVALID");
        } catch (e) {
            expect(e).toBeInstanceOf(ApiError);
            expect((e as ApiError).status).toBe(404);
        }
    });

    it("rejects network TypeError without wrapping it", async () => {
        global.fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));

        await expect(fetchApi("/api/query")).rejects.toBeInstanceOf(TypeError);
    });

    it("returns auth ApiError for 401 when noLogout is true", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: false,
                status: 401,
                json: async () => ({ detail: "登录已过期，请重新登录" }),
            }),
        );

        await expect(
            fetchApi("/api/query", { noLogout: true }),
        ).rejects.toMatchObject({
            status: 401,
            message: "登录已过期，请重新登录",
        });
    });

    it("returns ApiError for 403 quota_exceeded body", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: false,
                status: 403,
                json: async () => ({
                    detail: "API 额度不足，请联系管理员充值",
                }),
            }),
        );

        await expect(fetchApi("/api/query", { noLogout: true })).rejects.toMatchObject(
            {
                status: 403,
                message: "API 额度不足，请联系管理员充值",
            },
        );
    });

    it("falls back to request failure message when error response is not JSON", async () => {
        global.fetch = vi.fn().mockResolvedValue(
            makeResponse({
                ok: false,
                status: 500,
                json: async () => {
                    throw new Error("Unexpected token <");
                },
                text: async () => "<html>server error</html>",
            }),
        );

        await expect(fetchApi("/api/query", { noLogout: true })).rejects.toMatchObject(
            {
                status: 500,
                message: "请求失败 (500)",
            },
        );
    });
});
