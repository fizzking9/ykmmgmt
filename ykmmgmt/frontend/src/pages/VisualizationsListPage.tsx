import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useViews } from "@/hooks/useViews";
import {
  useVisualizations,
  useVisualizationData,
  useDeleteVisualization,
  type VisualizationListResponse,
} from "@/hooks/useVisualizations";
import { CHART_TYPES, type ChartType } from "@/contexts/VisualizationBuilderContext";
import {
  VisualizationRenderer,
  isThumbnailChartType,
} from "@/components/visualization/VisualizationRenderer";
import {
  SortableTimeHeader,
  nextSortDir,
  type TimeSortCol,
  type SortDir,
} from "@/components/SortableTimeHeader";
import {
  Eye,
  Pencil,
  Trash2,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Table2,
  CreditCard,
  Plus,
} from "lucide-react";

const PAGE_SIZE = 20;

// ── Helpers ────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function chartTypeLabel(chartType: string): string {
  return CHART_TYPES.find((ct) => ct.value === chartType)?.label ?? chartType;
}

// ── Thumbnail Cell ─────────────────────────────────────────────────────────
// Chart types render a zoomed-out copy of the true visualization; data is
// cached with staleTime: Infinity so pagination / tab navigation never
// re-queries. Thumbnails are clickable and open the full-size view.

function ThumbnailCell({ viz }: { viz: VisualizationListResponse }) {
  if (!isThumbnailChartType(viz.chart_type)) {
    // No thumbnail for table / KPI card — show a type icon placeholder
    return (
      <div className="flex h-24 w-44 items-center justify-center rounded-md border bg-muted/30 text-muted-foreground">
        {viz.chart_type === "kpi_card" ? (
          <CreditCard className="h-6 w-6" />
        ) : (
          <Table2 className="h-6 w-6" />
        )}
      </div>
    );
  }
  return <ChartThumbnail viz={viz} />;
}

function ChartThumbnail({ viz }: { viz: VisualizationListResponse }) {
  const navigate = useNavigate();
  const { data, isLoading } = useVisualizationData(viz.id);

  if (isLoading || !data) {
    return <Skeleton className="h-24 w-44" />;
  }

  return (
    <div
      onClick={() => navigate(`/visualizations/${viz.id}`)}
      title="点击查看"
      className="h-24 w-44 cursor-pointer overflow-hidden rounded-md border bg-background transition-colors hover:border-primary"
    >
      {/* Zoomed-out render of the true visualization: 704px wide chart scaled
          ×0.25 → 176px (w-44), so the thumbnail mirrors the real chart */}
      <div
        className="pointer-events-none origin-top-left select-none"
        style={{ width: 704, transform: "scale(0.25)" }}
      >
        <VisualizationRenderer
          chartType={viz.chart_type as ChartType}
          config={data.config_json}
          columns={data.columns}
          rows={data.rows}
          height={320}
        />
      </div>
    </div>
  );
}

// ── Delete Confirmation Dialog ─────────────────────────────────────────────

function DeleteConfirmDialog({
  open,
  vizName,
  onConfirm,
  onCancel,
  isPending,
}: {
  open: boolean;
  vizName: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
      {/* Dialog */}
      <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
        <h3 className="text-lg font-semibold">确认删除</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          确定要删除可视化「{vizName}」吗？此操作不可撤销。
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isPending}>
            取消
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
            {isPending ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-1 h-4 w-4" />
            )}
            确定
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function VisualizationsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: visualizations,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useVisualizations();
  const { data: views } = useViews();
  const deleteVisualization = useDeleteVisualization();

  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState<TimeSortCol>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [deleteTarget, setDeleteTarget] = useState<VisualizationListResponse | null>(null);

  const viewNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const v of views ?? []) map.set(v.id, v.name);
    return map;
  }, [views]);

  const handleSort = (col: TimeSortCol) => {
    if (sortCol === col) {
      setSortDir(nextSortDir(sortDir));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(1);
  };

  // Default (sortDir null): backend order — created_at descending
  const sortedRows = useMemo(() => {
    const list = [...(visualizations ?? [])];
    if (!sortDir) return list;
    list.sort((a, b) => new Date(a[sortCol]).getTime() - new Date(b[sortCol]).getTime());
    if (sortDir === "desc") list.reverse();
    return list;
  }, [visualizations, sortCol, sortDir]);

  const totalPages = sortedRows.length ? Math.max(1, Math.ceil(sortedRows.length / PAGE_SIZE)) : 1;
  const pagedRows = useMemo(
    () => sortedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [sortedRows, page],
  );

  // Manual refresh: re-fetch the list AND invalidate the cached thumbnail
  // data so charts re-render with possibly new data. This is the ONLY path
  // that re-fetches visualization data (no auto-refresh / polling).
  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["visualizationData"] });
    refetch();
  };

  const refreshing = isRefetching;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">可视化</h2>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/visualizations/builder", { state: { fresh: true } })}
          >
            <Plus className="mr-2 h-4 w-4" />
            新建
          </Button>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            刷新
          </Button>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="rounded-md bg-red-50 p-8 text-center">
          <p className="mb-4 text-red-700">
            加载失败：{error instanceof Error ? error.message : "未知错误"}
          </p>
          <Button variant="outline" onClick={() => refetch()}>
            重试
          </Button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>缩略图</TableHead>
                <TableHead>名称</TableHead>
                <TableHead>图表类型</TableHead>
                <TableHead>来源视图</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-[200px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-24 w-44" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-40" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-40" />
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Skeleton className="h-8 w-16" />
                      <Skeleton className="h-8 w-16" />
                      <Skeleton className="h-8 w-16" />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && visualizations && visualizations.length === 0 && (
        <div className="rounded-md bg-muted/30 p-16 text-center">
          <BarChart3 className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">暂无保存的可视化，请先创建可视化</p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => navigate("/visualizations/builder", { state: { fresh: true } })}
          >
            创建可视化
          </Button>
        </div>
      )}

      {/* Table */}
      {!isError && visualizations && visualizations.length > 0 && (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>缩略图</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>图表类型</TableHead>
                  <TableHead>来源视图</TableHead>
                  <TableHead>
                    <SortableTimeHeader
                      label="创建时间"
                      col="created_at"
                      sortCol={sortCol}
                      sortDir={sortDir}
                      onSort={handleSort}
                    />
                  </TableHead>
                  <TableHead>
                    <SortableTimeHeader
                      label="更新时间"
                      col="updated_at"
                      sortCol={sortCol}
                      sortDir={sortDir}
                      onSort={handleSort}
                    />
                  </TableHead>
                  <TableHead className="w-[200px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((viz) => (
                  <TableRow key={viz.id}>
                    <TableCell>
                      <ThumbnailCell viz={viz} />
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate font-medium" title={viz.name}>
                      {viz.name}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{chartTypeLabel(viz.chart_type)}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-muted-foreground">
                      {viewNameById.get(viz.view_id) ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(viz.created_at)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(viz.updated_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {/* 查看 */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/visualizations/${viz.id}`)}
                        >
                          <Eye className="mr-1 h-4 w-4" />
                          查看
                        </Button>

                        {/* 编辑 */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/visualizations/builder/${viz.id}`)}
                        >
                          <Pencil className="mr-1 h-4 w-4" />
                          编辑
                        </Button>

                        {/* 删除 */}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setDeleteTarget(viz)}
                        >
                          <Trash2 className="mr-1 h-4 w-4" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination (client-side; never triggers data fetches) */}
          {visualizations.length > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                共 {visualizations.length} 条记录，第{" "}
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={page}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val >= 1 && val <= totalPages) {
                      setPage(val);
                    }
                  }}
                  className="inline w-16 rounded border px-1 py-0.5 text-center text-sm"
                />{" "}
                / {totalPages} 页
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={!!deleteTarget}
        vizName={deleteTarget?.name ?? ""}
        onConfirm={() => {
          if (deleteTarget) {
            deleteVisualization.mutate(deleteTarget.id, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        onCancel={() => setDeleteTarget(null)}
        isPending={deleteVisualization.isPending}
      />
    </div>
  );
}
