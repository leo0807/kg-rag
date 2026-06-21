import "@testing-library/jest-dom";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HelpDrawer from "@/components/HelpDrawer";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/admin/dashboard"),
}));

// Mock page-guides
vi.mock("@/lib/page-guides", () => ({
  findGuide: vi.fn(),
}));

import { usePathname } from "next/navigation";
import { findGuide } from "@/lib/page-guides";

const mockUsePathname = vi.mocked(usePathname);
const mockFindGuide = vi.mocked(findGuide);

const GUIDE = {
  title: "管理后台",
  summary: "管理后台总览，监控系统运行状态",
  features: ["查看 KPI 指标", "监控实时任务"],
  actions: ["点击左侧菜单导航", "查看图表数据"],
  related: [{ href: "/admin/status", label: "系统状态" }],
};

describe("HelpDrawer", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockUsePathname.mockReturnValue("/admin/dashboard");
    mockFindGuide.mockReturnValue({ guide: GUIDE, key: "/admin/dashboard" });
    localStorage.clear();
  });

  it("renders trigger button", () => {
    render(<HelpDrawer />);
    expect(
      screen.getByRole("button", { name: "打开页面帮助" }),
    ).toBeInTheDocument();
  });

  it("trigger button has aria-expanded false when drawer is closed", () => {
    render(<HelpDrawer />);
    expect(
      screen.getByRole("button", { name: "打开页面帮助" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("opens drawer on trigger button click (aria-expanded becomes true)", async () => {
    render(<HelpDrawer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "打开页面帮助" }));
    });
    expect(
      screen.getByRole("button", { name: "打开页面帮助" }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("shows features and actions inside drawer", async () => {
    render(<HelpDrawer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "打开页面帮助" }));
    });
    expect(screen.getByText("查看 KPI 指标")).toBeInTheDocument();
    expect(screen.getByText("监控实时任务")).toBeInTheDocument();
    expect(screen.getByText("点击左侧菜单导航")).toBeInTheDocument();
  });

  it("shows related page links", async () => {
    render(<HelpDrawer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "打开页面帮助" }));
    });
    expect(screen.getByText("系统状态")).toBeInTheDocument();
  });

  it("closes drawer when 关闭 button clicked (aria-expanded back to false)", async () => {
    render(<HelpDrawer />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "打开页面帮助" }));
    });
    expect(
      screen.getByRole("button", { name: "打开页面帮助" }),
    ).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "关闭帮助面板" }));
    expect(
      screen.getByRole("button", { name: "打开页面帮助" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("does not render trigger when no guide found", () => {
    mockFindGuide.mockReturnValue(null);
    render(<HelpDrawer />);
    expect(
      screen.queryByRole("button", { name: "打开页面帮助" }),
    ).not.toBeInTheDocument();
  });

  it("mobile backdrop div renders only when drawer is open", async () => {
    render(<HelpDrawer />);
    // backdrop is a div (not SVG), only present when open
    expect(
      document.querySelector("div[aria-hidden='true']"),
    ).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "打开页面帮助" }));
    });
    expect(
      document.querySelector("div[aria-hidden='true']"),
    ).toBeInTheDocument();
  });
});
