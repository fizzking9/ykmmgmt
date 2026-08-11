/* eslint-disable react-refresh/only-export-components */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useViews, useViewFullData } from "@/hooks/useViews";
import {
  useVisualization,
  useVisualizations,
  useCreateVisualization,
  useUpdateVisualization,
} from "@/hooks/useVisualizations";
import {
  useVisualizationBuilderContext,
  CHART_TYPES,
  COLOR_THEMES,
  type ChartType,
} from "@/contexts/VisualizationBuilderContext";
import { useDashboardBuilderContext } from "@/contexts/DashboardBuilderContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart2,
  BarChart3,
  Box,
  LineChart,
  PieChart,
  ScatterChart,
  Table2,
  CreditCard,
  Save,
  Download,
  Link2,
  Loader2,
  RotateCcw,
  Eye,
  Maximize2,
  X,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";
import html2canvas from "html2canvas";
import {
  BarChart,
  Bar,
  LineChart as ReLineChart,
  Line,
  PieChart as RePieChart,
  Pie,
  Cell,
  ScatterChart as ReScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Brush,
  ResponsiveContainer,
} from "recharts";

// ── Chart type icons ────────────────────────────────────────────────────────

const CHART_ICONS: Record<ChartType, React.ReactNode> = {
  table: <Table2 className="h-6 w-6" />,
  kpi_card: <CreditCard className="h-6 w-6" />,
  bar: <BarChart3 className="h-6 w-6" />,
  line: <LineChart className="h-6 w-6" />,
  pie: <PieChart className="h-6 w-6" />,
  scatter: <ScatterChart className="h-6 w-6" />,
  histogram: <BarChart2 className="h-6 w-6" />,
  boxplot: <Box className="h-6 w-6" />,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function isNumericColumn(values: unknown[]): boolean {
  const sample = values.filter((v) => v != null).slice(0, 20);
  if (sample.length === 0) return false;
  return sample.every((v) => !isNaN(Number(v)));
}

export function isDateColumn(values: unknown[]): boolean {
  const sample = values.filter((v) => v != null).slice(0, 20);
  if (sample.length === 0) return false;
  return sample.every((v) => {
    if (typeof v !== "string") return false;
    // Check for ISO date/datetime patterns
    return /^\d{4}-\d{2}-\d{2}/.test(v) || !isNaN(Date.parse(v));
  });
}

/** Normalize category values: null/empty becomes 未知 so every series has a readable label. */
function categoryValue(row: Record<string, unknown>, column: string): string {
  return String(row[column] ?? "") || "未知";
}

// ── Chart styling constants (industrial-standard defaults) ────────────────

const AXIS_TICK = { fontSize: 11, fill: "#64748b" };
const AXIS_LINE_STROKE = "#cbd5e1";
const GRID_STROKE = "#e2e8f0";
const TOOLTIP_STYLE: React.CSSProperties = {
  fontSize: 12,
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
};
const LEGEND_STYLE: React.CSSProperties = {
  fontSize: 12,
  cursor: "pointer",
  paddingBottom: 8,
};

/** Compact number for Y-axis ticks: 1.2万 / 3.5亿 */
function trimZero(n: number): string {
  const s = Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1);
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

function compactNumber(value: unknown): string {
  const num = Number(value);
  if (isNaN(num)) return String(value ?? "");
  const abs = Math.abs(num);
  if (abs >= 1e8) return `${trimZero(num / 1e8)}亿`;
  if (abs >= 1e4) return `${trimZero(num / 1e4)}万`;
  return trimZero(num);
}

// ── Max categories shown per chart; the rest are merged into 其他 ─────────

const MAX_CATEGORIES = 10;

/** Keep only the top-N most frequent categories; remap the rest to 其他. */
function limitCategories(
  rows: Record<string, unknown>[],
  groupByColumn: string,
): { rows: Record<string, unknown>[]; categories: string[] } {
  if (!groupByColumn) return { rows, categories: [] };
  const counts = new Map<string, number>();
  for (const row of rows) {
    const v = categoryValue(row, groupByColumn);
    counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  const top = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_CATEGORIES)
    .map(([c]) => c)
    .sort((a, b) => a.localeCompare(b));
  if (counts.size <= MAX_CATEGORIES) {
    return { rows, categories: top };
  }
  const topSet = new Set(top);
  const remapped = rows.map((r) => {
    const v = categoryValue(r, groupByColumn);
    return topSet.has(v) ? r : { ...r, [groupByColumn]: "其他" };
  });
  return { rows: remapped, categories: [...top, "其他"] };
}

/** Hook for legend click-to-toggle series visibility. */
function useSeriesToggle() {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const toggle = useCallback((key: string) => {
    setHidden((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);
  return { hidden, toggle };
}

function formatNumber(
  value: unknown,
  decimals: number,
  thousandsSeparator: boolean,
  currencyPrefix: string,
): string {
  if (value == null) return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  let formatted = num.toFixed(decimals);
  if (thousandsSeparator) {
    const parts = formatted.split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    formatted = parts.join(".");
  }
  return currencyPrefix + formatted;
}

// ── Categorical aggregation (bar chart) ────────────────────────────────

/** Group rows by x category (and optional group column), aggregate each Y column. */
function aggregateCategoricalRows(
  rows: Record<string, unknown>[],
  xColumn: string,
  yColumns: string[],
  groupByColumn: string,
  method: string,
): Record<string, unknown>[] {
  const buckets = new Map<
    string,
    { x: string; cat: string; bucketRows: Record<string, unknown>[] }
  >();
  for (const row of rows) {
    const x = String(row[xColumn] ?? "");
    const cat = groupByColumn ? categoryValue(row, groupByColumn) : "";
    const key = groupByColumn ? `${x}||${cat}` : x;
    const bucket = buckets.get(key) ?? { x, cat, bucketRows: [] };
    bucket.bucketRows.push(row);
    buckets.set(key, bucket);
  }
  const out: Record<string, unknown>[] = [];
  for (const { x, cat, bucketRows } of buckets.values()) {
    const outRow: Record<string, unknown> = { [xColumn]: x };
    if (groupByColumn && cat) outRow[groupByColumn] = cat;
    for (const yCol of yColumns) {
      if (method === "COUNT") {
        // COUNT counts rows regardless of the Y value
        outRow[yCol] = bucketRows.length;
      } else {
        const values = bucketRows.map((r) => Number(r[yCol])).filter((v) => !isNaN(v));
        outRow[yCol] = aggregateValues(values, method);
      }
    }
    out.push(outRow);
  }
  out.sort((a, b) => String(a[xColumn]).localeCompare(String(b[xColumn])));
  return out;
}

// ── Histogram binning ──────────────────────────────────────────────────

/** Compute shared bins across one or more numeric columns; Y = count per bin. */
function buildHistogramData(
  rows: Record<string, unknown>[],
  columns: string[],
  binCount: number,
): Record<string, unknown>[] {
  const valuesByColumn = new Map<string, number[]>();
  let min = Infinity;
  let max = -Infinity;
  for (const col of columns) {
    const values: number[] = [];
    for (const row of rows) {
      const raw = row[col];
      if (raw == null) continue;
      const v = Number(raw);
      if (isNaN(v)) continue;
      values.push(v);
      if (v < min) min = v;
      if (v > max) max = v;
    }
    valuesByColumn.set(col, values);
  }
  if (!isFinite(min) || !isFinite(max)) return [];
  // Degenerate case: all values identical — create a single-width bin around it
  if (min === max) {
    min -= 0.5;
    max += 0.5;
  }
  const width = (max - min) / binCount;
  const data: Record<string, unknown>[] = Array.from({ length: binCount }, (_, i) => {
    const row: Record<string, unknown> = {
      __bin: i,
      __start: min + i * width,
      __end: min + (i + 1) * width,
    };
    for (const col of columns) row[col] = 0;
    return row;
  });
  for (const col of columns) {
    for (const v of valuesByColumn.get(col) ?? []) {
      let idx = Math.floor((v - min) / width);
      if (idx >= binCount) idx = binCount - 1; // include the max value in the last bin
      data[idx][col] = (data[idx][col] as number) + 1;
    }
  }
  return data;
}

// ── Boxplot five-number summary ────────────────────────────────────────

interface BoxSummary {
  cat: string;
  count: number;
  q1: number;
  median: number;
  q3: number;
  whiskerLow: number;
  whiskerHigh: number;
  outliers: number[];
  /** Range-bar value for recharts: [q1, q3] */
  range: [number, number];
}

/** Linear-interpolation quantile on an ascending-sorted array. */
function quantileSorted(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

/** Five-number summary with 1.5×IQR whiskers and explicit outliers. */
function computeBoxSummary(values: number[], cat: string): BoxSummary {
  const sorted = [...values].sort((a, b) => a - b);
  const q1 = quantileSorted(sorted, 0.25);
  const median = quantileSorted(sorted, 0.5);
  const q3 = quantileSorted(sorted, 0.75);
  const iqr = q3 - q1;
  const lowFence = q1 - 1.5 * iqr;
  const highFence = q3 + 1.5 * iqr;
  const inliers = sorted.filter((v) => v >= lowFence && v <= highFence);
  const outliers = sorted.filter((v) => v < lowFence || v > highFence);
  return {
    cat,
    count: sorted.length,
    q1,
    median,
    q3,
    whiskerLow: inliers.length ? inliers[0] : q1,
    whiskerHigh: inliers.length ? inliers[inliers.length - 1] : q3,
    outliers,
    range: [q1, q3],
  };
}

// ── Line/scatter symbols for class encoding ────────────────────────────

type SymbolShape = "circle" | "square" | "triangle" | "diamond" | "cross" | "star";

/** Beyond this many points per line, per-point symbols are dropped for performance. */
const LINE_DOT_MAX_POINTS = 500;

const SYMBOL_SHAPES: SymbolShape[] = ["circle", "square", "triangle", "diamond", "cross", "star"];

function starPoints(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 10; i++) {
    const radius = i % 2 === 0 ? r : r * 0.45;
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    pts.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`);
  }
  return pts.join(" ");
}

/** Render a small symbol centered at (cx, cy). */
function symbolElement(
  shape: SymbolShape,
  cx: number,
  cy: number,
  r: number,
  fill: string,
  key: string,
) {
  switch (shape) {
    case "circle":
      return <circle key={key} cx={cx} cy={cy} r={r} fill={fill} />;
    case "square":
      return <rect key={key} x={cx - r} y={cy - r} width={r * 2} height={r * 2} fill={fill} />;
    case "triangle":
      return (
        <polygon
          key={key}
          points={`${cx},${cy - r} ${cx - r},${cy + r} ${cx + r},${cy + r}`}
          fill={fill}
        />
      );
    case "diamond":
      return (
        <polygon
          key={key}
          points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`}
          fill={fill}
        />
      );
    case "cross":
      return (
        <g key={key} stroke={fill} strokeWidth={2} strokeLinecap="round">
          <line x1={cx - r} y1={cy - r} x2={cx + r} y2={cy + r} />
          <line x1={cx - r} y1={cy + r} x2={cx + r} y2={cy - r} />
        </g>
      );
    case "star":
      return <polygon key={key} points={starPoints(cx, cy, r + 1)} fill={fill} />;
  }
}

/** Line dot renderer drawing a per-class symbol at each data point. */
function makeLineDot(shape: SymbolShape, color: string) {
  return function renderDot(props: { cx?: number; cy?: number; index?: number }) {
    const { cx, cy, index } = props;
    if (cx == null || cy == null || isNaN(cx) || isNaN(cy)) {
      return <g key={`dot-${index}`} />;
    }
    return symbolElement(shape, cx, cy, 3.5, color, `dot-${index}`);
  };
}

// ── Component ───────────────────────────────────────────────────────────────

export default function VisualizationBuilderPage() {
  const { id } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const { data: viewsList } = useViews();
  const { data: existingViz } = useVisualization(id);
  const { data: vizList } = useVisualizations();
  const createViz = useCreateVisualization();
  const updateViz = useUpdateVisualization();

  const vizBuilder = useVisualizationBuilderContext();
  const { state } = vizBuilder;

  // When the user jumps here from a dashboard tile's "配置可视化" button,
  // the dashboard draft lives in DashboardBuilderContext (above the router)
  // — offer a way back without losing it.
  const dashboardBuilder = useDashboardBuilderContext();
  const hasDashboardDraft =
    dashboardBuilder.state.tiles.length > 0 ||
    !!dashboardBuilder.state.editingId ||
    dashboardBuilder.state.name.trim() !== "";
  const backToDashboardBuilder = () => {
    const draftId = dashboardBuilder.state.editingId;
    navigate(draftId ? `/dashboards/builder/${draftId}` : "/dashboards/builder");
  };

  // Fetch full view data for visualization preview (all rows, not paginated)
  const {
    data: viewData,
    isLoading: dataLoading,
    isError: dataError,
  } = useViewFullData(state.viewId ?? undefined);

  const previewRef = useRef<HTMLDivElement>(null);
  const loadedVizIdRef = useRef<string | null>(null);

  // Name-conflict confirmation dialog (save acts as update when the name exists)
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    targetId: string;
    targetName: string;
  } | null>(null);

  // Whether a PNG export is in progress (hides interactive controls like Brush)
  const [exporting, setExporting] = useState(false);
  // Whether the zoom-in popup is open
  const [zoomOpen, setZoomOpen] = useState(false);

  // ── Auto-select view from query param ──────────────────────────────────
  useEffect(() => {
    const queryViewId = searchParams.get("view_id");
    if (queryViewId && !state.viewId && !id) {
      vizBuilder.setViewId(queryViewId);
    }
  }, [searchParams, state.viewId, id, vizBuilder]);

  // ── Load existing visualization in edit mode ───────────────────────────
  useEffect(() => {
    if (existingViz && loadedVizIdRef.current !== existingViz.id) {
      loadedVizIdRef.current = existingViz.id;
      vizBuilder.loadVisualization(existingViz);
    }
  }, [existingViz, vizBuilder]);

  // ── Columns from view data ─────────────────────────────────────────────
  const columns = useMemo(() => viewData?.columns ?? [], [viewData]);
  const rows = useMemo(() => viewData?.rows ?? [], [viewData]);

  const numericColumns = useMemo(() => {
    if (!rows.length || !columns.length) return [];
    return columns.filter((col) => isNumericColumn(rows.map((r) => r[col])));
  }, [columns, rows]);

  const dateColumns = useMemo(() => {
    if (!rows.length || !columns.length) return [];
    return columns.filter((col) => isDateColumn(rows.map((r) => r[col])));
  }, [columns, rows]);

  // ── Selected view display name ─────────────────────────────────────────
  const selectedViewName = useMemo(() => {
    if (!state.viewId || !viewsList) return "";
    const found = viewsList.find((v) => v.id === state.viewId);
    return found ? found.name : "";
  }, [state.viewId, viewsList]);

  // ── Theme colors ───────────────────────────────────────────────────────
  const themeColors = useMemo(() => {
    const theme = COLOR_THEMES.find((t) => t.name === state.colorTheme);
    return theme?.colors ?? COLOR_THEMES[0].colors;
  }, [state.colorTheme]);

  // ── Handlers ───────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (!state.name.trim()) {
      toast.error("请输入可视化名称");
      return;
    }
    if (!state.viewId) {
      toast.error("请选择数据视图");
      return;
    }

    const configToSave = {
      ...state.configJson,
      _colorTheme: state.colorTheme,
      _numberFormat: state.numberFormat,
    };
    const trimmedName = state.name.trim();

    // Check if a visualization with this name already exists
    const existingWithName = vizList?.find((v) => v.name === trimmedName);

    if (existingWithName) {
      // Name already exists — confirm modification
      setConfirmDialog({
        open: true,
        targetId: existingWithName.id,
        targetName: trimmedName,
      });
      return;
    }

    // Name doesn't exist — create new visualization
    try {
      const result = await createViz.mutateAsync({
        name: trimmedName,
        view_id: state.viewId,
        chart_type: state.chartType,
        config_json: configToSave,
      });
      vizBuilder.setEditingId(result.id);
      loadedVizIdRef.current = result.id;
      navigate(`/visualizations/builder/${result.id}`, { replace: true });
    } catch {
      // error handled by mutation
    }
  }, [state, createViz, navigate, vizBuilder, vizList]);

  const handleConfirmUpdate = useCallback(async () => {
    if (!confirmDialog || !state.viewId) return;
    const configToSave = {
      ...state.configJson,
      _colorTheme: state.colorTheme,
      _numberFormat: state.numberFormat,
    };
    try {
      const result = await updateViz.mutateAsync({
        id: confirmDialog.targetId,
        name: state.name.trim(),
        view_id: state.viewId,
        chart_type: state.chartType,
        config_json: configToSave,
      });
      setConfirmDialog(null);
      vizBuilder.setEditingId(result.id);
      loadedVizIdRef.current = result.id;
      navigate(`/visualizations/builder/${result.id}`, { replace: true });
    } catch {
      // error handled by mutation
    }
  }, [confirmDialog, state, updateViz, navigate, vizBuilder]);

  const handleExportPng = useCallback(async () => {
    if (!previewRef.current) return;
    try {
      // Hide interactive controls (Brush) during capture
      setExporting(true);
      // Wait for React to re-render the preview without the brush
      await new Promise((r) => setTimeout(r, 150));
      const canvas = await html2canvas(previewRef.current, {
        backgroundColor: "#ffffff",
        scale: 2,
      });
      const link = document.createElement("a");
      link.download = `${state.name || "可视化"}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      toast.success("PNG 导出成功（不含缩放条）");
    } catch {
      toast.error("PNG 导出失败");
    } finally {
      setExporting(false);
    }
  }, [state.name]);

  const handleCopyLink = useCallback(() => {
    const url = state.editingId
      ? `${window.location.origin}/visualizations/builder/${state.editingId}`
      : window.location.href;
    navigator.clipboard.writeText(url).then(
      () => toast.success("链接已复制到剪贴板"),
      () => toast.error("复制失败"),
    );
  }, [state.editingId]);

  const handleReset = useCallback(() => {
    loadedVizIdRef.current = null;
    vizBuilder.resetState();
    navigate("/visualizations/builder", { replace: true });
  }, [vizBuilder, navigate]);

  const isSaving = createViz.isPending || updateViz.isPending;

  // ── Render chart preview ───────────────────────────────────────────────

  const renderPreview = (opts: { forModal?: boolean } = {}) => {
    if (!state.viewId) {
      return (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          请先选择数据视图
        </div>
      );
    }

    if (dataLoading) {
      return (
        <div className="space-y-2 p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      );
    }

    if (dataError) {
      return <div className="flex h-64 items-center justify-center text-red-600">数据加载失败</div>;
    }

    if (!rows.length) {
      return (
        <div className="flex h-64 items-center justify-center text-muted-foreground">暂无数据</div>
      );
    }

    const config = state.configJson;

    // Brush visibility: user toggle + hidden during PNG export (main preview only)
    const enableBrush = (config.enable_brush as boolean) ?? true;
    const showBrush = opts.forModal ? enableBrush : enableBrush && !exporting;
    const chartHeight = opts.forModal ? 580 : 420;

    switch (state.chartType) {
      case "table":
        return (
          <TablePreview config={config} columns={columns} rows={rows} inModal={opts.forModal} />
        );
      case "kpi_card":
        return (
          <KpiCardPreview
            config={config}
            rows={rows}
            numberFormat={state.numberFormat}
            height={chartHeight}
          />
        );
      case "bar":
        return (
          <BarChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            dateColumns={dateColumns}
            height={chartHeight}
            showBrush={showBrush}
          />
        );
      case "line":
        return (
          <LineChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            dateColumns={dateColumns}
            height={chartHeight}
            showBrush={showBrush}
          />
        );
      case "pie":
        return (
          <PieChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            height={opts.forModal ? 520 : 400}
          />
        );
      case "scatter":
        return (
          <ScatterChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            dateColumns={dateColumns}
            height={chartHeight}
            showBrush={showBrush}
          />
        );
      case "histogram":
        return (
          <HistogramChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            height={chartHeight}
          />
        );
      case "boxplot":
        return (
          <BoxplotChartPreview
            config={config}
            rows={rows}
            colors={themeColors}
            height={chartHeight}
          />
        );
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {hasDashboardDraft && (
            <Button variant="ghost" size="sm" onClick={backToDashboardBuilder}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回看板构建器
            </Button>
          )}
          <h2 className="text-2xl font-bold tracking-tight">可视化构建器</h2>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleExportPng} disabled={!state.viewId}>
            <Download className="mr-1 h-4 w-4" />
            导出 PNG
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopyLink}>
            <Link2 className="mr-1 h-4 w-4" />
            复制链接
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset}>
            <RotateCcw className="mr-1 h-4 w-4" />
            重置
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left panel — Configuration */}
        <div className="space-y-4">
          {/* Name & View Selection */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">基本设置</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">
                  名称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={state.name}
                  onChange={(e) => vizBuilder.setName(e.target.value)}
                  placeholder="输入可视化名称"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  数据视图 <span className="text-red-500">*</span>
                </label>
                <Select
                  value={state.viewId ?? ""}
                  onValueChange={(v) => {
                    if (v) vizBuilder.setViewId(v);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择数据视图">
                      {selectedViewName || undefined}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent
                    align="start"
                    sideOffset={4}
                    alignItemWithTrigger={false}
                    className="bg-background"
                  >
                    {viewsList?.map((v) => (
                      <SelectItem key={v.id} value={v.id}>
                        {v.name}
                        {v.description ? ` — ${v.description}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Chart Type Selector */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">图表类型</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-2">
                {CHART_TYPES.map((ct) => (
                  <button
                    key={ct.value}
                    onClick={() => vizBuilder.setChartType(ct.value)}
                    className={`flex flex-col items-center gap-1 rounded-md border p-3 text-sm transition-colors hover:bg-muted/50 ${
                      state.chartType === ct.value
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-border"
                    }`}
                  >
                    {CHART_ICONS[ct.value]}
                    {ct.label}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Per-chart config */}
          {state.viewId && columns.length > 0 && (
            <ChartConfigPanel
              chartType={state.chartType}
              config={state.configJson}
              columns={columns}
              numericColumns={numericColumns}
              dateColumns={dateColumns}
              onUpdateKey={vizBuilder.updateConfigKey}
            />
          )}

          {/* Color Theme */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">颜色主题</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {COLOR_THEMES.map((theme) => (
                  <button
                    key={theme.name}
                    onClick={() => vizBuilder.setColorTheme(theme.name)}
                    className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                      state.colorTheme === theme.name
                        ? "border-primary bg-primary/5"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex gap-0.5">
                      {theme.colors.slice(0, 4).map((c) => (
                        <div
                          key={c}
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: c }}
                        />
                      ))}
                    </div>
                    {theme.label}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Number Format */}
          {(state.chartType === "kpi_card" ||
            state.chartType === "bar" ||
            state.chartType === "line") && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">数字格式</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium">小数位数</label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={state.numberFormat.decimals}
                      onChange={(e) =>
                        vizBuilder.setNumberFormat({
                          ...state.numberFormat,
                          decimals: parseInt(e.target.value, 10) || 0,
                        })
                      }
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium">千分位</label>
                    <Select
                      value={state.numberFormat.thousandsSeparator ? "yes" : "no"}
                      onValueChange={(v) =>
                        vizBuilder.setNumberFormat({
                          ...state.numberFormat,
                          thousandsSeparator: v === "yes",
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue>
                          {state.numberFormat.thousandsSeparator ? "启用" : "禁用"}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent
                        align="start"
                        sideOffset={4}
                        alignItemWithTrigger={false}
                        className="bg-background"
                      >
                        <SelectItem value="yes">启用</SelectItem>
                        <SelectItem value="no">禁用</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium">货币前缀</label>
                    <input
                      type="text"
                      value={state.numberFormat.currencyPrefix}
                      onChange={(e) =>
                        vizBuilder.setNumberFormat({
                          ...state.numberFormat,
                          currencyPrefix: e.target.value,
                        })
                      }
                      placeholder="如 ¥"
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Time Profile — enables dashboard global time filtering.
              KPI cards use their own 日期列 setting (same date_column key). */}
          {state.viewId && columns.length > 0 && state.chartType !== "kpi_card" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">时间配置（可选）</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  设置时间列后，仪表盘的全局时间筛选（日期范围 / 粒度 / 聚合）才会作用于本可视化。
                </p>
                <div>
                  <label className="mb-1 block text-sm font-medium">时间列</label>
                  <Select
                    value={(state.configJson.date_column as string) || "__none__"}
                    onValueChange={(v) =>
                      vizBuilder.updateConfigKey("date_column", v === "__none__" ? "" : v)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue>
                        {(state.configJson.date_column as string) || "未设置"}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent
                      align="start"
                      sideOffset={4}
                      alignItemWithTrigger={false}
                      className="bg-background"
                    >
                      <SelectItem value="__none__">未设置</SelectItem>
                      {dateColumns.map((col) => (
                        <SelectItem key={col} value={col}>
                          {col}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {(state.configJson.date_column as string) && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-sm font-medium">默认粒度</label>
                      <Select
                        value={(state.configJson.default_granularity as string) || "day"}
                        onValueChange={(v) => vizBuilder.updateConfigKey("default_granularity", v)}
                      >
                        <SelectTrigger>
                          <SelectValue>
                            {TIME_PROFILE_GRANULARITY_OPTIONS.find(
                              (o) =>
                                o.value ===
                                ((state.configJson.default_granularity as string) || "day"),
                            )?.label ?? "日"}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent
                          align="start"
                          sideOffset={4}
                          alignItemWithTrigger={false}
                          className="bg-background"
                        >
                          {TIME_PROFILE_GRANULARITY_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium">默认聚合</label>
                      <Select
                        value={(state.configJson.default_agg as string) || "SUM"}
                        onValueChange={(v) => vizBuilder.updateConfigKey("default_agg", v)}
                      >
                        <SelectTrigger>
                          <SelectValue>
                            {AGGREGATION_OPTIONS.find(
                              (o) =>
                                o.value === ((state.configJson.default_agg as string) || "SUM"),
                            )?.label ?? "求和"}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent
                          align="start"
                          sideOffset={4}
                          alignItemWithTrigger={false}
                          className="bg-background"
                        >
                          {AGGREGATION_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Save */}
          <div className="flex gap-2 pb-4">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-1 h-4 w-4" />
              )}
              保存
            </Button>
          </div>
        </div>

        {/* Right panel — Preview */}
        <div>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Eye className="h-4 w-4" />
                预览
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoomOpen(true)}
                disabled={!state.viewId}
                title="放大查看"
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              {/* pb-4 keeps slack below the x-axis caption inside the captured
                  element, otherwise html2canvas clips the text's bottom half */}
              <div ref={previewRef} className="min-h-[300px] pb-4">
                {renderPreview()}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Zoom-in popup */}
      {zoomOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setZoomOpen(false)}
        >
          <div
            className="flex h-[88vh] w-[94vw] max-w-6xl flex-col rounded-lg bg-background shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="text-base font-semibold">{state.name || "可视化预览"}</h3>
              <Button variant="ghost" size="sm" onClick={() => setZoomOpen(false)} title="关闭">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-6">{renderPreview({ forModal: true })}</div>
          </div>
        </div>
      )}

      {/* Name-conflict Confirmation Dialog */}
      {confirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setConfirmDialog(null)} />
          <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold">确认修改</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              可视化名称「{confirmDialog.targetName}」已存在，是否修改该可视化？
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDialog(null)} disabled={isSaving}>
                取消
              </Button>
              <Button onClick={handleConfirmUpdate} disabled={isSaving}>
                {isSaving ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-1 h-4 w-4" />
                )}
                修改
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Config Panel per chart type ─────────────────────────────────────────────

function ChartConfigPanel({
  chartType,
  config,
  columns,
  numericColumns,
  dateColumns,
  onUpdateKey,
}: {
  chartType: ChartType;
  config: Record<string, unknown>;
  columns: string[];
  numericColumns: string[];
  dateColumns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  switch (chartType) {
    case "table":
      return <TableConfig config={config} columns={columns} onUpdateKey={onUpdateKey} />;
    case "kpi_card":
      return (
        <KpiCardConfig
          config={config}
          numericColumns={numericColumns}
          dateColumns={dateColumns}
          onUpdateKey={onUpdateKey}
        />
      );
    case "bar":
    case "line":
    case "scatter":
      return (
        <AxisChartConfig
          config={config}
          columns={columns}
          numericColumns={numericColumns}
          dateColumns={dateColumns}
          chartType={chartType}
          onUpdateKey={onUpdateKey}
        />
      );
    case "pie":
      return (
        <PieChartConfig
          config={config}
          columns={columns}
          numericColumns={numericColumns}
          onUpdateKey={onUpdateKey}
        />
      );
    case "histogram":
      return (
        <HistogramChartConfig
          config={config}
          numericColumns={numericColumns}
          onUpdateKey={onUpdateKey}
        />
      );
    case "boxplot":
      return (
        <BoxplotChartConfig
          config={config}
          columns={columns}
          numericColumns={numericColumns}
          dateColumns={dateColumns}
          onUpdateKey={onUpdateKey}
        />
      );
  }
}

// ── Table Config ────────────────────────────────────────────────────────────

function TableConfig({
  config,
  columns,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  columns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  const visibleColumns = (config.visible_columns as string[]) ?? [];

  const toggleColumn = (col: string) => {
    const next = visibleColumns.includes(col)
      ? visibleColumns.filter((c) => c !== col)
      : [...visibleColumns, col];
    onUpdateKey("visible_columns", next);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">表格配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-2 block text-sm font-medium">显示列</label>
          <div className="max-h-48 space-y-1 overflow-y-auto">
            {columns.map((col) => (
              <label
                key={col}
                className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(col)}
                  onChange={() => toggleColumn(col)}
                  className="h-4 w-4"
                />
                <span className="text-sm">{col}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">排序列</label>
          <Select
            value={(config.sort_column as string) ?? ""}
            onValueChange={(v) => onUpdateKey("sort_column", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择排序列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {columns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">排序方向</label>
          <Select
            value={(config.sort_direction as string) ?? "asc"}
            onValueChange={(v) => onUpdateKey("sort_direction", v)}
          >
            <SelectTrigger>
              <SelectValue>
                {((config.sort_direction as string) ?? "asc") === "asc" ? "升序" : "降序"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              <SelectItem value="asc">升序</SelectItem>
              <SelectItem value="desc">降序</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}

// ── KPI Card Config ─────────────────────────────────────────────────────────

const AGGREGATION_OPTIONS = [
  { value: "SUM", label: "求和" },
  { value: "AVG", label: "平均值" },
  { value: "COUNT", label: "计数" },
  { value: "MIN", label: "最小值" },
  { value: "MAX", label: "最大值" },
];

const GRANULARITY_OPTIONS = [
  { value: "day", label: "日" },
  { value: "month", label: "月" },
  { value: "year", label: "年" },
];

// Default granularity for the dashboard time profile — supports the full
// set the dashboard granularity tabs offer (week/quarter included).
const TIME_PROFILE_GRANULARITY_OPTIONS = [
  { value: "day", label: "日" },
  { value: "week", label: "周" },
  { value: "month", label: "月" },
  { value: "quarter", label: "季" },
  { value: "year", label: "年" },
];

function KpiCardConfig({
  config,
  numericColumns,
  dateColumns,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  numericColumns: string[];
  dateColumns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">KPI 卡片配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">数值列</label>
          <Select
            value={(config.value_column as string) ?? ""}
            onValueChange={(v) => onUpdateKey("value_column", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择数值列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {numericColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">聚合方式</label>
          <Select
            value={(config.aggregation as string) ?? "SUM"}
            onValueChange={(v) => onUpdateKey("aggregation", v)}
          >
            <SelectTrigger>
              <SelectValue>
                {AGGREGATION_OPTIONS.find(
                  (o) => o.value === ((config.aggregation as string) ?? "SUM"),
                )?.label ?? "求和"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {AGGREGATION_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">标签</label>
          <input
            type="text"
            value={(config.label as string) ?? ""}
            onChange={(e) => onUpdateKey("label", e.target.value)}
            placeholder="如：总退款金额"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">日期列（可选）</label>
          <Select
            value={(config.date_column as string) || "__none__"}
            onValueChange={(v) => onUpdateKey("date_column", v === "__none__" ? "" : v)}
          >
            <SelectTrigger>
              <SelectValue>{(config.date_column as string) || "无"}</SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              <SelectItem value="__none__">无</SelectItem>
              {dateColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {(config.date_column as string) && (
          <div>
            <label className="mb-1 block text-sm font-medium">时间粒度</label>
            <Select
              value={(config.granularity as string) ?? "day"}
              onValueChange={(v) => onUpdateKey("granularity", v)}
            >
              <SelectTrigger>
                <SelectValue>
                  {GRANULARITY_OPTIONS.find(
                    (o) => o.value === ((config.granularity as string) ?? "day"),
                  )?.label ?? "日"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent
                align="start"
                sideOffset={4}
                alignItemWithTrigger={false}
                className="bg-background"
              >
                {GRANULARITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Axis Chart Config (Bar / Line / Scatter) ────────────────────────────────

const TIME_GRANULARITY_OPTIONS = [
  { value: "none", label: "原始值（不聚合）" },
  { value: "day", label: "日" },
  { value: "week", label: "周" },
  { value: "month", label: "月" },
  { value: "quarter", label: "季" },
  { value: "year", label: "年" },
];

const TIME_AGGREGATION_OPTIONS = [
  { value: "SUM", label: "求和" },
  { value: "AVG", label: "平均值" },
  { value: "COUNT", label: "计数" },
  { value: "MIN", label: "最小值" },
  { value: "MAX", label: "最大值" },
];

function AxisChartConfig({
  config,
  columns,
  numericColumns,
  dateColumns,
  chartType,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  columns: string[];
  numericColumns: string[];
  dateColumns: string[];
  chartType: ChartType;
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  const title =
    chartType === "bar" ? "柱状图配置" : chartType === "line" ? "折线图配置" : "散点图配置";

  const yColumns = (config.y_columns as string[]) ?? [];
  const xColumn = (config.x_column as string) ?? "";
  const isTimeSeriesAxis = dateColumns.includes(xColumn);
  const timeGranularity = (config.time_granularity as string) ?? "none";

  // Categorical = neither numeric nor date. Bar charts only make sense on
  // categorical X / group columns (values are aggregated per category)
  const categoricalColumns = columns.filter(
    (c) => !numericColumns.includes(c) && !dateColumns.includes(c),
  );
  const xColumnOptions = chartType === "bar" ? categoricalColumns : columns;

  const toggleYColumn = (col: string) => {
    const next = yColumns.includes(col) ? yColumns.filter((c) => c !== col) : [...yColumns, col];
    onUpdateKey("y_columns", next);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">图表标题</label>
          <input
            type="text"
            value={(config.title as string) ?? ""}
            onChange={(e) => onUpdateKey("title", e.target.value)}
            placeholder="输入图表标题"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            X 轴列{chartType === "bar" ? "（分类）" : ""}
          </label>
          <Select value={xColumn} onValueChange={(v) => onUpdateKey("x_column", v)}>
            <SelectTrigger>
              <SelectValue placeholder="选择 X 轴列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {xColumnOptions.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {chartType === "bar" && (
          <div>
            <label className="mb-1 block text-sm font-medium">聚合方式</label>
            <Select
              value={(config.aggregation as string) ?? "SUM"}
              onValueChange={(v) => onUpdateKey("aggregation", v)}
            >
              <SelectTrigger>
                <SelectValue>
                  {AGGREGATION_OPTIONS.find(
                    (o) => o.value === ((config.aggregation as string) ?? "SUM"),
                  )?.label ?? "求和"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent
                align="start"
                sideOffset={4}
                alignItemWithTrigger={false}
                className="bg-background"
              >
                {AGGREGATION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Time-series options — shown only when X axis is a date column */}
        {isTimeSeriesAxis && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-sm font-medium">时间粒度（可选）</label>
                <Select
                  value={timeGranularity}
                  onValueChange={(v) => onUpdateKey("time_granularity", v)}
                >
                  <SelectTrigger>
                    <SelectValue>
                      {TIME_GRANULARITY_OPTIONS.find((o) => o.value === timeGranularity)?.label ??
                        "原始值（不聚合）"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent
                    align="start"
                    sideOffset={4}
                    alignItemWithTrigger={false}
                    className="bg-background"
                  >
                    {TIME_GRANULARITY_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {timeGranularity !== "none" && (
                <div>
                  <label className="mb-1 block text-sm font-medium">聚合方式</label>
                  <Select
                    value={(config.time_aggregation as string) ?? "SUM"}
                    onValueChange={(v) => onUpdateKey("time_aggregation", v)}
                  >
                    <SelectTrigger>
                      <SelectValue>
                        {TIME_AGGREGATION_OPTIONS.find(
                          (o) => o.value === ((config.time_aggregation as string) ?? "SUM"),
                        )?.label ?? "求和"}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent
                      align="start"
                      sideOffset={4}
                      alignItemWithTrigger={false}
                      className="bg-background"
                    >
                      {TIME_AGGREGATION_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="show-time"
                  checked={(config.show_time as boolean) ?? false}
                  onChange={(e) => onUpdateKey("show_time", e.target.checked)}
                  className="h-4 w-4"
                />
                <label htmlFor="show-time" className="text-sm">
                  刻度显示时间
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enable-brush"
                  checked={(config.enable_brush as boolean) ?? true}
                  onChange={(e) => onUpdateKey("enable_brush", e.target.checked)}
                  className="h-4 w-4"
                />
                <label htmlFor="enable-brush" className="text-sm">
                  缩放条
                </label>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium">起始日期（可选）</label>
                <input
                  type="date"
                  value={(config.date_range_start as string) ?? ""}
                  onChange={(e) => onUpdateKey("date_range_start", e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium">结束日期（可选）</label>
                <input
                  type="date"
                  value={(config.date_range_end as string) ?? ""}
                  onChange={(e) => onUpdateKey("date_range_end", e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                />
              </div>
            </div>
          </>
        )}

        <div>
          <label className="mb-2 block text-sm font-medium">Y 轴列（数值）</label>
          <div className="max-h-32 space-y-1 overflow-y-auto">
            {numericColumns.map((col) => (
              <label
                key={col}
                className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={yColumns.includes(col)}
                  onChange={() => toggleYColumn(col)}
                  className="h-4 w-4"
                />
                <span className="text-sm">{col}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">分组列（可选）</label>
          <Select
            value={(config.group_by_column as string) || "__none__"}
            onValueChange={(v) => onUpdateKey("group_by_column", v === "__none__" ? "" : v)}
          >
            <SelectTrigger>
              <SelectValue>{(config.group_by_column as string) || "无"}</SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              <SelectItem value="__none__">无</SelectItem>
              {columns
                .filter(
                  (c) =>
                    c !== xColumn &&
                    !numericColumns.includes(c) &&
                    (chartType !== "bar" || !dateColumns.includes(c)),
                )
                .map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        {chartType === "bar" && (config.group_by_column as string) && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="stack-bars"
              checked={(config.stack_bars as boolean) ?? false}
              onChange={(e) => onUpdateKey("stack_bars", e.target.checked)}
              className="h-4 w-4"
            />
            <label htmlFor="stack-bars" className="text-sm">
              堆叠显示（分组多时更易读）
            </label>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium">X 轴标签</label>
            <input
              type="text"
              value={(config.x_label as string) ?? ""}
              onChange={(e) => onUpdateKey("x_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Y 轴标签</label>
            <input
              type="text"
              value={(config.y_label as string) ?? ""}
              onChange={(e) => onUpdateKey("y_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Pie Chart Config ────────────────────────────────────────────────────────

function PieChartConfig({
  config,
  columns,
  numericColumns,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  columns: string[];
  numericColumns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">饼图配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">图表标题</label>
          <input
            type="text"
            value={(config.title as string) ?? ""}
            onChange={(e) => onUpdateKey("title", e.target.value)}
            placeholder="输入图表标题"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">标签列</label>
          <Select
            value={(config.label_column as string) ?? ""}
            onValueChange={(v) => onUpdateKey("label_column", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择标签列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {columns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">数值列</label>
          <Select
            value={(config.value_column as string) ?? ""}
            onValueChange={(v) => onUpdateKey("value_column", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择数值列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {numericColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">聚合方式</label>
          <Select
            value={(config.aggregation as string) ?? "SUM"}
            onValueChange={(v) => onUpdateKey("aggregation", v)}
          >
            <SelectTrigger>
              <SelectValue>
                {AGGREGATION_OPTIONS.find(
                  (o) => o.value === ((config.aggregation as string) ?? "SUM"),
                )?.label ?? "求和"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {AGGREGATION_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Histogram Chart Config ──────────────────────────────────────────────

function HistogramChartConfig({
  config,
  numericColumns,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  numericColumns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  const selected = (config.columns as string[]) ?? [];
  const bins = (config.bins as number) ?? 20;

  const toggleColumn = (col: string) => {
    const next = selected.includes(col) ? selected.filter((c) => c !== col) : [...selected, col];
    onUpdateKey("columns", next);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">直方图配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">图表标题</label>
          <input
            type="text"
            value={(config.title as string) ?? ""}
            onChange={(e) => onUpdateKey("title", e.target.value)}
            placeholder="输入图表标题"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">数值列（可多选）</label>
          <div className="max-h-32 space-y-1 overflow-y-auto">
            {numericColumns.map((col) => (
              <label
                key={col}
                className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(col)}
                  onChange={() => toggleColumn(col)}
                  className="h-4 w-4"
                />
                <span className="text-sm">{col}</span>
              </label>
            ))}
          </div>
          {selected.length > 1 && (
            <p className="mt-1 text-xs text-muted-foreground">
              多列时以不同颜色半透明重叠显示，便于对比分布
            </p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">分箱数（可选）</label>
          <input
            type="number"
            min={1}
            max={200}
            value={bins}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              onUpdateKey("bins", isNaN(n) ? 20 : Math.min(200, Math.max(1, n)));
            }}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium">X 轴标签</label>
            <input
              type="text"
              value={(config.x_label as string) ?? ""}
              onChange={(e) => onUpdateKey("x_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Y 轴标签</label>
            <input
              type="text"
              value={(config.y_label as string) ?? ""}
              onChange={(e) => onUpdateKey("y_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Boxplot Chart Config ────────────────────────────────────────────────

function BoxplotChartConfig({
  config,
  columns,
  numericColumns,
  dateColumns,
  onUpdateKey,
}: {
  config: Record<string, unknown>;
  columns: string[];
  numericColumns: string[];
  dateColumns: string[];
  onUpdateKey: (key: string, value: unknown) => void;
}) {
  // Only categorical columns make sense as the boxplot grouping axis
  const categoricalColumns = columns.filter(
    (c) => !numericColumns.includes(c) && !dateColumns.includes(c),
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">箱线图配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">图表标题</label>
          <input
            type="text"
            value={(config.title as string) ?? ""}
            onChange={(e) => onUpdateKey("title", e.target.value)}
            placeholder="输入图表标题"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">分类列（可选）</label>
          <Select
            value={(config.category_column as string) || "__none__"}
            onValueChange={(v) => onUpdateKey("category_column", v === "__none__" ? "" : v)}
          >
            <SelectTrigger>
              <SelectValue>{(config.category_column as string) || "无"}</SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              <SelectItem value="__none__">无</SelectItem>
              {categoricalColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">数值列</label>
          <Select
            value={(config.value_column as string) ?? ""}
            onValueChange={(v) => onUpdateKey("value_column", v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择数值列" />
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {numericColumns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium">X 轴标签</label>
            <input
              type="text"
              value={(config.x_label as string) ?? ""}
              onChange={(e) => onUpdateKey("x_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Y 轴标签</label>
            <input
              type="text"
              value={(config.y_label as string) ?? ""}
              onChange={(e) => onUpdateKey("y_label", e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Preview Components ──────────────────────────────────────────────────────

// ── Shared time-series helpers ──────────────────────────────────────────────

/** Truncate an ISO date string to the given granularity. */
function truncateDate(dateStr: string, granularity: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const y = d.getFullYear();
  const m = d.getMonth();
  const day = d.getDate();
  switch (granularity) {
    case "day":
      return `${y}-${String(m + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    case "week": {
      // ISO week: Monday-based
      const dow = d.getDay() || 7; // Sunday = 7
      const monday = new Date(d);
      monday.setDate(day - dow + 1);
      return `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, "0")}-${String(monday.getDate()).padStart(2, "0")}`;
    }
    case "month":
      return `${y}-${String(m + 1).padStart(2, "0")}`;
    case "quarter": {
      const q = Math.floor(m / 3) + 1;
      return `${y}-Q${q}`;
    }
    case "year":
      return `${y}`;
    default:
      return dateStr;
  }
}

/** Format a date/datetime string for x-axis display. */
function formatAxisDate(value: string, showTime: boolean): string {
  if (!value) return value;
  // If it looks like a quarter key (e.g. "2026-Q1"), return as-is
  if (/^\d{4}-Q\d$/.test(value)) return value;
  // If it's date-only (YYYY-MM-DD or YYYY-MM or YYYY), return as-is
  if (/^\d{4}(-\d{2})?(-\d{2})?$/.test(value)) return value;
  // Try parsing as date
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  const datePart = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (!showTime) return datePart;
  const timePart = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  return `${datePart} ${timePart}`;
}

/** Aggregate numeric values. */
function aggregateValues(values: number[], method: string): number {
  if (!values.length) return 0;
  switch (method) {
    case "SUM":
      return values.reduce((a, b) => a + b, 0);
    case "AVG":
      return values.reduce((a, b) => a + b, 0) / values.length;
    case "COUNT":
      return values.length;
    case "MIN":
      return Math.min(...values);
    case "MAX":
      return Math.max(...values);
    default:
      return values.reduce((a, b) => a + b, 0);
  }
}

/** Process rows for time-series display: filter by date range, bucket by granularity, aggregate. */
function processTimeSeriesRows(
  rows: Record<string, unknown>[],
  xColumn: string,
  yColumns: string[],
  config: Record<string, unknown>,
  isTimeSeries: boolean,
): Record<string, unknown>[] {
  // Rows without an X value cannot be placed on the axis — drop them
  let filtered = rows.filter((r) => r[xColumn] != null && String(r[xColumn]) !== "");

  // Date range filter
  if (isTimeSeries) {
    const rangeStart = config.date_range_start as string;
    const rangeEnd = config.date_range_end as string;
    if (rangeStart) {
      filtered = filtered.filter((r) => {
        const v = String(r[xColumn] ?? "");
        return v >= rangeStart;
      });
    }
    if (rangeEnd) {
      // Add one day to include the end date
      const end = new Date(rangeEnd);
      end.setDate(end.getDate() + 1);
      const endStr = end.toISOString().slice(0, 10);
      filtered = filtered.filter((r) => {
        const v = String(r[xColumn] ?? "");
        return v < endStr;
      });
    }
  }

  if (!isTimeSeries) return filtered;

  const granularity = (config.time_granularity as string) || "none";

  // No aggregation — show raw datetimes sorted chronologically
  if (granularity === "none") {
    return [...filtered].sort((a, b) =>
      String(a[xColumn] ?? "").localeCompare(String(b[xColumn] ?? "")),
    );
  }

  // Bucket by granularity and aggregate
  const aggregation = (config.time_aggregation as string) || "SUM";
  const groupByCol = config.group_by_column as string;

  const buckets = new Map<string, Record<string, unknown>[]>();
  for (const row of filtered) {
    const rawDate = String(row[xColumn] ?? "");
    const bucketKey = truncateDate(rawDate, granularity);
    const groupKey = groupByCol ? String(row[groupByCol] ?? "") : "";
    const key = groupKey ? `${bucketKey}||${groupKey}` : bucketKey;
    const existing = buckets.get(key) ?? [];
    existing.push(row);
    buckets.set(key, existing);
  }

  // Convert buckets to aggregated rows
  const result: Record<string, unknown>[] = [];
  for (const [key, bucketRows] of buckets) {
    const [bucketKey, groupKey] = key.split("||");
    const outRow: Record<string, unknown> = { [xColumn]: bucketKey };
    if (groupByCol && groupKey) {
      outRow[groupByCol] = groupKey;
    }
    for (const yCol of yColumns) {
      const values = bucketRows.map((r) => Number(r[yCol])).filter((v) => !isNaN(v));
      outRow[yCol] = aggregateValues(values, aggregation);
    }
    result.push(outRow);
  }

  // Sort by x-axis value
  result.sort((a, b) => String(a[xColumn]).localeCompare(String(b[xColumn])));
  return result;
}

/** Pivot rows for grouped display: one row per x-value, columns = category_yCol */
function pivotForGroupBy(
  rows: Record<string, unknown>[],
  xColumn: string,
  yColumns: string[],
  groupByColumn: string,
  categories: string[],
): {
  data: Record<string, unknown>[];
  seriesKeys: { key: string; label: string; yCol: string; category: string }[];
} {
  const seriesKeys: { key: string; label: string; yCol: string; category: string }[] = [];
  const multiY = yColumns.length > 1;
  for (const yCol of yColumns) {
    for (const cat of categories) {
      // With a single Y column the legend shows the class name only;
      // with multiple Y columns the variable name is needed to disambiguate
      const label = multiY ? `${cat} · ${yCol}` : cat;
      seriesKeys.push({ key: `${yCol}||${cat}`, label, yCol, category: cat });
    }
  }

  const xValues = new Map<string, Record<string, unknown>>();
  for (const row of rows) {
    const xVal = String(row[xColumn] ?? "");
    const cat = categoryValue(row, groupByColumn);
    if (!xValues.has(xVal)) {
      xValues.set(xVal, { [xColumn]: xVal });
    }
    const outRow = xValues.get(xVal)!;
    for (const yCol of yColumns) {
      const key = `${yCol}||${cat}`;
      outRow[key] = row[yCol];
    }
  }

  const data = Array.from(xValues.values()).sort((a, b) =>
    String(a[xColumn]).localeCompare(String(b[xColumn])),
  );
  return { data, seriesKeys };
}

// ── Scatter shape symbols for 3rd dimension ─────────────────────────────────

const SCATTER_SHAPES: SymbolShape[] = SYMBOL_SHAPES;

/** Normalized Y key for scatter points — YAxis needs an explicit dataKey. */
const SCATTER_Y_KEY = "__y";

/** Hidden point field carrying the original Y column name for tooltips. */
const SCATTER_YCOL_KEY = "__yCol";

/** Cap scatter points per series — full datasets (30k+ rows) freeze the browser. */
const MAX_SCATTER_POINTS = 2000;

/** Deterministic stride sampling keeps the overall distribution shape intact. */
function samplePoints(points: Record<string, unknown>[]): Record<string, unknown>[] {
  if (points.length <= MAX_SCATTER_POINTS) return points;
  const stride = points.length / MAX_SCATTER_POINTS;
  const out: Record<string, unknown>[] = [];
  for (let i = 0; out.length < MAX_SCATTER_POINTS; i++) {
    out.push(points[Math.floor(i * stride)]);
  }
  return out;
}

const TABLE_PAGE_SIZE = 20;

export function TablePreview({
  config,
  columns,
  rows,
  inModal = false,
}: {
  config: Record<string, unknown>;
  columns: string[];
  rows: Record<string, unknown>[];
  inModal?: boolean;
}) {
  const visibleColumns =
    ((config.visible_columns as string[]) ?? []).length > 0
      ? (config.visible_columns as string[])
      : columns;

  const sortColumn = config.sort_column as string;
  const sortDirection = (config.sort_direction as string) ?? "asc";

  const sortedRows = useMemo(() => {
    if (!sortColumn) return rows;
    return [...rows].sort((a, b) => {
      const va = a[sortColumn];
      const vb = b[sortColumn];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDirection === "desc" ? -cmp : cmp;
    });
  }, [rows, sortColumn, sortDirection]);

  // ── Client-side pagination ───────────────────────────────────────────
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / TABLE_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = useMemo(
    () => sortedRows.slice((safePage - 1) * TABLE_PAGE_SIZE, safePage * TABLE_PAGE_SIZE),
    [sortedRows, safePage],
  );

  // Reset to first page when sorting changes
  useEffect(() => {
    setPage(1);
  }, [sortColumn, sortDirection, rows]);

  return (
    <div>
      <div
        className={`overflow-auto rounded-md border ${inModal ? "max-h-[calc(88vh-220px)]" : "max-h-[460px]"}`}
      >
        <Table>
          <TableHeader>
            <TableRow>
              {visibleColumns.map((col) => (
                <TableHead key={col} className="max-w-[200px] truncate whitespace-nowrap">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((row, i) => (
              <TableRow key={i}>
                {visibleColumns.map((col) => (
                  <TableCell key={col} className="max-w-[200px] truncate">
                    {row[col] != null ? String(row[col]) : ""}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {/* Pagination controls */}
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          共 {sortedRows.length} 行 · 第 {safePage}/{totalPages} 页
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={safePage <= 1}
            onClick={() => setPage(safePage - 1)}
          >
            <ChevronLeft className="mr-0.5 h-3.5 w-3.5" />
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={safePage >= totalPages}
            onClick={() => setPage(safePage + 1)}
          >
            下一页
            <ChevronRight className="ml-0.5 h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function KpiCardPreview({
  config,
  rows,
  numberFormat,
  height,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  numberFormat: { decimals: number; thousandsSeparator: boolean; currencyPrefix: string };
  /** Fixed height (px) for contexts without a height-constrained parent (e.g. thumbnails). */
  height?: number;
}) {
  const valueColumn = config.value_column as string;
  const label = (config.label as string) || "指标";
  const aggregation = (config.aggregation as string) || "SUM";
  const dateColumn = config.date_column as string;
  const granularity = (config.granularity as string) || "day";

  // ── Aggregate a set of rows ───────────────────────────────────────────
  const aggregate = useCallback(
    (subset: Record<string, unknown>[]): number => {
      if (!valueColumn || !subset.length) return 0;
      const values = subset.map((r) => Number(r[valueColumn])).filter((v) => !isNaN(v));
      if (!values.length) return 0;
      switch (aggregation) {
        case "SUM":
          return values.reduce((a, b) => a + b, 0);
        case "AVG":
          return values.reduce((a, b) => a + b, 0) / values.length;
        case "COUNT":
          return values.length;
        case "MIN":
          return Math.min(...values);
        case "MAX":
          return Math.max(...values);
        default:
          return values.reduce((a, b) => a + b, 0);
      }
    },
    [valueColumn, aggregation],
  );

  // ── Period helpers ────────────────────────────────────────────────────
  const getPeriodKey = useCallback(
    (dateStr: string): string => {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return "";
      switch (granularity) {
        case "day":
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        case "month":
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        case "year":
          return `${d.getFullYear()}`;
        default:
          return "";
      }
    },
    [granularity],
  );

  const getPrevPeriodKey = useCallback(
    (periodKey: string): string => {
      if (!periodKey) return "";
      switch (granularity) {
        case "day": {
          const d = new Date(periodKey);
          d.setDate(d.getDate() - 1);
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        }
        case "month": {
          const [y, m] = periodKey.split("-").map(Number);
          const d = new Date(y, m - 2, 1); // m-1 is 0-indexed, -1 more for prev
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        }
        case "year": {
          return `${Number(periodKey) - 1}`;
        }
        default:
          return "";
      }
    },
    [granularity],
  );

  const getYearAgoPeriodKey = useCallback(
    (periodKey: string): string => {
      if (!periodKey) return "";
      switch (granularity) {
        case "day": {
          const d = new Date(periodKey);
          d.setFullYear(d.getFullYear() - 1);
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        }
        case "month": {
          const [y, m] = periodKey.split("-").map(Number);
          return `${y - 1}-${String(m).padStart(2, "0")}`;
        }
        case "year": {
          return `${Number(periodKey) - 1}`;
        }
        default:
          return "";
      }
    },
    [granularity],
  );

  // ── Compute current / prev / year-ago values ──────────────────────────
  const { currentValue, prevChange, yearAgoChange, currentPeriodLabel } = useMemo(() => {
    if (!valueColumn || !rows.length) {
      return { currentValue: 0, prevChange: null, yearAgoChange: null, currentPeriodLabel: "" };
    }

    // No date column — aggregate all rows
    if (!dateColumn) {
      return {
        currentValue: aggregate(rows),
        prevChange: null,
        yearAgoChange: null,
        currentPeriodLabel: "",
      };
    }

    // Group rows by period
    const periodMap = new Map<string, Record<string, unknown>[]>();
    for (const row of rows) {
      const dateVal = row[dateColumn];
      if (!dateVal) continue;
      const key = getPeriodKey(String(dateVal));
      if (!key) continue;
      const existing = periodMap.get(key) ?? [];
      existing.push(row);
      periodMap.set(key, existing);
    }

    if (periodMap.size === 0) {
      return { currentValue: 0, prevChange: null, yearAgoChange: null, currentPeriodLabel: "" };
    }

    // Find the most recent period
    const sortedPeriods = Array.from(periodMap.keys()).sort().reverse();
    const currentPeriod = sortedPeriods[0];
    const currentVal = aggregate(periodMap.get(currentPeriod)!);

    // Previous period
    const prevPeriod = getPrevPeriodKey(currentPeriod);
    const prevRows = periodMap.get(prevPeriod);
    const prevVal = prevRows ? aggregate(prevRows) : null;
    const prevPct =
      prevVal !== null && prevVal !== 0 ? ((currentVal - prevVal) / prevVal) * 100 : null;

    // Year-ago period
    const yearAgoPeriod = getYearAgoPeriodKey(currentPeriod);
    const yearAgoRows = periodMap.get(yearAgoPeriod);
    const yearAgoVal = yearAgoRows ? aggregate(yearAgoRows) : null;
    const yearAgoPct =
      yearAgoVal !== null && yearAgoVal !== 0
        ? ((currentVal - yearAgoVal) / yearAgoVal) * 100
        : null;

    return {
      currentValue: currentVal,
      prevChange: prevPct,
      yearAgoChange: yearAgoPct,
      currentPeriodLabel: currentPeriod,
    };
  }, [
    rows,
    valueColumn,
    dateColumn,
    aggregate,
    getPeriodKey,
    getPrevPeriodKey,
    getYearAgoPeriodKey,
  ]);

  const formattedValue = formatNumber(
    currentValue,
    numberFormat.decimals,
    numberFormat.thousandsSeparator,
    numberFormat.currencyPrefix,
  );

  const granularityLabel = granularity === "day" ? "日" : granularity === "month" ? "月" : "年";

  return (
    <div
      // Fill the tile completely; inline-size containment lets the value
      // scale with the tile width (cqw) instead of leaving blank area.
      className="flex h-full w-full flex-col items-center justify-center gap-1 rounded-lg bg-card p-3 text-center [container-type:inline-size]"
      style={height ? { height } : { minHeight: 200 }}
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-bold leading-tight tracking-tight text-[clamp(1.5rem,11cqw,3.5rem)]">
        {formattedValue}
      </p>
      {currentPeriodLabel && (
        <p className="text-[11px] text-muted-foreground">
          {currentPeriodLabel}（按{granularityLabel}）
        </p>
      )}
      {(prevChange !== null || yearAgoChange !== null) && (
        <div className="flex flex-wrap items-center justify-center gap-x-3">
          {prevChange !== null && (
            <p className={`text-xs ${prevChange >= 0 ? "text-green-600" : "text-red-600"}`}>
              {prevChange >= 0 ? "+" : ""}
              {prevChange.toFixed(1)}% 环比
            </p>
          )}
          {yearAgoChange !== null && (
            <p className={`text-xs ${yearAgoChange >= 0 ? "text-green-600" : "text-red-600"}`}>
              {yearAgoChange >= 0 ? "+" : ""}
              {yearAgoChange.toFixed(1)}% 同比
            </p>
          )}
        </div>
      )}
      <p className="text-[11px] text-muted-foreground/80">共 {rows.length} 条记录</p>
    </div>
  );
}

export function BarChartPreview({
  config,
  rows,
  colors,
  dateColumns,
  height = 420,
  showBrush = true,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  dateColumns: string[];
  height?: number;
  showBrush?: boolean;
}) {
  const xColumn = config.x_column as string;
  const yColumns = useMemo(() => (config.y_columns as string[]) ?? [], [config.y_columns]);
  const title = config.title as string;
  const groupByColumn = (config.group_by_column as string) ?? "";
  const stackBars = (config.stack_bars as boolean) ?? false;
  const aggregation = (config.aggregation as string) || "SUM";
  const isTimeSeries = dateColumns.includes(xColumn);
  const showTime = (config.show_time as boolean) ?? false;
  const { hidden, toggle } = useSeriesToggle();

  const processedRows = useMemo(
    () => processTimeSeriesRows(rows, xColumn, yColumns, config, isTimeSeries),
    [rows, xColumn, yColumns, config, isTimeSeries],
  );

  // Limit categories to Top-N for readability (rest merged into 其他)
  const { rows: limitedRows, categories } = useMemo(
    () => limitCategories(processedRows, groupByColumn),
    [processedRows, groupByColumn],
  );

  const { data: chartData, seriesKeys } = useMemo(() => {
    // Bar X is categorical: aggregate Y values per category with the chosen method
    // (legacy configs with a date X keep the time-series bucketing path)
    const finalRows = isTimeSeries
      ? limitedRows
      : aggregateCategoricalRows(limitedRows, xColumn, yColumns, groupByColumn, aggregation);
    if (groupByColumn && categories.length > 0) {
      return pivotForGroupBy(finalRows, xColumn, yColumns, groupByColumn, categories);
    }
    return {
      data: finalRows,
      seriesKeys: yColumns.map((yc) => ({ key: yc, label: yc, yCol: yc, category: "" })),
    };
  }, [limitedRows, xColumn, yColumns, groupByColumn, categories, isTimeSeries, aggregation]);

  if (!xColumn || yColumns.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请配置 X 轴和 Y 轴列
      </div>
    );
  }

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      {(config.y_label as string) && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{config.y_label as string}</p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey={xColumn}
            angle={-30}
            textAnchor="end"
            height={55}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: AXIS_LINE_STROKE }}
            tickFormatter={(v: string) => (isTimeSeries ? formatAxisDate(v, showTime) : v)}
          />
          <YAxis
            width={60}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            tickFormatter={compactNumber}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: "rgba(148,163,184,0.12)" }}
            labelFormatter={(v) => (isTimeSeries ? formatAxisDate(String(v), showTime) : String(v))}
          />
          <Legend
            verticalAlign="top"
            iconSize={10}
            wrapperStyle={LEGEND_STYLE}
            onClick={(entry) => {
              const e = entry as unknown as { value?: unknown };
              if (e.value != null) toggle(String(e.value));
            }}
            formatter={(value, entry) => {
              const e = entry as unknown as { value?: unknown };
              const isHidden = !!hidden[String(e.value)];
              return (
                <span
                  style={
                    isHidden ? { color: "#94a3b8", textDecoration: "line-through" } : undefined
                  }
                >
                  {String(value)}
                </span>
              );
            }}
          />
          {seriesKeys.map((sk, i) => (
            <Bar
              key={sk.key}
              dataKey={sk.key}
              name={sk.label}
              fill={colors[i % colors.length]}
              hide={!!hidden[sk.label]}
              stackId={stackBars && groupByColumn ? sk.yCol : undefined}
              radius={stackBars ? undefined : [3, 3, 0, 0]}
              maxBarSize={48}
            />
          ))}
          {isTimeSeries && showBrush && (
            <Brush
              dataKey={xColumn}
              height={20}
              stroke="#94a3b8"
              travellerWidth={8}
              tickFormatter={(v: string) => formatAxisDate(v, false)}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
      {(config.x_label as string) && (
        <p className="mt-2 text-center text-xs font-medium text-muted-foreground">
          {config.x_label as string}
        </p>
      )}
    </div>
  );
}

export function LineChartPreview({
  config,
  rows,
  colors,
  dateColumns,
  height = 420,
  showBrush = true,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  dateColumns: string[];
  height?: number;
  showBrush?: boolean;
}) {
  const xColumn = config.x_column as string;
  const yColumns = useMemo(() => (config.y_columns as string[]) ?? [], [config.y_columns]);
  const title = config.title as string;
  const groupByColumn = (config.group_by_column as string) ?? "";
  const isTimeSeries = dateColumns.includes(xColumn);
  const showTime = (config.show_time as boolean) ?? false;
  const { hidden, toggle } = useSeriesToggle();

  const processedRows = useMemo(
    () => processTimeSeriesRows(rows, xColumn, yColumns, config, isTimeSeries),
    [rows, xColumn, yColumns, config, isTimeSeries],
  );

  const { rows: limitedRows, categories } = useMemo(
    () => limitCategories(processedRows, groupByColumn),
    [processedRows, groupByColumn],
  );

  const { data: chartData, seriesKeys } = useMemo(() => {
    if (groupByColumn && categories.length > 0) {
      return pivotForGroupBy(limitedRows, xColumn, yColumns, groupByColumn, categories);
    }
    return {
      data: limitedRows,
      seriesKeys: yColumns.map((yc) => ({ key: yc, label: yc, yCol: yc, category: "" })),
    };
  }, [limitedRows, xColumn, yColumns, groupByColumn, categories]);

  if (!xColumn || yColumns.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请配置 X 轴和 Y 轴列
      </div>
    );
  }

  // Very large series: keep the line path but drop per-point symbols
  const showDots = chartData.length <= LINE_DOT_MAX_POINTS;

  // Class encoding: color + point symbol per category (single Y column);
  // with multiple Y columns, color encodes the Y variable and symbol the category
  const singleY = yColumns.length === 1;
  const catIdxMap = new Map<string, number>();
  const yColColorMap = new Map<string, number>();
  let catIdx = 0;
  let yColorIdx = 0;
  for (const sk of seriesKeys) {
    if (sk.category && !catIdxMap.has(sk.category)) {
      catIdxMap.set(sk.category, catIdx++);
    }
    if (!yColColorMap.has(sk.yCol)) {
      yColColorMap.set(sk.yCol, yColorIdx++);
    }
  }

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      {(config.y_label as string) && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{config.y_label as string}</p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ReLineChart data={chartData} margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey={xColumn}
            angle={-30}
            textAnchor="end"
            height={55}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: AXIS_LINE_STROKE }}
            tickFormatter={(v: string) => (isTimeSeries ? formatAxisDate(v, showTime) : v)}
          />
          <YAxis
            width={60}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            tickFormatter={compactNumber}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(v) => (isTimeSeries ? formatAxisDate(String(v), showTime) : String(v))}
          />
          <Legend
            verticalAlign="top"
            iconSize={10}
            wrapperStyle={LEGEND_STYLE}
            onClick={(entry) => {
              const e = entry as unknown as { value?: unknown };
              if (e.value != null) toggle(String(e.value));
            }}
            formatter={(value, entry) => {
              const e = entry as unknown as { value?: unknown };
              const isHidden = !!hidden[String(e.value)];
              return (
                <span
                  style={
                    isHidden ? { color: "#94a3b8", textDecoration: "line-through" } : undefined
                  }
                >
                  {String(value)}
                </span>
              );
            }}
          />
          {seriesKeys.map((sk) => {
            const ci = singleY
              ? sk.category
                ? (catIdxMap.get(sk.category) ?? 0)
                : 0
              : (yColColorMap.get(sk.yCol) ?? 0);
            const color = colors[ci % colors.length];
            const si = sk.category ? (catIdxMap.get(sk.category) ?? 0) : 0;
            const shape = SYMBOL_SHAPES[si % SYMBOL_SHAPES.length];
            return (
              <Line
                key={sk.key}
                type="monotone"
                dataKey={sk.key}
                name={sk.label}
                stroke={color}
                strokeWidth={2}
                dot={
                  !showDots
                    ? false
                    : sk.category
                      ? makeLineDot(shape, color)
                      : { r: 2.5, strokeWidth: 0 }
                }
                activeDot={{ r: 4.5 }}
                hide={!!hidden[sk.label]}
              />
            );
          })}
          {isTimeSeries && showBrush && (
            <Brush
              dataKey={xColumn}
              height={20}
              stroke="#94a3b8"
              travellerWidth={8}
              tickFormatter={(v: string) => formatAxisDate(v, false)}
            />
          )}
        </ReLineChart>
      </ResponsiveContainer>
      {(config.x_label as string) && (
        <p className="mt-2 text-center text-xs font-medium text-muted-foreground">
          {config.x_label as string}
        </p>
      )}
    </div>
  );
}

const PIE_MAX_SLICES = 8;

/** Slices below this share get no on-chart label — tiny slices stack their
 *  labels into an unreadable blob; their values stay visible in the legend
 *  and tooltip instead. */
const PIE_MIN_LABEL_PERCENT = 0.04;

interface PieDatum {
  name: string;
  value: number;
  /** Stable color index so colors don't shift when slices are hidden. */
  ci: number;
}

/** Pie legend: lists every category (incl. hidden) with its color swatch and
 *  share of the visible total; clicking toggles slice visibility. */
function PieLegendContent({
  pieData,
  colors,
  hidden,
  visibleTotal,
  onToggle,
}: {
  pieData: PieDatum[];
  colors: string[];
  hidden: Record<string, boolean>;
  visibleTotal: number;
  onToggle: (name: string) => void;
}) {
  return (
    <div className="flex max-h-full flex-col gap-1.5 overflow-y-auto pr-1">
      {pieData.map((d) => {
        const isHidden = !!hidden[d.name];
        const pct =
          !isHidden && visibleTotal > 0 ? ((d.value / visibleTotal) * 100).toFixed(1) : null;
        return (
          <button
            key={d.name}
            type="button"
            onClick={() => onToggle(d.name)}
            className="inline-flex cursor-pointer items-center gap-1.5 border-none bg-transparent p-0 text-left"
            title={isHidden ? "点击显示" : "点击隐藏"}
          >
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: isHidden ? "#94a3b8" : colors[d.ci % colors.length] }}
            />
            <span
              className="truncate"
              style={isHidden ? { color: "#94a3b8", textDecoration: "line-through" } : undefined}
            >
              {d.name}
              {pct != null ? ` ${pct}%` : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function PieChartPreview({
  config,
  rows,
  colors,
  height = 400,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  height?: number;
}) {
  const labelColumn = config.label_column as string;
  const valueColumn = config.value_column as string;
  const title = config.title as string;
  const aggregation = (config.aggregation as string) || "SUM";
  const { hidden, toggle } = useSeriesToggle();

  const pieData = useMemo(() => {
    if (!labelColumn || !valueColumn || !rows.length) return [];
    // Group raw values per label, then apply the chosen aggregation
    const grouped = new Map<string, number[]>();
    for (const row of rows) {
      const label = String(row[labelColumn] ?? "未知");
      const arr = grouped.get(label) ?? [];
      arr.push(Number(row[valueColumn]) || 0);
      grouped.set(label, arr);
    }
    let aggregated = Array.from(grouped.entries()).map(([name, values]) => ({
      name,
      value: aggregation === "COUNT" ? values.length : aggregateValues(values, aggregation),
    }));
    aggregated.sort((a, b) => b.value - a.value);
    // Keep the chart readable: top-N slices, the rest merged into 其他
    if (aggregated.length > PIE_MAX_SLICES) {
      const top = aggregated.slice(0, PIE_MAX_SLICES);
      const rest = aggregated.slice(PIE_MAX_SLICES).reduce((s, d) => s + d.value, 0);
      aggregated = [...top, { name: "其他", value: rest }];
    }
    return aggregated.map((d, i) => ({ ...d, ci: i }));
  }, [rows, labelColumn, valueColumn, aggregation]);

  // Hidden slices are excluded entirely so percentages recalculate over the
  // visible slices
  const visibleData = useMemo(() => pieData.filter((d) => !hidden[d.name]), [pieData, hidden]);
  const visibleTotal = useMemo(() => visibleData.reduce((s, d) => s + d.value, 0), [visibleData]);

  if (!labelColumn || !valueColumn) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请配置标签列和数值列
      </div>
    );
  }

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      <ResponsiveContainer width="100%" height={height}>
        <RePieChart>
          <Pie
            data={visibleData}
            dataKey="value"
            nameKey="name"
            cx="42%"
            cy="50%"
            outerRadius="80%"
            label={({ percent }: { percent?: number | string }) => {
              const p = Number(percent ?? 0);
              // Tiny slices get no label — values are shown in the legend
              return p >= PIE_MIN_LABEL_PERCENT ? `${(p * 100).toFixed(1)}%` : "";
            }}
            labelLine={{ stroke: AXIS_LINE_STROKE }}
          >
            {visibleData.map((d) => (
              <Cell key={d.name} fill={colors[d.ci % colors.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => compactNumber(v)} />
          <Legend
            layout="vertical"
            align="right"
            verticalAlign="middle"
            wrapperStyle={{ fontSize: 12 }}
            content={
              <PieLegendContent
                pieData={pieData}
                colors={colors}
                hidden={hidden}
                visibleTotal={visibleTotal}
                onToggle={toggle}
              />
            }
          />
        </RePieChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Scatter tooltip: shows X, the real Y variable name (not the internal key)
 *  and the point's category when a categorical split is active. */
function ScatterTooltipContent({
  active,
  payload,
  xColumn,
  groupByColumn,
  isTimeSeries,
  showTime,
}: {
  active?: boolean;
  payload?: { payload?: Record<string, unknown> }[];
  xColumn: string;
  groupByColumn: string;
  isTimeSeries: boolean;
  showTime: boolean;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  const yCol = String(point[SCATTER_YCOL_KEY] ?? "");
  const xRaw = point[xColumn];
  const xText = isTimeSeries ? formatAxisDate(String(xRaw ?? ""), showTime) : String(xRaw ?? "");
  const yText = formatNumber(point[SCATTER_Y_KEY], 2, true, "")
    .replace(/(\.\d*?)0+$/, "$1")
    .replace(/\.$/, "");
  const lines = [
    { label: xColumn, value: xText },
    ...(yCol ? [{ label: yCol, value: yText }] : []),
    ...(groupByColumn
      ? [{ label: groupByColumn, value: categoryValue(point, groupByColumn) }]
      : []),
  ];
  return (
    <div style={TOOLTIP_STYLE} className="space-y-0.5 bg-card px-3 py-2">
      {lines.map((l) => (
        <div key={l.label} className="flex items-center gap-2 whitespace-nowrap">
          <span className="text-muted-foreground">{l.label}:</span>
          <span className="font-medium">{l.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Scatter legend: icons must mirror the in-chart encoding (color + shape),
 *  which recharts' default legend (always circles) does not. */
function ScatterLegendContent({
  payload,
  meta,
  hidden,
  onToggle,
}: {
  payload?: { value?: unknown; color?: string }[];
  meta: Record<string, { color: string; shape: SymbolShape }>;
  hidden: Record<string, boolean>;
  onToggle: (name: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 py-1">
      {(payload ?? []).map((entry) => {
        const name = String(entry.value ?? "");
        const m = meta[name];
        const isHidden = !!hidden[name];
        const fill = isHidden ? "#94a3b8" : (m?.color ?? entry.color ?? "#94a3b8");
        const shape = m?.shape ?? "circle";
        return (
          <button
            key={name}
            type="button"
            onClick={() => onToggle(name)}
            className="inline-flex cursor-pointer items-center gap-1.5 border-none bg-transparent p-0"
          >
            <svg width={12} height={12} aria-hidden>
              {symbolElement(shape, 6, 6, 4.5, fill, `legend-${name}`)}
            </svg>
            <span
              style={isHidden ? { color: "#94a3b8", textDecoration: "line-through" } : undefined}
            >
              {name}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function ScatterChartPreview({
  config,
  rows,
  colors,
  dateColumns,
  height = 420,
  showBrush = true,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  dateColumns: string[];
  height?: number;
  showBrush?: boolean;
}) {
  const xColumn = config.x_column as string;
  const yColumns = useMemo(() => (config.y_columns as string[]) ?? [], [config.y_columns]);
  const title = config.title as string;
  const groupByColumn = (config.group_by_column as string) ?? "";
  const isTimeSeries = dateColumns.includes(xColumn);
  const showTime = (config.show_time as boolean) ?? false;
  const { hidden, toggle } = useSeriesToggle();

  const processedRows = useMemo(
    () => processTimeSeriesRows(rows, xColumn, yColumns, config, isTimeSeries),
    [rows, xColumn, yColumns, config, isTimeSeries],
  );

  const { rows: limitedRows, categories } = useMemo(
    () => limitCategories(processedRows, groupByColumn),
    [processedRows, groupByColumn],
  );

  if (!xColumn || yColumns.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请配置 X 轴和 Y 轴列
      </div>
    );
  }

  // Use a numeric axis when x values are numbers
  const xIsNumeric =
    limitedRows.length > 0 &&
    limitedRows.slice(0, 20).every((r) => r[xColumn] != null && !isNaN(Number(r[xColumn])));

  // Normalize to numeric points — recharts Scatter requires numeric x/y values,
  // and the YAxis needs an explicit dataKey (SCATTER_Y_KEY) to render at all
  const toPoints = (subset: Record<string, unknown>[], yCol: string) =>
    samplePoints(
      subset
        .map((r) => ({
          ...r,
          [xColumn]: xIsNumeric ? Number(r[xColumn]) : String(r[xColumn] ?? ""),
          [SCATTER_Y_KEY]: r[yCol] == null ? NaN : Number(r[yCol]),
          [SCATTER_YCOL_KEY]: yCol,
        }))
        .filter(
          (p) =>
            !isNaN(p[SCATTER_Y_KEY] as number) && (!xIsNumeric || !isNaN(p[xColumn] as number)),
        ),
    );

  // For scatter, we render one Scatter series per (yCol, category) pair
  const scatterSeries: { yCol: string; category: string; data: Record<string, unknown>[] }[] = [];
  if (groupByColumn && categories.length > 0) {
    for (const yCol of yColumns) {
      for (const cat of categories) {
        scatterSeries.push({
          yCol,
          category: cat,
          data: toPoints(
            limitedRows.filter((r) => categoryValue(r, groupByColumn) === cat),
            yCol,
          ),
        });
      }
    }
  } else {
    for (const yCol of yColumns) {
      scatterSeries.push({ yCol, category: "", data: toPoints(limitedRows, yCol) });
    }
  }

  // Color by y-column, shape by category
  const yColColorMap = new Map<string, number>();
  const catShapeMap = new Map<string, number>();
  let ci = 0;
  let si = 0;
  for (const s of scatterSeries) {
    if (!yColColorMap.has(s.yCol)) yColColorMap.set(s.yCol, ci++);
    if (s.category && !catShapeMap.has(s.category)) catShapeMap.set(s.category, si++);
  }

  // Resolve per-series name/color/shape once — shared by the chart and the legend
  const styledSeries = scatterSeries.map((s) => {
    const colorIdx = yColColorMap.get(s.yCol) ?? 0;
    const shapeIdx = s.category ? (catShapeMap.get(s.category) ?? 0) : 0;
    // With a single Y column the legend shows the class name only
    const name = s.category
      ? yColumns.length > 1
        ? `${s.category} · ${s.yCol}`
        : s.category
      : s.yCol;
    return {
      ...s,
      name,
      color: colors[colorIdx % colors.length],
      shape: SCATTER_SHAPES[shapeIdx % SCATTER_SHAPES.length],
    };
  });

  const legendMeta: Record<string, { color: string; shape: SymbolShape }> = {};
  for (const s of styledSeries) legendMeta[s.name] = { color: s.color, shape: s.shape };

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      {(config.y_label as string) && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{config.y_label as string}</p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ReScatterChart margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis
            dataKey={xColumn}
            name={xColumn}
            type={xIsNumeric ? "number" : "category"}
            domain={xIsNumeric ? ["auto", "auto"] : undefined}
            angle={xIsNumeric ? 0 : -30}
            textAnchor={xIsNumeric ? "middle" : "end"}
            height={xIsNumeric ? 30 : 55}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: AXIS_LINE_STROKE }}
            tickFormatter={(v: string) => (isTimeSeries ? formatAxisDate(v, showTime) : String(v))}
          />
          <YAxis
            dataKey={SCATTER_Y_KEY}
            type="number"
            width={60}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            tickFormatter={compactNumber}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={
              <ScatterTooltipContent
                xColumn={xColumn}
                groupByColumn={groupByColumn}
                isTimeSeries={isTimeSeries}
                showTime={showTime}
              />
            }
          />
          <Legend
            verticalAlign="top"
            wrapperStyle={LEGEND_STYLE}
            content={<ScatterLegendContent meta={legendMeta} hidden={hidden} onToggle={toggle} />}
          />
          {styledSeries.map((s) => (
            <Scatter
              key={`${s.yCol}||${s.category}`}
              name={s.name}
              data={s.data}
              fill={s.color}
              shape={s.shape}
              hide={!!hidden[s.name]}
            />
          ))}
          {isTimeSeries && showBrush && (
            <Brush
              dataKey={xColumn}
              height={20}
              stroke="#94a3b8"
              travellerWidth={8}
              tickFormatter={(v: string) => formatAxisDate(v, false)}
            />
          )}
        </ReScatterChart>
      </ResponsiveContainer>
      {(config.x_label as string) && (
        <p className="mt-2 text-center text-xs font-medium text-muted-foreground">
          {config.x_label as string}
        </p>
      )}
    </div>
  );
}

// ── Histogram Preview ────────────────────────────────────────────────

/**
 * Overlapping histogram bars: recharts splits multiple Bar series into
 * side-by-side slots, so expand each rect back to the full bin width
 * (band = slot width × series count, since barGap/barCategoryGap are 0)
 * to layer the distributions for comparison.
 */
function OverlappedHistogramBar(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
  seriesIndex?: number;
  seriesCount?: number;
}) {
  const {
    x = 0,
    y = 0,
    width = 0,
    height = 0,
    fill = "#2563eb",
    seriesIndex = 0,
    seriesCount = 1,
  } = props;
  if (width <= 0 || height <= 0) return <g />;
  const bandWidth = width * seriesCount;
  const bx = x - width * seriesIndex;
  return (
    <rect
      x={bx}
      y={y}
      width={bandWidth}
      height={height}
      fill={fill}
      fillOpacity={0.5}
      stroke={fill}
      strokeOpacity={0.9}
      strokeWidth={1}
    />
  );
}

export function HistogramChartPreview({
  config,
  rows,
  colors,
  height = 420,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  height?: number;
}) {
  const selected = useMemo(() => (config.columns as string[]) ?? [], [config.columns]);
  const bins = Math.min(200, Math.max(1, (config.bins as number) ?? 20));
  const title = config.title as string;
  const { hidden, toggle } = useSeriesToggle();

  const binData = useMemo(() => buildHistogramData(rows, selected, bins), [rows, selected, bins]);

  if (selected.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请选择至少一个数值列
      </div>
    );
  }
  if (!binData.length) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        无有效数值数据
      </div>
    );
  }

  const multiSeries = selected.length > 1;

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      {(config.y_label as string) && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{config.y_label as string}</p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={binData}
          margin={{ top: 5, right: 24, left: 8, bottom: 5 }}
          barCategoryGap={0}
          barGap={0}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey="__start"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: AXIS_LINE_STROKE }}
            tickFormatter={(v) => compactNumber(v)}
          />
          <YAxis
            width={50}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            tickFormatter={compactNumber}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: "rgba(148,163,184,0.12)" }}
            labelFormatter={(v, payload) => {
              const p = payload?.[0]?.payload as Record<string, unknown> | undefined;
              if (!p) return String(v);
              return `${compactNumber(p.__start)} – ${compactNumber(p.__end)}`;
            }}
            formatter={(v, name) => [`${compactNumber(v)} 条`, String(name)]}
          />
          <Legend
            verticalAlign="top"
            iconSize={10}
            wrapperStyle={LEGEND_STYLE}
            onClick={(entry) => {
              const e = entry as unknown as { value?: unknown };
              if (e.value != null) toggle(String(e.value));
            }}
            formatter={(value, entry) => {
              const e = entry as unknown as { value?: unknown };
              const isHidden = !!hidden[String(e.value)];
              return (
                <span
                  style={
                    isHidden ? { color: "#94a3b8", textDecoration: "line-through" } : undefined
                  }
                >
                  {String(value)}
                </span>
              );
            }}
          />
          {selected.map((col, i) => (
            <Bar
              key={col}
              dataKey={col}
              name={col}
              fill={colors[i % colors.length]}
              fillOpacity={multiSeries ? undefined : 0.85}
              shape={
                multiSeries ? (
                  <OverlappedHistogramBar seriesIndex={i} seriesCount={selected.length} />
                ) : undefined
              }
              hide={!!hidden[col]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      {(config.x_label as string) && (
        <p className="mt-2 text-center text-xs font-medium text-muted-foreground">
          {config.x_label as string}
        </p>
      )}
    </div>
  );
}

// ── Boxplot Preview ─────────────────────────────────────────────────

/** Custom bar shape that renders a full boxplot from the q1–q3 range bar. */
function BoxplotShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
  payload?: BoxSummary & { _fill?: string };
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (!payload || height <= 0) return <g />;
  const { q1, median, q3, whiskerLow, whiskerHigh, outliers, _fill } = payload;
  const range = q3 - q1;
  if (range <= 0) return <g />;
  const color = _fill || "#2563eb";
  const pxPerUnit = height / range;
  // y corresponds to q3 (top); SVG y grows downward
  const yOf = (v: number) => y + (q3 - v) * pxPerUnit;
  const cx = x + width / 2;
  const boxW = Math.min(width, 72);
  const bx = cx - boxW / 2;
  const capW = boxW * 0.6;
  return (
    <g>
      {/* whisker stems */}
      <line x1={cx} y1={yOf(whiskerHigh)} x2={cx} y2={y} stroke={color} strokeWidth={1.5} />
      <line x1={cx} y1={y + height} x2={cx} y2={yOf(whiskerLow)} stroke={color} strokeWidth={1.5} />
      {/* whisker caps */}
      <line
        x1={cx - capW / 2}
        y1={yOf(whiskerHigh)}
        x2={cx + capW / 2}
        y2={yOf(whiskerHigh)}
        stroke={color}
        strokeWidth={1.5}
      />
      <line
        x1={cx - capW / 2}
        y1={yOf(whiskerLow)}
        x2={cx + capW / 2}
        y2={yOf(whiskerLow)}
        stroke={color}
        strokeWidth={1.5}
      />
      {/* box (q1–q3) */}
      <rect
        x={bx}
        y={y}
        width={boxW}
        height={height}
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={1.5}
      />
      {/* median */}
      <line
        x1={bx}
        y1={yOf(median)}
        x2={bx + boxW}
        y2={yOf(median)}
        stroke={color}
        strokeWidth={2.5}
      />
      {/* outliers */}
      {outliers.map((v, i) => (
        <circle key={i} cx={cx} cy={yOf(v)} r={3} fill="none" stroke={color} strokeWidth={1.5} />
      ))}
    </g>
  );
}

export function BoxplotChartPreview({
  config,
  rows,
  colors,
  height = 420,
}: {
  config: Record<string, unknown>;
  rows: Record<string, unknown>[];
  colors: string[];
  height?: number;
}) {
  const categoryColumn = (config.category_column as string) ?? "";
  const valueColumn = (config.value_column as string) ?? "";
  const title = config.title as string;

  const summaries = useMemo(() => {
    if (!valueColumn) return [];
    const grouped = new Map<string, number[]>();
    for (const row of rows) {
      const raw = row[valueColumn];
      if (raw == null) continue;
      const v = Number(raw);
      if (isNaN(v)) continue;
      const cat = categoryColumn ? categoryValue(row, categoryColumn) : "全部";
      const arr = grouped.get(cat) ?? [];
      arr.push(v);
      grouped.set(cat, arr);
    }
    // Keep the top-N categories by frequency for readability
    const cats = Array.from(grouped.keys());
    const kept =
      categoryColumn && cats.length > MAX_CATEGORIES
        ? cats
            .sort((a, b) => (grouped.get(b)?.length ?? 0) - (grouped.get(a)?.length ?? 0))
            .slice(0, MAX_CATEGORIES)
        : cats;
    return kept
      .sort((a, b) => a.localeCompare(b))
      .map((cat, i) => ({
        ...computeBoxSummary(grouped.get(cat) ?? [], cat),
        boxRange: undefined as unknown as [number, number],
        _fill: colors[i % colors.length],
      }))
      .map((s) => ({ ...s, boxRange: [s.q1, s.q3] as [number, number] }));
  }, [rows, categoryColumn, valueColumn, colors]);

  if (!valueColumn) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        请选择数值列
      </div>
    );
  }
  if (!summaries.length) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        无有效数值数据
      </div>
    );
  }

  // Y domain must cover whiskers and outliers, not just the q1–q3 boxes
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of summaries) {
    lo = Math.min(lo, s.whiskerLow, ...(s.outliers.length ? s.outliers : [s.whiskerLow]));
    hi = Math.max(hi, s.whiskerHigh, ...(s.outliers.length ? s.outliers : [s.whiskerHigh]));
  }
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.06;

  return (
    <div>
      {title && <p className="mb-3 text-center text-sm font-semibold">{title}</p>}
      {(config.y_label as string) && (
        <p className="mb-1 text-xs font-medium text-muted-foreground">{config.y_label as string}</p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={summaries} margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey="cat"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: AXIS_LINE_STROKE }}
          />
          <YAxis
            width={60}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            tickFormatter={compactNumber}
            domain={[lo - pad, hi + pad]}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: "rgba(148,163,184,0.12)" }}
            formatter={(_, __, item) => {
              const p = item.payload as BoxSummary;
              return [
                `中位数 ${compactNumber(p.median)} · Q1 ${compactNumber(p.q1)} · Q3 ${compactNumber(p.q3)}`,
                p.cat,
              ];
            }}
          />
          <Bar dataKey="boxRange" shape={<BoxplotShape />} />
        </BarChart>
      </ResponsiveContainer>
      {(config.x_label as string) && (
        <p className="mt-2 text-center text-xs font-medium text-muted-foreground">
          {config.x_label as string}
        </p>
      )}
    </div>
  );
}
