import { useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { GridLayout, type LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import html2canvas from "html2canvas";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard, useDeleteDashboard, type DashboardTile } from "@/hooks/useDashboards";
import {
  useVisualization,
  useVisualizationTileData,
  type VizDataTimeParams,
} from "@/hooks/useVisualizations";
import { useIsDesktop } from "@/hooks/useMediaQuery";
import { useMeasuredWidth } from "@/hooks/useMeasuredWidth";
import { DATE_PRESETS, computePresetRange, type DatePresetKey } from "@/lib/datePresets";
import { InfoTip } from "@/components/dashboard/InfoTip";
import { TextTileMarkdown } from "@/components/dashboard/TextTileMarkdown";
import {
  KpiTileBody,
  TileLoadingBody,
  VisualizationTileBody,
} from "@/components/dashboard/DashboardTiles";
import {
  ArrowLeft,
  Pencil,
  Trash2,
  RefreshCw,
  Maximize2,
  Loader2,
  LayoutGrid,
  Download,
  FileText,
  Link2,
  Info,
  X,
} from "lucide-react";

// ── Global time filter state ────────────────────────────────────────────────

interface GlobalTimeFilter {
  start: string;
  end: string;
  granularity: string; // "auto" | day/week/month/quarter/year
  agg: string; // "auto" | SUM/...
}

/** Granularity selector is a segmented tab strip: 默认 | 日 | 周 | 月 | 季 | 年. */
const GRANULARITY_TABS = [
  { value: "auto", label: "默认" },
  { value: "day", label: "日" },
  { value: "week", label: "周" },
  { value: "month", label: "月" },
  { value: "quarter", label: "季" },
  { value: "year", label: "年" },
];

function isFilterActive(f: GlobalTimeFilter): boolean {
  return !!(
    f.start ||
    f.end ||
    (f.granularity && f.granularity !== "auto") ||
    (f.agg && f.agg !== "auto")
  );
}

// ── Visualization tile ──────────────────────────────────────────────────────

function VizTileBody({
  tile,
  filter,
  filterActive,
  height,
  onRefresh,
}: {
  tile: DashboardTile;
  filter: GlobalTimeFilter;
  filterActive: boolean;
  height?: number;
  onRefresh?: () => void;
}) {
  const { data: viz } = useVisualization(tile.visualization_id ?? undefined);
  const dateColumn = (viz?.config_json.date_column as string) ?? "";
  const timeEnabled = !!dateColumn;

  // "auto" resolves to the visualization's own time-profile defaults.
  const params: VizDataTimeParams = useMemo(() => {
    if (!timeEnabled) return {};
    const p: VizDataTimeParams = {};
    if (filter.start) p.start = filter.start;
    if (filter.end) p.end = filter.end;
    if (filter.granularity && filter.granularity !== "auto") {
      p.granularity = filter.granularity;
    } else if (viz?.config_json.default_granularity) {
      p.granularity = viz.config_json.default_granularity as string;
    }
    if (filter.agg && filter.agg !== "auto") {
      p.agg = filter.agg;
    } else if (viz?.config_json.default_agg) {
      p.agg = viz.config_json.default_agg as string;
    }
    return p;
  }, [timeEnabled, filter, viz]);

  const { data, isLoading, isError, error } = useVisualizationTileData(
    tile.visualization_id ?? undefined,
    params,
  );

  const showHint = filterActive && !timeEnabled;
  // Charts fill the tile exactly (no scroll) so exports capture them whole;
  // table tiles keep their own scrolling.
  const isTable = data?.chart_type === "table";

  return (
    <div className="relative h-full">
      {showHint && (
        <span className="absolute left-1.5 top-1.5 z-10 rounded bg-muted/90 px-1.5 py-0.5 text-[10px] text-muted-foreground">
          不响应时间筛选
        </span>
      )}
      <div className={isTable ? "h-full overflow-auto" : "h-full overflow-hidden"}>
        {isLoading || !data ? (
          <TileLoadingBody />
        ) : isError ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-3 text-sm text-red-600">
            数据加载失败：{error instanceof Error ? error.message : "未知错误"}
            {onRefresh && (
              <Button variant="outline" size="sm" onClick={onRefresh}>
                重试
              </Button>
            )}
          </div>
        ) : (
          <VisualizationTileBody data={data} height={height} fill={!isTable} />
        )}
      </div>
    </div>
  );
}

// ── Tile frame: clean tile with a hover toolbar ─────────────────────────
// No permanent header — the tile name lives in the toolbar's info tooltip,
// keeping the dashboard overview quiet and WYSIWYG.

function TileFrame({
  title,
  children,
  onRefresh,
  refreshing,
  onMaximize,
}: {
  title: string;
  children: React.ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  onMaximize?: () => void;
}) {
  return (
    <div className="group relative flex h-full flex-col overflow-hidden rounded-lg border bg-background shadow-sm">
      <div className="min-h-0 flex-1">{children}</div>
      <div className="absolute right-1.5 top-1.5 z-10 flex items-center gap-0.5 rounded-md border bg-background/95 p-0.5 shadow-sm opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        <span title={`瓦片：${title}`} className="cursor-help p-1 text-muted-foreground">
          <Info className="h-3.5 w-3.5" />
        </span>
        {onRefresh && (
          <button
            type="button"
            title="刷新瓦片"
            className="rounded p-1 text-muted-foreground hover:bg-muted"
            onClick={onRefresh}
            disabled={refreshing}
          >
            {refreshing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </button>
        )}
        {onMaximize && (
          <button
            type="button"
            title="全屏查看"
            className="rounded p-1 text-muted-foreground hover:bg-muted"
            onClick={onMaximize}
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function DashboardDisplayPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isDesktop = useIsDesktop();

  const { data: dashboard, isLoading, isError } = useDashboard(id);
  const deleteDashboard = useDeleteDashboard();

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [maxTile, setMaxTile] = useState<DashboardTile | null>(null);
  const [filter, setFilter] = useState<GlobalTimeFilter>({
    start: "",
    end: "",
    granularity: "auto",
    agg: "auto",
  });
  // Which quick preset filled the date inputs (null = custom range)
  const [activePreset, setActivePreset] = useState<DatePresetKey | null>(null);
  const [exporting, setExporting] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const filterActive = isFilterActive(filter);

  const applyPreset = (key: DatePresetKey) => {
    const range = computePresetRange(key);
    setFilter((f) => ({ ...f, start: range.start, end: range.end }));
    setActivePreset(key);
  };

  const clearFilter = () => {
    setFilter({ start: "", end: "", granularity: "auto", agg: "auto" });
    setActivePreset(null);
  };

  // Grid container measurement — ref-callback based so the late-rendered
  // grid container (after loading) is measured correctly
  const { width: gridWidth, mounted: gridMounted, containerRef: gridRef } = useMeasuredWidth();

  const tiles = useMemo(() => dashboard?.layout_json ?? [], [dashboard]);
  const sortedTiles = useMemo(() => [...tiles].sort((a, b) => a.y - b.y || a.x - b.x), [tiles]);

  const layout: LayoutItem[] = useMemo(
    () => tiles.map((t) => ({ i: t.i, x: t.x, y: t.y, w: t.w, h: t.h })),
    [tiles],
  );

  // Per-tile manual refresh — the ONLY refetch path besides filter changes
  const refreshTile = (tile: DashboardTile) => {
    if (tile.tile_type === "visualization" && tile.visualization_id) {
      queryClient.invalidateQueries({
        queryKey: ["visualizationData", tile.visualization_id],
      });
    } else if (tile.tile_type === "kpi_card" && tile.config) {
      queryClient.invalidateQueries({ queryKey: ["kpiTileData", tile.config.view_id] });
    }
  };

  // Refresh the whole dashboard: every visualization + KPI tile
  const handleRefreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["visualizationData"] });
    queryClient.invalidateQueries({ queryKey: ["kpiTileData"] });
  };

  // Export the rendered grid as PNG (bottom padding on the capture target
  // protects bottom-edge content from html2canvas clipping)
  const handleExportPng = async () => {
    if (!exportRef.current) return;
    setExporting(true);
    try {
      await new Promise((r) => setTimeout(r, 150));
      const canvas = await html2canvas(exportRef.current, {
        backgroundColor: "#ffffff",
        scale: 2,
      });
      const link = document.createElement("a");
      link.download = `${dashboard?.name ?? "数据看板"}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      toast.success("PNG 导出成功");
    } catch {
      toast.error("导出失败");
    } finally {
      setExporting(false);
    }
  };

  // PDF via the browser print dialog (print CSS hides chrome/controls)
  const handleExportPdf = () => {
    toast.info("请在打印对话框中选择「另存为 PDF」");
    setTimeout(() => window.print(), 400);
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href).then(
      () => toast.success("链接已复制到剪贴板"),
      () => toast.error("复制失败"),
    );
  };

  const tileTitle = (tile: DashboardTile): string => {
    if (tile.tile_type === "kpi_card") return tile.config?.label ?? "KPI 卡";
    if (tile.tile_type === "text") return "文本";
    return "可视化";
  };

  const renderTileBody = (tile: DashboardTile, height?: number) => {
    switch (tile.tile_type) {
      case "visualization":
        return (
          <VizTileBody
            tile={tile}
            filter={filter}
            filterActive={filterActive}
            height={height}
            onRefresh={() => refreshTile(tile)}
          />
        );
      case "kpi_card":
        return tile.config ? <KpiTileBody config={tile.config} /> : null;
      case "text":
        return <TextTileMarkdown content={tile.content ?? ""} />;
    }
  };

  // ── Loading / error / not-found states ───────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-[480px] w-full" />
      </div>
    );
  }

  if (isError || !dashboard) {
    return (
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate("/dashboards")}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回看板列表
        </Button>
        <div className="mt-8 rounded-md bg-muted/30 p-16 text-center">
          <LayoutGrid className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">看板不存在</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/dashboards")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{dashboard.name}</h2>
            {dashboard.description && (
              <p className="text-sm text-muted-foreground">{dashboard.description}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <Button variant="outline" size="sm" onClick={handleRefreshAll}>
            <RefreshCw className="mr-1 h-4 w-4" />
            刷新
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportPng} disabled={exporting}>
            {exporting ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-1 h-4 w-4" />
            )}
            导出 PNG
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportPdf}>
            <FileText className="mr-1 h-4 w-4" />
            导出 PDF
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopyLink}>
            <Link2 className="mr-1 h-4 w-4" />
            复制链接
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/dashboards/builder/${dashboard.id}`)}
          >
            <Pencil className="mr-1 h-4 w-4" />
            编辑
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            删除
          </Button>
        </div>
      </div>

      {/* Global time controls — tools only; presets sit beside the date pickers */}
      <Card className="mb-4 print:hidden">
        <CardContent className="py-3">
          <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
            <div className="flex h-9 items-center">
              <InfoTip text="时间筛选仅作用于配置了时间列的可视化瓦片；其他瓦片保持不变。" />
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {DATE_PRESETS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => applyPreset(p.key)}
                  className={cn(
                    "rounded-md border px-2.5 py-1.5 text-sm transition-colors",
                    activePreset === p.key
                      ? "border-primary bg-primary/10 font-medium text-primary"
                      : "border-border text-muted-foreground hover:bg-muted",
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">开始日期</label>
              <input
                type="date"
                value={filter.start}
                onChange={(e) => {
                  setFilter((f) => ({ ...f, start: e.target.value }));
                  setActivePreset(null);
                }}
                className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">结束日期</label>
              <input
                type="date"
                value={filter.end}
                onChange={(e) => {
                  setFilter((f) => ({ ...f, end: e.target.value }));
                  setActivePreset(null);
                }}
                className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">时间粒度</label>
              <div className="inline-flex h-9 items-stretch overflow-hidden rounded-md border border-input bg-transparent">
                {GRANULARITY_TABS.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setFilter((f) => ({ ...f, granularity: t.value }))}
                    className={cn(
                      "border-r border-input px-3 text-sm transition-colors last:border-r-0",
                      filter.granularity === t.value
                        ? "bg-primary font-medium text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="w-36">
              <label className="mb-1 block text-xs font-medium">聚合方式</label>
              <Select
                value={filter.agg}
                onValueChange={(v) => setFilter((f) => ({ ...f, agg: v ?? "auto" }))}
              >
                <SelectTrigger>
                  <SelectValue>
                    {filter.agg === "auto"
                      ? "按可视化默认"
                      : ({
                          SUM: "求和",
                          COUNT: "计数",
                          AVG: "平均值",
                          MIN: "最小值",
                          MAX: "最大值",
                        }[filter.agg] ?? filter.agg)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent
                  align="start"
                  sideOffset={4}
                  alignItemWithTrigger={false}
                  className="bg-background"
                >
                  <SelectItem value="auto">按可视化默认</SelectItem>
                  <SelectItem value="SUM">求和</SelectItem>
                  <SelectItem value="COUNT">计数</SelectItem>
                  <SelectItem value="AVG">平均值</SelectItem>
                  <SelectItem value="MIN">最小值</SelectItem>
                  <SelectItem value="MAX">最大值</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {filterActive && (
              <Button variant="ghost" size="sm" onClick={clearFilter}>
                清除筛选
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tiles */}
      {sortedTiles.length === 0 ? (
        <div className="rounded-md bg-muted/30 p-16 text-center">
          <LayoutGrid className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">该看板暂无瓦片</p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => navigate(`/dashboards/builder/${dashboard.id}`)}
          >
            去编辑
          </Button>
        </div>
      ) : (
        /* pb-4 protects bottom-edge content during PNG export (html2canvas) */
        <div ref={exportRef} className="pb-4">
          {isDesktop ? (
            <div ref={gridRef}>
              {gridMounted && (
                <GridLayout
                  width={gridWidth}
                  layout={layout}
                  gridConfig={{ cols: 12, rowHeight: 80, margin: [12, 12] }}
                  dragConfig={{ enabled: false }}
                  resizeConfig={{ enabled: false }}
                >
                  {tiles.map((tile) => (
                    <div key={tile.i}>
                      <TileFrame
                        title={tileTitle(tile)}
                        onRefresh={tile.tile_type !== "text" ? () => refreshTile(tile) : undefined}
                        onMaximize={() => setMaxTile(tile)}
                      >
                        {renderTileBody(tile, Math.max(160, tile.h * 92 - 30))}
                      </TileFrame>
                    </div>
                  ))}
                </GridLayout>
              )}
            </div>
          ) : (
            /* Mobile: read-only vertical stacking (no drag/resize) */
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">小屏模式：瓦片按只读单列展示。</p>
              {sortedTiles.map((tile) => (
                <div key={tile.i} style={{ height: tile.tile_type === "kpi_card" ? 160 : 360 }}>
                  <TileFrame
                    title={tileTitle(tile)}
                    onRefresh={tile.tile_type !== "text" ? () => refreshTile(tile) : undefined}
                    onMaximize={() => setMaxTile(tile)}
                  >
                    {renderTileBody(tile, 260)}
                  </TileFrame>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Full-screen single-tile dialog */}
      {maxTile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="flex h-[88vh] w-[94vw] max-w-6xl flex-col rounded-lg bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="text-base font-semibold">{tileTitle(maxTile)}</h3>
              <Button variant="ghost" size="sm" onClick={() => setMaxTile(null)} title="关闭">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-4">{renderTileBody(maxTile, 520)}</div>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {deleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDeleteOpen(false)} />
          <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold">确认删除</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              确定要删除看板「{dashboard.name}」吗？此操作不可撤销。
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteOpen(false)}>
                取消
              </Button>
              <Button
                variant="destructive"
                disabled={deleteDashboard.isPending}
                onClick={() => {
                  deleteDashboard.mutate(dashboard.id, {
                    onSuccess: () => navigate("/dashboards"),
                  });
                }}
              >
                {deleteDashboard.isPending ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-1 h-4 w-4" />
                )}
                确定
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
