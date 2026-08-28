import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";
import { DashboardExportCanvas } from "@/components/dashboard/DashboardExportCanvas";
import type { DashboardResponse } from "@/hooks/useDashboards";

// ── Fixtures ───────────────────────────────────────────────────────────────

const DASHBOARD: DashboardResponse = {
  id: "dash-1",
  name: "运营总览",
  description: "核心指标",
  layout_json: [
    { i: "t1", tile_type: "visualization", visualization_id: "viz-1", x: 0, y: 0, w: 6, h: 4 },
    { i: "t2", tile_type: "text", content: "## 说明", x: 6, y: 0, w: 6, h: 2 },
  ],
  created_at: "2026-08-01T10:00:00",
  updated_at: "2026-08-01T10:00:00",
};

const TILE_DATA = {
  columns: ["月份", "金额"],
  rows: [
    { 月份: "2026-06", 金额: 100 },
    { 月份: "2026-07", 金额: 200 },
  ],
  chart_type: "line",
  config_json: { x_column: "月份", y_columns: ["金额"], title: "" },
};

// Mutable so tests can switch between cached / loading states
let dashboardState: { data: DashboardResponse | undefined; isLoading: boolean; isError: boolean } =
  {
    data: DASHBOARD,
    isLoading: false,
    isError: false,
  };
let tileDataState: { data: typeof TILE_DATA | undefined; isLoading: boolean } = {
  data: TILE_DATA,
  isLoading: false,
};

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useDashboards", async () => {
  const actual =
    await vi.importActual<typeof import("@/hooks/useDashboards")>("@/hooks/useDashboards");
  return {
    ...actual,
    useDashboard: () => dashboardState,
    useKpiTileData: () => ({ data: undefined, isLoading: false }),
  };
});

vi.mock("@/hooks/useVisualizations", () => ({
  useVisualizationTileData: () => tileDataState,
}));

// Grid layout isn't under test — render tiles in plain flow
vi.mock("react-grid-layout", () => ({
  GridLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
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

// ── Tests ──────────────────────────────────────────────────────────────────
// Regression tests for the "second dashboard export hangs forever" bug: a
// mount-time "reset readiness" effect in the canvas used to wipe the
// readyTiles increments that child tiles had already made (child effects run
// before parent effects), so onReady never fired and the export queue stayed
// stuck at "正在导出 0/1…".

describe("DashboardExportCanvas", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    dashboardState = { data: DASHBOARD, isLoading: false, isError: false };
    tileDataState = { data: TILE_DATA, isLoading: false };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fires onReady(true) on mount when dashboard and tile data are cached", () => {
    // Fully cached = the second-export scenario: tiles mount with data and
    // notify immediately, before the parent's effects run
    const onReady = vi.fn();
    render(<DashboardExportCanvas dashboardId="dash-1" onReady={onReady} />);

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(true);
  });

  it("fires onReady(false) when the dashboard itself failed to load", () => {
    dashboardState = { data: undefined, isLoading: false, isError: true };
    const onReady = vi.fn();
    render(<DashboardExportCanvas dashboardId="dash-1" onReady={onReady} />);

    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(false);
  });

  it("waits for the dashboard and tile data to load before firing onReady", () => {
    dashboardState = { data: undefined, isLoading: true, isError: false };
    const onReady = vi.fn();
    const { rerender } = render(<DashboardExportCanvas dashboardId="dash-1" onReady={onReady} />);

    // Dashboard arrives but the tile is still loading — must not fire yet
    dashboardState = { data: DASHBOARD, isLoading: false, isError: false };
    tileDataState = { data: undefined, isLoading: true };
    rerender(<DashboardExportCanvas dashboardId="dash-1" onReady={onReady} />);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onReady).not.toHaveBeenCalled();

    // Tile data arrives — settle timer schedules and fires once
    tileDataState = { data: TILE_DATA, isLoading: false };
    rerender(<DashboardExportCanvas dashboardId="dash-1" onReady={onReady} />);
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(true);
  });
});
