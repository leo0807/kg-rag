import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import QuotaPanel from "@/components/quota/QuotaPanel";

vi.mock("@/lib/api", () => ({
    fetchApi: vi.fn(),
    ApiError: class ApiError extends Error {
        status: number;
        constructor(msg: string, status: number) {
            super(msg);
            this.status = status;
        }
    },
}));

import { fetchApi, ApiError } from "@/lib/api";
const mockFetchApi = vi.mocked(fetchApi);

const QUOTA_DATA = {
    period: "2026-06",
    queries: { used: 500, limit: 10000, pct: 5 },
    tokens: { used: 200000, limit: 5000000, pct: 4 },
    storage_mb: { used: 1200, limit: 5000, pct: 24 },
    users: { used: 3, limit: 10, pct: 30 },
    documents: { used: 45, limit: 100, pct: 45 },
    features: { advanced_search: true, export_pdf: false },
};

describe("QuotaPanel", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it("shows loading state initially", () => {
        mockFetchApi.mockReturnValue(new Promise(() => {}));
        render(<QuotaPanel />);
        expect(screen.getByText(/加载配额数据/)).toBeInTheDocument();
    });

    it("renders quota rows after successful fetch", async () => {
        mockFetchApi.mockResolvedValue(QUOTA_DATA);
        render(<QuotaPanel />);
        await waitFor(() => expect(screen.queryByText(/加载配额数据/)).not.toBeInTheDocument());
        expect(screen.getByText("查询次数")).toBeInTheDocument();
        expect(screen.getByText("LLM Tokens")).toBeInTheDocument();
        expect(screen.getByText("存储空间 (MB)")).toBeInTheDocument();
    });

    it("shows 403 error message for permission denied", async () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        mockFetchApi.mockRejectedValue(new (ApiError as any)("Forbidden", 403));
        render(<QuotaPanel />);
        await waitFor(() => expect(screen.getByText("无权限查看配额")).toBeInTheDocument());
    });

    it("shows generic error for non-403 failures", async () => {
        mockFetchApi.mockRejectedValue(new Error("Network error"));
        render(<QuotaPanel />);
        await waitFor(() => expect(screen.getByText("配额数据加载失败")).toBeInTheDocument());
    });

    it("renders null limit as 无限制", async () => {
        const unlimitedData = {
            ...QUOTA_DATA,
            queries: { used: 100, limit: null, pct: null },
        };
        mockFetchApi.mockResolvedValue(unlimitedData);
        render(<QuotaPanel />);
        await waitFor(() => expect(screen.getByText(/无限制/)).toBeInTheDocument());
    });

    it("renders feature flags section", async () => {
        mockFetchApi.mockResolvedValue(QUOTA_DATA);
        render(<QuotaPanel />);
        await waitFor(() => expect(screen.getByText(/功能开关/)).toBeInTheDocument());
        expect(screen.getByText("advanced_search")).toBeInTheDocument();
        expect(screen.getByText("export_pdf")).toBeInTheDocument();
    });

    it("shows high usage bar in red at 90%+", async () => {
        const highUsage = {
            ...QUOTA_DATA,
            queries: { used: 9500, limit: 10000, pct: 95 },
        };
        mockFetchApi.mockResolvedValue(highUsage);
        const { container } = render(<QuotaPanel />);
        await waitFor(() => expect(screen.queryByText(/加载配额数据/)).not.toBeInTheDocument());
        expect(container.querySelector(".bg-red-500")).toBeInTheDocument();
    });
});
