import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";
import { VisualizationExportCanvas } from "@/components/visualization/VisualizationExportCanvas";
import type { VisualizationListResponse } from "@/hooks/useVisualizations";

// ── Fixtures ───────────────────────────────────────────────────────────────

const VIZ: VisualizationListResponse = {
  id: "viz-bar",
  name: "月度退款柱状图",
  view_id: "view-1",
  chart_type: "bar",
  created_at: "2026-08-01T10:00:00",
  updated_at: "2026-08-01T10:00:00",
};

const CACHED_DATA = {
  columns: ["月份", "金额"],
  rows: [
    { 月份: "2026-06", 金额: 100 },
    { 月份: "2026-07", 金额: 200 },
  ],
  chart_type: "bar",
  config_json: { x_column: "月份", y_columns: ["金额"], title: "" },
};

// Mutable so tests can switch between cached / loading / error states
let dataState: {
  data: typeof CACHED_DATA | undefined;
  isLoading: boolean;
  isError: boolean;
} = { data: CACHED_DATA, isLoading: false, isError: false };

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useVisualizations", () => ({
  useVisualizationData: () => dataState,
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
// The settle timer must fire under React StrictMode's dev-only
// mount → unmount → remount effect cycle. Regression test for the bug where
// a ref-guard set BEFORE the timer fired blocked re-scheduling after the
// cleanup cancelled it, so onReady never fired and the export queue hung
// in "正在导出" forever.

describe("VisualizationExportCanvas", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    dataState = { data: CACHED_DATA, isLoading: false, isError: false };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fires onReady(true) under StrictMode when data is already cached", () => {
    // Cached data = the same query the list-page thumbnail already fetched
    // (isLoading is false on the very first render)
    const onReady = vi.fn();
    render(
      <React.StrictMode>
        <VisualizationExportCanvas viz={VIZ} onReady={onReady} />
      </React.StrictMode>,
    );

    // No premature fire before the settle delay
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(onReady).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(true);
  });

  it("fires onReady(false) when the data failed to load", () => {
    dataState = { data: undefined, isLoading: false, isError: true };
    const onReady = vi.fn();
    render(<VisualizationExportCanvas viz={VIZ} onReady={onReady} />);

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(false);
  });

  it("waits for loading to finish before firing onReady", () => {
    const onReady = vi.fn();
    const { rerender } = render(<VisualizationExportCanvas viz={VIZ} onReady={onReady} />);

    // Still loading — settle timer must not be scheduled yet
    dataState = { data: undefined, isLoading: true, isError: false };
    rerender(<VisualizationExportCanvas viz={VIZ} onReady={onReady} />);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(onReady).not.toHaveBeenCalled();

    // Data arrives — timer schedules and fires once
    dataState = { data: CACHED_DATA, isLoading: false, isError: false };
    rerender(<VisualizationExportCanvas viz={VIZ} onReady={onReady} />);
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledWith(true);
  });
});
