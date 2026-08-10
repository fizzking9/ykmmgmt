import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import VisualizationsListPage from "@/pages/VisualizationsListPage";

// ── Fixtures ───────────────────────────────────────────────────────────────

const BAR_VIZ = {
  id: "viz-bar",
  name: "月度退款柱状图",
  view_id: "view-1",
  chart_type: "bar",
  created_at: "2026-08-01T10:00:00",
  updated_at: "2026-08-01T10:00:00",
};

const TABLE_VIZ = {
  id: "viz-table",
  name: "退款明细表",
  view_id: "view-1",
  chart_type: "table",
  created_at: "2026-08-02T10:00:00",
  updated_at: "2026-08-02T10:00:00",
};

const refetchListMock = vi.fn();
const deleteMutateMock = vi.fn();

// ── Hook mocks ─────────────────────────────────────────────────────────────

vi.mock("@/hooks/useViews", () => ({
  useViews: () => ({
    data: [
      {
        id: "view-1",
        name: "退款视图",
        description: "",
        created_at: "2026-01-01",
        updated_at: "2026-01-01",
      },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useVisualizations", () => ({
  useVisualizations: () => ({
    data: [BAR_VIZ, TABLE_VIZ],
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchListMock,
    isRefetching: false,
  }),
  useVisualizationData: () => ({
    data: {
      columns: ["月份", "金额"],
      rows: [
        { 月份: "2026-06", 金额: 100 },
        { 月份: "2026-07", 金额: 200 },
      ],
      chart_type: "bar",
      config_json: { x_column: "月份", y_columns: ["金额"], title: "" },
    },
    isLoading: false,
  }),
  useDeleteVisualization: () => ({
    mutate: deleteMutateMock,
    isPending: false,
  }),
}));

// Mock html2canvas (imported transitively via the builder page previews)
vi.mock("html2canvas", () => ({
  default: vi.fn(),
}));

// Mock recharts to avoid rendering issues in jsdom
vi.mock("recharts", () => ({
  BarChart: () => <div data-testid="bar-chart" />,
  Bar: () => null,
  LineChart: () => <div data-testid="line-chart" />,
  Line: () => null,
  PieChart: () => <div data-testid="pie-chart" />,
  Pie: () => null,
  Cell: () => null,
  ScatterChart: () => <div data-testid="scatter-chart" />,
  Scatter: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Brush: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderPage() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/visualizations"]}>
        <Routes>
          <Route path="/visualizations" element={<VisualizationsListPage />} />
          <Route path="/visualizations/:id" element={<div>全屏查看页探针</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("VisualizationsListPage", () => {
  it("renders the page title and refresh button", () => {
    renderPage();
    expect(screen.getByText("可视化")).toBeInTheDocument();
    expect(screen.getByText("刷新")).toBeInTheDocument();
  });

  it("renders rows with metadata columns and action buttons", () => {
    renderPage();
    expect(screen.getByText("月度退款柱状图")).toBeInTheDocument();
    expect(screen.getByText("退款明细表")).toBeInTheDocument();
    // Chart type badges
    expect(screen.getByText("柱状图")).toBeInTheDocument();
    expect(screen.getByText("表格")).toBeInTheDocument();
    // Sortable time columns
    expect(screen.getByText("创建时间")).toBeInTheDocument();
    expect(screen.getByText("更新时间")).toBeInTheDocument();
    // Source view name resolved from views list
    expect(screen.getAllByText("退款视图").length).toBeGreaterThanOrEqual(2);
    // Three actions per row
    expect(screen.getAllByText("查看")).toHaveLength(2);
    expect(screen.getAllByText("编辑")).toHaveLength(2);
    expect(screen.getAllByText("删除")).toHaveLength(2);
  });

  it("renders a chart thumbnail only for chart types, not for table", () => {
    const { container } = renderPage();
    // Bar visualization renders a chart preview
    expect(screen.getAllByTestId("bar-chart").length).toBe(1);
    // Table visualization renders an icon placeholder, not a chart —
    // exactly one chart total across both rows
    expect(container.querySelectorAll("[data-testid]").length).toBe(1);
  });

  it("clicking a chart thumbnail opens the full-size view", () => {
    renderPage();
    fireEvent.click(screen.getByTitle("点击查看"));
    expect(screen.getByText("全屏查看页探针")).toBeInTheDocument();
  });

  it("sorts rows by updated time ascending on header click", () => {
    renderPage();
    fireEvent.click(screen.getByText("更新时间"));
    // asc: 月度退款柱状图 (08-01) before 退款明细表 (08-02)
    const rows = screen.getAllByRole("row").slice(1); // skip header
    expect(within(rows[0]).getByText("月度退款柱状图")).toBeInTheDocument();
    expect(within(rows[1]).getByText("退款明细表")).toBeInTheDocument();
  });

  it("refresh button triggers list refetch", () => {
    renderPage();
    refetchListMock.mockClear();
    fireEvent.click(screen.getByText("刷新"));
    expect(refetchListMock).toHaveBeenCalled();
  });

  it("delete requires confirmation and passes the id on confirm", () => {
    renderPage();
    const deleteButtons = screen.getAllByText("删除");
    fireEvent.click(deleteButtons[0]);

    // Confirmation dialog shows the visualization name
    expect(screen.getByText(/确定要删除可视化「月度退款柱状图」吗？/)).toBeInTheDocument();

    // Cancel closes the dialog without deleting
    fireEvent.click(screen.getByText("取消"));
    expect(screen.queryByText(/此操作不可撤销/)).not.toBeInTheDocument();
    expect(deleteMutateMock).not.toHaveBeenCalled();

    // Confirm calls the delete mutation with the id
    fireEvent.click(deleteButtons[0]);
    fireEvent.click(screen.getByText("确定"));
    expect(deleteMutateMock).toHaveBeenCalledWith("viz-bar", expect.anything());
  });
});
