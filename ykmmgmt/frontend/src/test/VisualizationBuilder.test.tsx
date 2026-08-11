import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { VisualizationBuilderProvider } from "@/contexts/VisualizationBuilderContext";
import { DashboardBuilderProvider } from "@/contexts/DashboardBuilderContext";
import VisualizationBuilderPage from "@/pages/VisualizationBuilderPage";

// Mock the hooks
vi.mock("@/hooks/useViews", () => ({
  useViews: () => ({
    data: [
      {
        id: "view-1",
        name: "测试视图",
        description: "测试描述",
        created_at: "2026-01-01",
        updated_at: "2026-01-01",
      },
    ],
    isLoading: false,
  }),
  useViewFullData: () => ({
    data: {
      columns: ["id", "amount", "date"],
      rows: [
        { id: 1, amount: 100, date: "2026-01-01" },
        { id: 2, amount: 200, date: "2026-01-02" },
      ],
      total: 2,
      page: 1,
      size: 2,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/hooks/useVisualizations", () => ({
  useVisualizations: () => ({ data: [], isLoading: false }),
  useVisualization: () => ({ data: undefined, isLoading: false }),
  useCreateVisualization: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateVisualization: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

// Mock html2canvas
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

function renderPage(initialRoute = "/visualizations/builder") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <VisualizationBuilderProvider>
          <DashboardBuilderProvider>
            <VisualizationBuilderPage />
          </DashboardBuilderProvider>
        </VisualizationBuilderProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("VisualizationBuilderPage", () => {
  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("可视化构建器")).toBeInTheDocument();
  });

  it("renders name input", () => {
    renderPage();
    expect(screen.getByPlaceholderText("输入可视化名称")).toBeInTheDocument();
  });

  it("renders view selector", () => {
    renderPage();
    expect(screen.getByText("数据视图")).toBeInTheDocument();
  });

  it("renders chart type selector with all 8 types", () => {
    renderPage();
    expect(screen.getByText("表格")).toBeInTheDocument();
    expect(screen.getByText("KPI 卡片")).toBeInTheDocument();
    expect(screen.getByText("柱状图")).toBeInTheDocument();
    expect(screen.getByText("折线图")).toBeInTheDocument();
    expect(screen.getByText("饼图")).toBeInTheDocument();
    expect(screen.getByText("散点图")).toBeInTheDocument();
    expect(screen.getByText("直方图")).toBeInTheDocument();
    expect(screen.getByText("箱线图")).toBeInTheDocument();
  });

  it("renders color theme picker", () => {
    renderPage();
    expect(screen.getByText("颜色主题")).toBeInTheDocument();
    expect(screen.getByText("默认")).toBeInTheDocument();
    expect(screen.getByText("暖色")).toBeInTheDocument();
    expect(screen.getByText("冷色")).toBeInTheDocument();
  });

  it("renders save button", () => {
    renderPage();
    expect(screen.getByText("保存")).toBeInTheDocument();
  });

  it("renders export and share buttons", () => {
    renderPage();
    expect(screen.getByText("导出 PNG")).toBeInTheDocument();
    expect(screen.getByText("复制链接")).toBeInTheDocument();
  });

  it("renders preview section", () => {
    renderPage();
    expect(screen.getByText("预览")).toBeInTheDocument();
  });

  it("shows placeholder when no view selected", () => {
    renderPage();
    expect(screen.getByText("请先选择数据视图")).toBeInTheDocument();
  });

  it("shows paginated table preview when a view is selected via query param", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    expect(screen.getByText(/共 2 行 · 第 1\/1 页/)).toBeInTheDocument();
    expect(screen.getByText("上一页")).toBeInTheDocument();
    expect(screen.getByText("下一页")).toBeInTheDocument();
  });

  it("opens the zoom popup and closes it", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    fireEvent.click(screen.getByTitle("放大查看"));
    expect(screen.getByText("可视化预览")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("关闭"));
  });

  it("shows the histogram config panel with bins input when 直方图 is selected", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    fireEvent.click(screen.getByText("直方图"));
    expect(screen.getByText("直方图配置")).toBeInTheDocument();
    expect(screen.getByText("分箱数（可选）")).toBeInTheDocument();
    expect(screen.getByText("数值列（可多选）")).toBeInTheDocument();
  });

  it("shows the boxplot config panel when 箱线图 is selected", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    fireEvent.click(screen.getByText("箱线图"));
    expect(screen.getByText("箱线图配置")).toBeInTheDocument();
    expect(screen.getByText("分类列（可选）")).toBeInTheDocument();
    expect(screen.getByText("数值列")).toBeInTheDocument();
  });

  it("shows the bar aggregation selector when 柱状图 is selected", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    fireEvent.click(screen.getByText("柱状图"));
    expect(screen.getByText("柱状图配置")).toBeInTheDocument();
    expect(screen.getByText("聚合方式")).toBeInTheDocument();
  });

  it("shows the pie aggregation selector when 饼图 is selected", () => {
    renderPage("/visualizations/builder?view_id=view-1");
    fireEvent.click(screen.getByText("饼图"));
    expect(screen.getByText("饼图配置")).toBeInTheDocument();
    expect(screen.getByText("聚合方式")).toBeInTheDocument();
  });
});
