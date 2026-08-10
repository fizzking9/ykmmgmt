/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react";

// ── Chart types ─────────────────────────────────────────────────────────────

export type ChartType =
  "table" | "kpi_card" | "bar" | "line" | "pie" | "scatter" | "histogram" | "boxplot";

export const CHART_TYPES: { value: ChartType; label: string }[] = [
  { value: "table", label: "表格" },
  { value: "kpi_card", label: "KPI 卡片" },
  { value: "bar", label: "柱状图" },
  { value: "line", label: "折线图" },
  { value: "pie", label: "饼图" },
  { value: "scatter", label: "散点图" },
  { value: "histogram", label: "直方图" },
  { value: "boxplot", label: "箱线图" },
];

// ── Color themes ────────────────────────────────────────────────────────────

export interface ColorTheme {
  name: string;
  label: string;
  colors: string[];
}

export const COLOR_THEMES: ColorTheme[] = [
  {
    name: "default",
    label: "默认",
    colors: ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea", "#0891b2"],
  },
  {
    name: "warm",
    label: "暖色",
    colors: ["#ef4444", "#f97316", "#eab308", "#fb923c", "#fbbf24", "#fca5a5"],
  },
  {
    name: "cool",
    label: "冷色",
    colors: ["#3b82f6", "#06b6d4", "#8b5cf6", "#6366f1", "#0ea5e9", "#a78bfa"],
  },
  {
    name: "nature",
    label: "自然",
    colors: ["#16a34a", "#65a30d", "#059669", "#0d9488", "#84cc16", "#34d399"],
  },
  {
    name: "monochrome",
    label: "单色",
    colors: ["#1e293b", "#475569", "#64748b", "#94a3b8", "#334155", "#0f172a"],
  },
];

// ── Number format ───────────────────────────────────────────────────────────

export interface NumberFormat {
  decimals: number;
  thousandsSeparator: boolean;
  currencyPrefix: string;
}

export const DEFAULT_NUMBER_FORMAT: NumberFormat = {
  decimals: 2,
  thousandsSeparator: true,
  currencyPrefix: "",
};

// ── State ───────────────────────────────────────────────────────────────────

export interface VisualizationBuilderState {
  name: string;
  description: string;
  viewId: string | null;
  chartType: ChartType;
  configJson: Record<string, unknown>;
  colorTheme: string;
  numberFormat: NumberFormat;
  editingId: string | null;
}

// ── Default configs per chart type ──────────────────────────────────────────

export function getDefaultConfig(chartType: ChartType): Record<string, unknown> {
  switch (chartType) {
    case "table":
      return { visible_columns: [], sort_column: "", sort_direction: "asc" };
    case "kpi_card":
      return {
        value_column: "",
        label: "",
        aggregation: "SUM",
        date_column: "",
        granularity: "day",
      };
    case "bar":
    case "line":
    case "scatter":
      return {
        x_column: "",
        y_columns: [],
        group_by_column: "",
        title: "",
        x_label: "",
        y_label: "",
        // Bar-only: aggregation applied over each category (bar x is categorical)
        aggregation: "SUM",
        // Time-series options (only relevant when x_column is a date column)
        // "none" = no aggregation, show raw date/datetime values
        time_granularity: "none",
        time_aggregation: "SUM",
        show_time: false,
        enable_brush: true,
        date_range_start: "",
        date_range_end: "",
        // Bar-only: stack grouped bars instead of side-by-side
        stack_bars: false,
      };
    case "pie":
      return { label_column: "", value_column: "", title: "" };
    case "histogram":
      // Distribution of one or more numeric columns
      return { columns: [], bins: 20, title: "", x_label: "", y_label: "" };
    case "boxplot":
      // Five-number summary of a numeric column, optionally split by category
      return { category_column: "", value_column: "", title: "", x_label: "", y_label: "" };
  }
}

// ── Context value ───────────────────────────────────────────────────────────

export interface VisualizationBuilderContextValue {
  state: VisualizationBuilderState;
  setName: (name: string) => void;
  setDescription: (desc: string) => void;
  setViewId: (id: string | null) => void;
  setChartType: (type: ChartType) => void;
  setConfigJson: (config: Record<string, unknown>) => void;
  updateConfigKey: (key: string, value: unknown) => void;
  setColorTheme: (theme: string) => void;
  setNumberFormat: (format: NumberFormat) => void;
  setEditingId: (id: string | null) => void;
  resetState: () => void;
  loadVisualization: (viz: {
    id: string;
    name: string;
    view_id: string;
    chart_type: string;
    config_json: Record<string, unknown>;
  }) => void;
}

// ── Context ─────────────────────────────────────────────────────────────────

const VisualizationBuilderContext = createContext<VisualizationBuilderContextValue | null>(null);

const INITIAL_STATE: VisualizationBuilderState = {
  name: "",
  description: "",
  viewId: null,
  chartType: "table",
  configJson: getDefaultConfig("table"),
  colorTheme: "default",
  numberFormat: DEFAULT_NUMBER_FORMAT,
  editingId: null,
};

export function VisualizationBuilderProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<VisualizationBuilderState>(INITIAL_STATE);

  const setName = useCallback((name: string) => {
    setState((prev) => ({ ...prev, name }));
  }, []);

  const setDescription = useCallback((desc: string) => {
    setState((prev) => ({ ...prev, description: desc }));
  }, []);

  const setViewId = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, viewId: id }));
  }, []);

  const setChartType = useCallback((type: ChartType) => {
    setState((prev) => ({
      ...prev,
      chartType: type,
      configJson: getDefaultConfig(type),
    }));
  }, []);

  const setConfigJson = useCallback((config: Record<string, unknown>) => {
    setState((prev) => ({ ...prev, configJson: config }));
  }, []);

  const updateConfigKey = useCallback((key: string, value: unknown) => {
    setState((prev) => ({
      ...prev,
      configJson: { ...prev.configJson, [key]: value },
    }));
  }, []);

  const setColorTheme = useCallback((theme: string) => {
    setState((prev) => ({ ...prev, colorTheme: theme }));
  }, []);

  const setNumberFormat = useCallback((format: NumberFormat) => {
    setState((prev) => ({ ...prev, numberFormat: format }));
  }, []);

  const setEditingId = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, editingId: id }));
  }, []);

  const resetState = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const loadVisualization = useCallback(
    (viz: {
      id: string;
      name: string;
      view_id: string;
      chart_type: string;
      config_json: Record<string, unknown>;
    }) => {
      setState({
        name: viz.name,
        description: "",
        viewId: viz.view_id,
        chartType: viz.chart_type as ChartType,
        configJson: viz.config_json,
        colorTheme: (viz.config_json._colorTheme as string) || "default",
        numberFormat: (viz.config_json._numberFormat as NumberFormat) || DEFAULT_NUMBER_FORMAT,
        editingId: viz.id,
      });
    },
    [],
  );

  const value = useMemo(
    () => ({
      state,
      setName,
      setDescription,
      setViewId,
      setChartType,
      setConfigJson,
      updateConfigKey,
      setColorTheme,
      setNumberFormat,
      setEditingId,
      resetState,
      loadVisualization,
    }),
    [
      state,
      setName,
      setDescription,
      setViewId,
      setChartType,
      setConfigJson,
      updateConfigKey,
      setColorTheme,
      setNumberFormat,
      setEditingId,
      resetState,
      loadVisualization,
    ],
  );

  return (
    <VisualizationBuilderContext.Provider value={value}>
      {children}
    </VisualizationBuilderContext.Provider>
  );
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useVisualizationBuilderContext() {
  const ctx = useContext(VisualizationBuilderContext);
  if (!ctx) {
    throw new Error(
      "useVisualizationBuilderContext must be used within VisualizationBuilderProvider",
    );
  }
  return ctx;
}
