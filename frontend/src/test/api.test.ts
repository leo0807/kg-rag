import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchApi, ApiError } from "@/lib/api";

describe("fetchApi", () => {
    beforeEach(() => {
        vi.stubGlobal("localStorage", {
            getItem: vi.fn().mockReturnValue(null),
            setItem: vi.fn(),
            removeItem: vi.fn(),
        });
    });

    it("returns data on success", async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ status: "OK" }),
        } as any);

        const result = await fetchApi<{ status: string }>("/api/health");
        expect(result.status).toBe("OK");
    });

    it("throws ApiError on 400", async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ detail: "question 不能为空" }),
        } as any);

        await expect(fetchApi("/api/query", { method: "POST" }))
            .rejects
            .toThrow("question 不能为空");
    });

    it("ApiError has correct status code", async () => {
        global.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            json: async () => ({ detail: "文档不存在" }),
        } as any);

        try {
            await fetchApi("/api/documents/INVALID");
        } catch (e) {
            expect(e).toBeInstanceOf(ApiError);
            expect((e as ApiError).status).toBe(404);
        }
    });
});