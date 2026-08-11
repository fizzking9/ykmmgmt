import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { GridLayout, useContainerWidth, type LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDashboardBuilderContext } from "@/contexts/DashboardBuilderContext";
import {
  useDashboards,
  useDashboard,
  useCreateDashboard,
  useUpdateDashboard,
  type DashboardTile,
  type KpiTileConfig,
} from "@/hooks/useDashboards";
import { useVisualizations } from "@/hooks/useVisualizations";
import { useViews, useViewFullData } from "@/hooks/useViews";
import { useIsDesktop } from "@/hooks/useMediaQuery";
import { CHART_TYPES } from "@/contexts/VisualizationBuilderContext";
import { TextTileMarkdown } from "@/components/dashboard/TextTileMarkdown";
import { AGG_LABELS } from "@/components/dashboard/DashboardTiles";
import {
  Plus,
  Save,
  Loader2,
  Trash2,
  GripVertical,
  Pencil,
  BarChart3,
  Type,
  Gauge,
  RotateCcw,
  MonitorSmartphone,
} from "lucide-react";

// ── Text tile editor (textarea + preview toggle) ──────────────────────────

function TextTileEditor({
  content,
  onChange,
}: {
  content: string;
  onChange: (value: string) => void;
}) {
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  return (
    <div className="flex h-full flex-col">
      <div className="flex gap-1 pb-1">
        <button
          type="button"
          className={`rounded px-2 py-0.5 text-xs ${mode === "edit" ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted/50"}`}
          onClick={() => setMode("edit")}
        >
          编辑
        </button>
        <button
          type="button"
          className={`rounded px-2 py-0.5 text-xs ${mode === "preview" ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted/50"}`}
          onClick={() => setMode("preview")}
        >
          预览
        </button>
      </div>
      {mode === "edit" ? (
        <textarea
          value={content}
          onChange={(e) => onChange(e.target.value)}
          placeholder="支持简单 Markdown：# 标题、**加粗**、- 列表"
          className="h-full w-full resize-none rounded-md border border-input bg-transparent p-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      ) : (
        <div className="h-full overflow-auto rounded-md border bg-background">
          <TextTileMarkdown content={content} />
        </div>
      )}
    </div>
  );
}

// ── KPI tile config panel ─────────────────────────────────────────────────

const KPI_AGG_OPTIONS: KpiTileConfig["agg"][] = ["SUM", "COUNT", "AVG", "MIN", "MAX"];

function KpiTilePanel({
  open,
  editingTile,
  onConfirm,
  onClose,
}: {
  open: boolean;
  editingTile: DashboardTile | null;
  onConfirm: (config: KpiTileConfig) => void;
  onClose: () => void;
}) {
  const { data: views } = useViews();
  const [viewId, setViewId] = useState(editingTile?.config?.view_id ?? "");
  const [valueColumn, setValueColumn] = useState(editingTile?.config?.value_column ?? "");
  const [label, setLabel] = useState(editingTile?.config?.label ?? "");
  const [agg, setAgg] = useState<KpiTileConfig["agg"]>(editingTile?.config?.agg ?? "SUM");

  const { data: viewData } = useViewFullData(viewId || undefined);
  const columns = useMemo(() => viewData?.columns ?? [], [viewData]);

  // Reset column selection when the view changes
  useEffect(() => {
    setValueColumn(editingTile?.config?.view_id === viewId ? (valueColumn ?? "") : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewId]);

  if (!open) return null;

  const handleConfirm = () => {
    if (!viewId) {
      toast.error("请选择数据视图");
      return;
    }
    if (!valueColumn && agg !== "COUNT") {
      toast.error("请选择数值列");
      return;
    }
    if (!label.trim()) {
      toast.error("请输入卡片标签");
      return;
    }
    onConfirm({
      view_id: viewId,
      value_column: valueColumn,
      label: label.trim(),
      agg,
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{editingTile ? "编辑 KPI 卡" : "添加 KPI 卡"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium">
            数据视图 <span className="text-red-500">*</span>
          </label>
          <Select value={viewId} onValueChange={(v) => setViewId(v ?? "")}>
            <SelectTrigger>
              <SelectValue placeholder="选择数据视图">
                {views?.find((v) => v.id === viewId)?.name}
              </SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {(views ?? []).map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            数值列 {agg !== "COUNT" && <span className="text-red-500">*</span>}
          </label>
          <Select
            value={valueColumn || "__none__"}
            onValueChange={(v) => setValueColumn(!v || v === "__none__" ? "" : v)}
          >
            <SelectTrigger>
              <SelectValue>
                {valueColumn || (agg === "COUNT" ? "（计数无需数值列）" : "选择列")}
              </SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              <SelectItem value="__none__">（计数无需数值列）</SelectItem>
              {columns.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            标签 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="如：退款总额"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">聚合方式</label>
          <Select value={agg} onValueChange={(v) => v && setAgg(v as KpiTileConfig["agg"])}>
            <SelectTrigger>
              <SelectValue>{AGG_LABELS[agg]}</SelectValue>
            </SelectTrigger>
            <SelectContent
              align="start"
              sideOffset={4}
              alignItemWithTrigger={false}
              className="bg-background"
            >
              {KPI_AGG_OPTIONS.map((a) => (
                <SelectItem key={a} value={a}>
                  {AGG_LABELS[a]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2 pt-1">
          <Button size="sm" onClick={handleConfirm}>
            {editingTile ? "保存修改" : "添加"}
          </Button>
          <Button size="sm" variant="outline" onClick={onClose}>
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function DashboardBuilderPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isDesktop = useIsDesktop();

  const builder = useDashboardBuilderContext();
  const { state } = builder;

  const { data: dashboards } = useDashboards();
  const { data: existingDashboard } = useDashboard(id);
  const { data: visualizations } = useVisualizations();
  const createDashboard = useCreateDashboard();
  const updateDashboard = useUpdateDashboard();

  const loadedRef = useRef<string | null>(null);

  // Grid container measurement (react-grid-layout v2 replaces WidthProvider)
  const { width: gridWidth, mounted: gridMounted, containerRef: gridRef } = useContainerWidth();

  // KPI panel state
  const [kpiPanelOpen, setKpiPanelOpen] = useState(false);
  const [kpiEditingTile, setKpiEditingTile] = useState<DashboardTile | null>(null);

  // Name conflict dialogs
  const [overwriteTarget, setOverwriteTarget] = useState<{ id: string; name: string } | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");

  // ── Load existing dashboard in edit mode ─────────────────────────────
  useEffect(() => {
    if (existingDashboard && loadedRef.current !== existingDashboard.id) {
      loadedRef.current = existingDashboard.id;
      builder.loadDashboard(existingDashboard);
    }
  }, [existingDashboard, builder]);

  const vizNameById = useMemo(() => {
    const map = new Map<string, { name: string; chartType: string }>();
    for (const v of visualizations ?? []) map.set(v.id, { name: v.name, chartType: v.chart_type });
    return map;
  }, [visualizations]);

  const views = useViews();
  const viewNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const v of views.data ?? []) map.set(v.id, v.name);
    return map;
  }, [views.data]);

  // ── Grid wiring ────────────────────────────────────────────────────────

  const layout: LayoutItem[] = useMemo(
    () => state.tiles.map((t) => ({ i: t.i, x: t.x, y: t.y, w: t.w, h: t.h })),
    [state.tiles],
  );

  const handleLayoutChange = useCallback(
    (newLayout: readonly LayoutItem[]) => {
      builder.applyLayout(newLayout.map((l) => ({ i: l.i, x: l.x, y: l.y, w: l.w, h: l.h })));
    },
    [builder],
  );

  // ── Save flow ──────────────────────────────────────────────────────────

  const buildTiles = useCallback((): DashboardTile[] => {
    return state.tiles.map((t) => ({
      i: t.i,
      tile_type: t.tile_type,
      visualization_id: t.tile_type === "visualization" ? (t.visualization_id ?? null) : null,
      x: t.x,
      y: t.y,
      w: t.w,
      h: t.h,
      content: t.tile_type === "text" ? (t.content ?? "") : null,
      config: t.tile_type === "kpi_card" ? (t.config ?? null) : null,
    }));
  }, [state.tiles]);

  const persist = useCallback(
    async (name: string, targetId?: string) => {
      const payload = {
        name,
        description: state.description.trim() || null,
        layout_json: buildTiles(),
      };
      try {
        if (targetId) {
          const result = await updateDashboard.mutateAsync({ id: targetId, ...payload });
          loadedRef.current = result.id;
          builder.setEditingId(result.id);
          navigate(`/dashboards/builder/${result.id}`, { replace: true });
        } else {
          const result = await createDashboard.mutateAsync(payload);
          loadedRef.current = result.id;
          builder.setEditingId(result.id);
          navigate(`/dashboards/builder/${result.id}`, { replace: true });
        }
      } catch (err) {
        // Server-side duplicate (race) — prompt for a new name and retry
        if (err instanceof Error && err.message.includes("已存在")) {
          setRenameValue(name);
          setRenameOpen(true);
        }
        // other errors already toasted by the mutation
      }
    },
    [state.description, buildTiles, createDashboard, updateDashboard, builder, navigate],
  );

  const handleSave = useCallback(async () => {
    const trimmedName = state.name.trim();
    if (!trimmedName) {
      toast.error("请输入仪表盘名称");
      return;
    }

    const existingWithName = dashboards?.find((d) => d.name === trimmedName);
    if (existingWithName && existingWithName.id !== state.editingId) {
      // Name taken by another dashboard — mirror views/visualizations flow:
      // confirm before overwriting the existing dashboard via PUT
      setOverwriteTarget({ id: existingWithName.id, name: trimmedName });
      return;
    }

    await persist(trimmedName, state.editingId ?? existingWithName?.id);
  }, [state.name, state.editingId, dashboards, persist]);

  const handleRenameRetry = useCallback(async () => {
    const newName = renameValue.trim();
    if (!newName) {
      toast.error("请输入新的仪表盘名称");
      return;
    }
    setRenameOpen(false);
    builder.setName(newName);
    await persist(newName, state.editingId ?? undefined);
  }, [renameValue, builder, persist, state.editingId]);

  const isSaving = createDashboard.isPending || updateDashboard.isPending;

  const handleReset = useCallback(() => {
    loadedRef.current = null;
    builder.resetState();
    navigate("/dashboards/builder", { replace: true });
  }, [builder, navigate]);

  // ── KPI panel handlers ─────────────────────────────────────────────────

  const openKpiPanel = (tile: DashboardTile | null) => {
    setKpiEditingTile(tile);
    setKpiPanelOpen(true);
  };

  const handleKpiConfirm = (config: KpiTileConfig) => {
    if (kpiEditingTile) {
      builder.updateTile(kpiEditingTile.i, { config });
    } else {
      builder.addTile("kpi_card", { config });
    }
    setKpiPanelOpen(false);
    setKpiEditingTile(null);
  };

  // ── Tile rendering inside the grid ─────────────────────────────────────

  const renderTileBody = (tile: DashboardTile) => {
    switch (tile.tile_type) {
      case "visualization": {
        const viz = tile.visualization_id ? vizNameById.get(tile.visualization_id) : undefined;
        return (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-3 text-center">
            <BarChart3 className="h-6 w-6 text-muted-foreground" />
            {viz ? (
              <>
                <p className="text-sm font-medium">{viz.name}</p>
                <Badge variant="secondary">
                  {CHART_TYPES.find((ct) => ct.value === viz.chartType)?.label ?? viz.chartType}
                </Badge>
              </>
            ) : (
              <p className="text-sm text-red-600">可视化不存在或已被删除</p>
            )}
          </div>
        );
      }
      case "text":
        return (
          <TextTileEditor
            content={tile.content ?? ""}
            onChange={(value) => builder.updateTile(tile.i, { content: value })}
          />
        );
      case "kpi_card": {
        const cfg = tile.config;
        return (
          <div className="flex h-full flex-col items-center justify-center gap-1 p-3 text-center">
            <Gauge className="h-5 w-5 text-muted-foreground" />
            <p className="text-sm font-medium">{cfg?.label || "KPI 卡"}</p>
            {cfg && (
              <p className="text-xs text-muted-foreground">
                {viewNameById.get(cfg.view_id) ?? "未知视图"} · {AGG_LABELS[cfg.agg]}
                {cfg.value_column ? ` · ${cfg.value_column}` : ""}
              </p>
            )}
            <Button variant="ghost" size="sm" onClick={() => openKpiPanel(tile)}>
              <Pencil className="mr-1 h-3 w-3" />
              编辑
            </Button>
          </div>
        );
      }
    }
  };

  const tileTypeLabel = (tile: DashboardTile) =>
    tile.tile_type === "visualization" ? "可视化" : tile.tile_type === "text" ? "文本" : "KPI 卡";

  // ── Mobile hint ────────────────────────────────────────────────────────

  if (!isDesktop) {
    return (
      <div className="rounded-md bg-muted/30 p-16 text-center">
        <MonitorSmartphone className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
        <p className="text-lg text-muted-foreground">仪表盘编辑需要桌面端视口（宽度 ≥ 1024px）</p>
        <p className="mt-2 text-sm text-muted-foreground">
          请在桌面浏览器中打开以拖拽和调整瓦片布局；移动端仅支持只读查看。
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">仪表盘构建器</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleReset}>
            <RotateCcw className="mr-1 h-4 w-4" />
            重置
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-1 h-4 w-4" />
            )}
            保存
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Left panel — settings & add tiles */}
        <div className="space-y-4">
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
                  onChange={(e) => builder.setName(e.target.value)}
                  placeholder="输入仪表盘名称"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">描述</label>
                <textarea
                  value={state.description}
                  onChange={(e) => builder.setDescription(e.target.value)}
                  placeholder="可选描述"
                  rows={2}
                  className="w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">添加瓦片</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => builder.addTile("text", { content: "## 新标题" })}
                >
                  <Type className="mr-1 h-4 w-4" />
                  添加文本
                </Button>
                <Button variant="outline" size="sm" onClick={() => openKpiPanel(null)}>
                  <Gauge className="mr-1 h-4 w-4" />
                  添加 KPI 卡
                </Button>
              </div>

              {kpiPanelOpen && (
                <KpiTilePanel
                  open={kpiPanelOpen}
                  editingTile={kpiEditingTile}
                  onConfirm={handleKpiConfirm}
                  onClose={() => {
                    setKpiPanelOpen(false);
                    setKpiEditingTile(null);
                  }}
                />
              )}

              <div>
                <p className="mb-2 text-sm font-medium">添加可视化</p>
                {(visualizations ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    暂无已保存的可视化，请先在可视化构建器中创建。
                  </p>
                ) : (
                  <div className="max-h-72 space-y-1 overflow-auto">
                    {(visualizations ?? []).map((viz) => (
                      <div
                        key={viz.id}
                        className="flex items-center justify-between gap-2 rounded-md border px-2 py-1.5"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm" title={viz.name}>
                            {viz.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {CHART_TYPES.find((ct) => ct.value === viz.chart_type)?.label ??
                              viz.chart_type}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="添加到仪表盘"
                          onClick={() =>
                            builder.addTile("visualization", { visualization_id: viz.id })
                          }
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right panel — grid canvas */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">布局画布</CardTitle>
            <p className="text-xs text-muted-foreground">
              拖动手柄调整位置，拖动右下角调整大小；点击瓦片右上角 × 删除。
            </p>
          </CardHeader>
          <CardContent>
            {state.tiles.length === 0 ? (
              <div className="rounded-md bg-muted/30 p-12 text-center text-muted-foreground">
                暂无瓦片 — 从左侧添加可视化、文本或 KPI 卡
              </div>
            ) : (
              <div ref={gridRef as React.RefObject<HTMLDivElement>}>
                {gridMounted && (
                  <GridLayout
                    width={gridWidth}
                    layout={layout}
                    gridConfig={{ cols: 12, rowHeight: 80, margin: [12, 12] }}
                    dragConfig={{ handle: ".tile-drag-handle" }}
                    onLayoutChange={handleLayoutChange}
                  >
                    {state.tiles.map((tile) => (
                      <div key={tile.i} className="rounded-lg border bg-background shadow-sm">
                        <div className="flex items-center justify-between border-b px-2 py-1">
                          <div className="tile-drag-handle flex cursor-move items-center gap-1 text-xs text-muted-foreground">
                            <GripVertical className="h-3.5 w-3.5" />
                            {tileTypeLabel(tile)}
                          </div>
                          <button
                            type="button"
                            title="删除瓦片"
                            className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-destructive"
                            onClick={() => builder.removeTile(tile.i)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="h-[calc(100%-29px)] overflow-hidden p-1">
                          {renderTileBody(tile)}
                        </div>
                      </div>
                    ))}
                  </GridLayout>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Overwrite confirmation dialog (name exists → update that dashboard) */}
      {overwriteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOverwriteTarget(null)} />
          <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold">名称已存在</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              仪表盘名称「{overwriteTarget.name}」已存在，是否修改该仪表盘？
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOverwriteTarget(null)}>
                取消
              </Button>
              <Button
                onClick={async () => {
                  const target = overwriteTarget;
                  setOverwriteTarget(null);
                  await persist(target.name, target.id);
                }}
              >
                确定修改
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Rename dialog (server 409 → prompt for a new name and retry) */}
      {renameOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={() => setRenameOpen(false)} />
          <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold">名称冲突</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              仪表盘名称已存在，请输入新的名称后重试。
            </p>
            <input
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder="输入新的仪表盘名称"
              className="mt-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            />
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRenameOpen(false)}>
                取消
              </Button>
              <Button onClick={handleRenameRetry}>保存</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
