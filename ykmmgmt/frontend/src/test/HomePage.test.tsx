import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DeviceAnalysisProvider } from "@/contexts/DeviceAnalysisContext";
import HomePage from "@/pages/HomePage";

// Mock recharts to avoid rendering issues in jsdom
vi.mock("recharts", () => ({
  LineChart: () => <div data-testid="line-chart" />,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const OVERVIEW = {
  date: "2026-09-11",
  kpis: [
    { key: "reception", label: "接待数", format: "int", value: 920 },
    { key: "sessions", label: "会话数", format: "int", value: 2700 },
    { key: "refund_count", label: "退款笔数", format: "int", value: 78 },
    { key: "refund_amount", label: "退款金额", format: "currency", value: 10566.8 },
    { key: "complaints", label: "投诉数", format: "int", value: 46 },
  ],
  trend: {
    groups: [
      { key: "reception", label: "接待", series: ["reception", "sessions"] },
      { key: "complaint", label: "投诉", series: ["complaints"] },
    ],
    hours: Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}:00`),
    series: [
      { key: "reception", label: "接待数", values: new Array(24).fill(0) },
      { key: "sessions", label: "会话数", values: new Array(24).fill(0) },
      { key: "complaints", label: "投诉数", values: new Array(24).fill(0) },
    ],
  },
};

function mockOverview() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/api/home/overview")) {
      return Promise.resolve(
        new Response(JSON.stringify(OVERVIEW), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (url.includes("/api/home/complaints")) {
      return Promise.resolve(
        new Response(JSON.stringify({ total: 0, rows: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
}

function renderHome() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DeviceAnalysisProvider>
        <HomePage />
      </DeviceAnalysisProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HomePage — fixed business dashboard", () => {
  it("renders every KPI card with its formatted value", async () => {
    mockOverview();
    renderHome();
    // Series labels also appear in the chart legend, so match KPI+legend together
    expect((await screen.findAllByText("接待数")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("会话数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("投诉数").length).toBeGreaterThan(0);
    expect(screen.getByText("退款笔数")).toBeInTheDocument();
    expect(screen.getByText("退款金额")).toBeInTheDocument();
    expect(screen.getByText("920")).toBeInTheDocument();
    expect(screen.getByText("2.7k")).toBeInTheDocument();
    expect(screen.getByText("¥10,566.80")).toBeInTheDocument();
  });

  it("renders the 投诉明细 section", async () => {
    mockOverview();
    renderHome();
    expect(await screen.findByText("投诉明细")).toBeInTheDocument();
    expect(screen.getByText(/共 0 条/)).toBeInTheDocument();
  });

  it("shows the trend tabs and toggles groups (multi-select)", async () => {
    mockOverview();
    renderHome();
    const reception = await screen.findByRole("button", { name: "接待" });
    const complaint = screen.getByRole("button", { name: "投诉" });
    // 接待 selected by default
    expect(reception).toHaveAttribute("aria-pressed", "true");
    expect(complaint).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("line-chart")).toBeInTheDocument();

    // Multi-select: adding 投诉 keeps 接待 active
    fireEvent.click(complaint);
    expect(complaint).toHaveAttribute("aria-pressed", "true");
    expect(reception).toHaveAttribute("aria-pressed", "true");

    // Deselecting both shows the empty hint instead of the chart
    fireEvent.click(reception);
    fireEvent.click(complaint);
    expect(screen.getByText("请选择至少一个指标")).toBeInTheDocument();
  });
});
