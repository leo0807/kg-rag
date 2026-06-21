import "@testing-library/jest-dom";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import BillingPage from "@/app/admin/billing/page";

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

const BILLS = [
    {
        id: "bill-1",
        billing_period: "2026-05",
        status: "paid",
        base_amount: "999.00",
        overage_amount: "0.00",
        total_amount: "999.00",
        details: {},
        paid_at: "2026-06-01",
        created_at: "2026-05-31",
    },
    {
        id: "bill-2",
        billing_period: "2026-06",
        status: "pending",
        base_amount: "999.00",
        overage_amount: "50.00",
        total_amount: "1049.00",
        details: {},
        paid_at: null,
        created_at: "2026-06-30",
    },
];

const PLANS = [
    {
        name: "standard",
        display_name: "标准版",
        monthly_price_cny: "999.00",
        yearly_price_cny: "9990.00",
        max_users: 20,
        max_documents: 500,
        max_queries_per_month: 50000,
    },
];

describe("BillingPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it("shows loading initially", () => {
        mockFetchApi.mockReturnValue(new Promise(() => {}));
        render(<BillingPage />);
        expect(screen.getByText(/加载中/)).toBeInTheDocument();
    });

    it("renders bills table after successful fetch", async () => {
        mockFetchApi
            .mockResolvedValueOnce(BILLS)
            .mockResolvedValueOnce(PLANS);
        render(<BillingPage />);
        await waitFor(() => expect(screen.queryByText(/加载中/)).not.toBeInTheDocument());
        expect(screen.getByText("账单中心")).toBeInTheDocument();
        expect(screen.getByText("2026-05")).toBeInTheDocument();
        expect(screen.getByText("2026-06")).toBeInTheDocument();
    });

    it("switches to plans tab on click", async () => {
        mockFetchApi
            .mockResolvedValueOnce(BILLS)
            .mockResolvedValueOnce(PLANS);
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText("套餐详情")).toBeInTheDocument());
        fireEvent.click(screen.getByText("套餐详情"));
        expect(screen.getByText("标准版")).toBeInTheDocument();
        expect(screen.getByText(/999\.00/)).toBeInTheDocument();
    });

    it("shows 403 permission error", async () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        mockFetchApi.mockRejectedValue(new (ApiError as any)("Forbidden", 403));
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText("无权限访问账单功能")).toBeInTheDocument());
    });

    it("shows generic load error", async () => {
        mockFetchApi.mockRejectedValue(new Error("Network error"));
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText(/加载失败/)).toBeInTheDocument());
    });

    it("pending bill shows 标记已付 button", async () => {
        mockFetchApi
            .mockResolvedValueOnce(BILLS)
            .mockResolvedValueOnce(PLANS);
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText("标记已付")).toBeInTheDocument());
    });

    it("paid bill does not show 标记已付 button", async () => {
        const paidOnly = [BILLS[0]]; // status: paid
        mockFetchApi
            .mockResolvedValueOnce(paidOnly)
            .mockResolvedValueOnce(PLANS);
        render(<BillingPage />);
        await waitFor(() => expect(screen.queryByText(/加载中/)).not.toBeInTheDocument());
        expect(screen.queryByText("标记已付")).not.toBeInTheDocument();
    });

    it("pay action removes 标记已付 button from that row", async () => {
        mockFetchApi
            .mockResolvedValueOnce(BILLS)
            .mockResolvedValueOnce(PLANS)
            .mockResolvedValueOnce({}); // pay endpoint
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText("标记已付")).toBeInTheDocument());
        fireEvent.click(screen.getByText("标记已付"));
        await waitFor(() => expect(screen.queryByText("标记已付")).not.toBeInTheDocument());
    });

    it("shows empty state when no bills", async () => {
        mockFetchApi
            .mockResolvedValueOnce([])
            .mockResolvedValueOnce([]);
        render(<BillingPage />);
        await waitFor(() => expect(screen.getByText("暂无账单")).toBeInTheDocument());
    });
});
