import { useCallback, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog } from "@/components/ui/dialog";
import {
  useDashboards,
  useUpdateDashboard,
  useDeleteDashboard,
  type DashboardListResponse,
} from "@/hooks/useDashboards";
import { useDashboardBuilderContext } from "@/contexts/DashboardBuilderContext";
import { useAuth } from "@/contexts/AuthContext";
import { DashboardExportCanvas } from "@/components/dashboard/DashboardExportCanvas";
import { downloadBlob, elementToPngBlob, batchStamp, sanitizeFilename } from "@/lib/exportPng";
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
  LayoutGrid,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Plus,
  SpellCheck,
  Download,
} from "lucide-react";

const PAGE_SIZE = 20;

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

// ── Rename Dialog ───────────────────────────────────────────────────────────

function RenameDialog({ target, onClose }: { target: DashboardListResponse; onClose: () => void }) {
  const updateDashboard = useUpdateDashboard();
  const [name, setName] = useState(target.name);

  const handleConfirm = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    updateDashboard.mutate(
      { id: target.id, name: trimmed },
      {
        onSuccess: () => onClose(),
      },
    );
  };

  return (
    <Dialog open onClose={onClose} title="重命名看板">
      <p className="text-sm text-muted-foreground">
        为看板「{target.name}」输入新名称（名称必须唯一）。
      </p>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="输入新名称"
        className="mt-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={updateDashboard.isPending}>
          取消
        </Button>
        <Button
          onClick={handleConfirm}
          disabled={!name.trim() || name.trim() === target.name || updateDashboard.isPending}
        >
          {updateDashboard.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
          确定
        </Button>
      </div>
    </Dialog>
  );
}

// ── Delete Confirmation Dialog ──────────────────────────────────────────────

function DeleteConfirmDialog({
  target,
  onClose,
}: {
  target: DashboardListResponse;
  onClose: () => void;
}) {
  const deleteDashboard = useDeleteDashboard();
  return (
    <Dialog open onClose={onClose} title="确认删除">
      <p className="text-sm text-muted-foreground">
        确定要删除看板「{target.name}」吗？此操作不可撤销。
      </p>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={deleteDashboard.isPending}>
          取消
        </Button>
        <Button
          variant="destructive"
          disabled={deleteDashboard.isPending}
          onClick={() => {
            deleteDashboard.mutate(target.id, { onSuccess: () => onClose() });
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
    </Dialog>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function DashboardsListPage() {
  const navigate = useNavigate();
  const builder = useDashboardBuilderContext();
  const { isAdmin } = useAuth();

  const { data: dashboards, isLoading, isError, error, refetch, isRefetching } = useDashboards();

  // Fresh builder state for a new dashboard — otherwise a stale draft
  // (name/tiles/editingId) from a previous session would leak in.
  const handleCreate = () => {
    builder.resetState();
    navigate("/dashboards/builder");
  };

  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState<TimeSortCol>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [renameTarget, setRenameTarget] = useState<DashboardListResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DashboardListResponse | null>(null);

  // ── PNG export & batch selection ──────────────────────────────────────
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // Queue of dashboards pending PNG export (one at a time, off-screen)
  const [exportQueue, setExportQueue] = useState<DashboardListResponse[]>([]);
  const [exportProgress, setExportProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  const exportWrapRef = useRef<HTMLDivElement>(null);
  // Batch identifier ("dashboards_YYYY-MM-DD_HH-mm-ss") prefixed onto
  // every filename in the current batch; null for single exports
  const exportBatchRef = useRef<string | null>(null);
  const exportTotalRef = useRef(0);
  const exportDoneRef = useRef(0);
  const exporting = exportQueue.length > 0;

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
    const list = [...(dashboards ?? [])];
    if (!sortDir) return list;
    list.sort((a, b) => new Date(a[sortCol]).getTime() - new Date(b[sortCol]).getTime());
    if (sortDir === "desc") list.reverse();
    return list;
  }, [dashboards, sortCol, sortDir]);

  const totalPages = sortedRows.length ? Math.max(1, Math.ceil(sortedRows.length / PAGE_SIZE)) : 1;
  const pagedRows = useMemo(
    () => sortedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [sortedRows, page],
  );

  // ── Batch selection helpers ────────────────────────────────────────────

  const enterSelectionMode = () => {
    setSelectionMode(true);
    setSelectedIds(new Set());
  };

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedIds(new Set());
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // 全选 covers the whole list (all pages), not just the current page
  const selectAll = () => setSelectedIds(new Set(sortedRows.map((d) => d.id)));
  const clearAll = () => setSelectedIds(new Set());

  // ── PNG export ────────────────────────────────────────────────────────
  // Every file downloads straight to the browser's default download
  // location (same as single exports — no save-as dialog). Batch files get
  // a "dashboards_YYYY-MM-DD_HH-mm-ss" prefix so they group together;
  // a real subfolder there is impossible without a directory picker.

  const beginExport = (targets: DashboardListResponse[], batch: boolean) => {
    if (targets.length === 0 || exporting) return;
    exportTotalRef.current = targets.length;
    exportDoneRef.current = 0;
    setExportProgress({ done: 0, total: targets.length });
    exportBatchRef.current = batch ? batchStamp("dashboards") : null;
    setExportQueue(targets);
  };

  const handleCanvasReady = useCallback(
    async (ok: boolean) => {
      const current = exportQueue[0];
      if (!current) return;
      if (ok && exportWrapRef.current) {
        try {
          const blob = await elementToPngBlob(exportWrapRef.current);
          const baseName = sanitizeFilename(current.name);
          const filename = exportBatchRef.current
            ? `${exportBatchRef.current}_${baseName}.png`
            : `${baseName}.png`;
          downloadBlob(blob, filename);
          exportDoneRef.current += 1;
        } catch {
          toast.error(`「${current.name}」PNG 导出失败`);
        }
      } else {
        toast.error(`「${current.name}」看板加载失败，已跳过`);
      }
      setExportProgress({ done: exportDoneRef.current, total: exportTotalRef.current });
      const remaining = exportQueue.slice(1);
      setExportQueue(remaining);
      if (remaining.length === 0) {
        const batch = exportBatchRef.current;
        if (exportDoneRef.current > 0) {
          if (batch) {
            toast.success(
              `已导出 ${exportDoneRef.current} 张 PNG 至下载目录（文件名前缀：${batch}）`,
            );
          } else {
            toast.success(`已导出 ${exportDoneRef.current} 张 PNG`);
          }
        }
        exportBatchRef.current = null;
        setExportProgress(null);
      }
    },
    [exportQueue],
  );

  const exportSelected = () => {
    const targets = sortedRows.filter((d) => selectedIds.has(d.id));
    exitSelectionMode();
    beginExport(targets, true);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">数据看板</h2>
        <div className="flex items-center gap-2">
          {exporting && exportProgress && (
            <span className="text-sm text-muted-foreground">
              正在导出 {exportProgress.done}/{exportProgress.total}…
            </span>
          )}
          {selectionMode ? (
            <>
              <span className="text-sm text-muted-foreground">已选 {selectedIds.size} 项</span>
              <Button variant="outline" size="sm" onClick={selectAll} disabled={exporting}>
                全选
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clearAll}
                disabled={selectedIds.size === 0 || exporting}
              >
                清空
              </Button>
              <Button
                size="sm"
                onClick={exportSelected}
                disabled={selectedIds.size === 0 || exporting}
              >
                {exporting ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-1 h-4 w-4" />
                )}
                导出所选
              </Button>
              <Button variant="outline" size="sm" onClick={exitSelectionMode} disabled={exporting}>
                取消
              </Button>
            </>
          ) : (
            <>
              {isAdmin && (
                <Button variant="outline" size="sm" onClick={handleCreate}>
                  <Plus className="mr-2 h-4 w-4" />
                  新建看板
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={enterSelectionMode}
                disabled={exporting || !dashboards || dashboards.length === 0}
              >
                <Download className="mr-2 h-4 w-4" />
                批量导出
              </Button>
              <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
                {isRefetching ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                刷新
              </Button>
            </>
          )}
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
                {selectionMode && <TableHead className="w-10">选择</TableHead>}
                <TableHead>名称</TableHead>
                <TableHead>描述</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-[320px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  {selectionMode && <TableCell />}
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-48" />
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
      {!isLoading && !isError && dashboards && dashboards.length === 0 && (
        <div className="rounded-md bg-muted/30 p-16 text-center">
          <LayoutGrid className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">暂无看板，请先创建看板</p>
          <Button className="mt-4" variant="outline" onClick={handleCreate}>
            创建看板
          </Button>
        </div>
      )}

      {/* Table */}
      {!isError && dashboards && dashboards.length > 0 && (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  {selectionMode && <TableHead className="w-10">选择</TableHead>}
                  <TableHead>名称</TableHead>
                  <TableHead>描述</TableHead>
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
                  <TableHead className="w-[320px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((dash) => (
                  <TableRow key={dash.id}>
                    {selectionMode && (
                      <TableCell className="w-10">
                        <input
                          type="checkbox"
                          aria-label={`选择 ${dash.name}`}
                          checked={selectedIds.has(dash.id)}
                          onChange={() => toggleSelected(dash.id)}
                          disabled={exporting}
                          className="h-4 w-4"
                        />
                      </TableCell>
                    )}
                    <TableCell className="max-w-[200px] truncate font-medium" title={dash.name}>
                      {dash.name}
                    </TableCell>
                    <TableCell
                      className="max-w-[260px] truncate text-muted-foreground"
                      title={dash.description ?? ""}
                    >
                      {dash.description || "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(dash.created_at)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(dash.updated_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/dashboards/${dash.id}`)}
                        >
                          <Eye className="mr-1 h-4 w-4" />
                          查看
                        </Button>
                        {isAdmin && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => navigate(`/dashboards/builder/${dash.id}`)}
                            >
                              <Pencil className="mr-1 h-4 w-4" />
                              编辑
                            </Button>
                            {/* 导出 PNG */}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => beginExport([dash], false)}
                              disabled={exporting}
                            >
                              <Download className="mr-1 h-4 w-4" />
                              导出
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setRenameTarget(dash)}>
                              <SpellCheck className="mr-1 h-4 w-4" />
                              重命名
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(dash)}
                            >
                              <Trash2 className="mr-1 h-4 w-4" />
                              删除
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {dashboards.length > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                共 {dashboards.length} 条记录，第{" "}
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

      {/* Dialogs */}
      {renameTarget && <RenameDialog target={renameTarget} onClose={() => setRenameTarget(null)} />}
      {deleteTarget && (
        <DeleteConfirmDialog target={deleteTarget} onClose={() => setDeleteTarget(null)} />
      )}

      {/* Offscreen export canvas — renders one queued dashboard at a time */}
      <div
        ref={exportWrapRef}
        aria-hidden
        style={{ position: "fixed", top: 0, left: -20000, width: 1280 }}
      >
        {exportQueue[0] && (
          <DashboardExportCanvas
            key={exportQueue[0].id}
            dashboardId={exportQueue[0].id}
            onReady={handleCanvasReady}
          />
        )}
      </div>
    </div>
  );
}
