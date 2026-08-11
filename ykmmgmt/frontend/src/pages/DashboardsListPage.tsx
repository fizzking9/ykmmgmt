import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import {
  useDashboards,
  useUpdateDashboard,
  useDeleteDashboard,
  type DashboardListResponse,
} from "@/hooks/useDashboards";
import { useDashboardBuilderContext } from "@/contexts/DashboardBuilderContext";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
        <h3 className="text-lg font-semibold">重命名仪表盘</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          为仪表盘「{target.name}」输入新名称（名称必须唯一）。
        </p>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="输入新名称"
          className="mt-3 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
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
      </div>
    </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
        <h3 className="text-lg font-semibold">确认删除</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          确定要删除仪表盘「{target.name}」吗？此操作不可撤销。
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
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function DashboardsListPage() {
  const navigate = useNavigate();
  const builder = useDashboardBuilderContext();

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

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">仪表盘</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" />
            新建仪表盘
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isRefetching}>
            {isRefetching ? (
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
                <TableHead>名称</TableHead>
                <TableHead>描述</TableHead>
                <TableHead>瓦片数</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-[260px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-48" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-8" />
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
          <p className="text-lg text-muted-foreground">暂无仪表盘，请先创建仪表盘</p>
          <Button className="mt-4" variant="outline" onClick={handleCreate}>
            创建仪表盘
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
                  <TableHead>名称</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>瓦片数</TableHead>
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
                  <TableHead className="w-[260px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((dash) => (
                  <TableRow key={dash.id}>
                    <TableCell className="max-w-[200px] truncate font-medium" title={dash.name}>
                      {dash.name}
                    </TableCell>
                    <TableCell
                      className="max-w-[260px] truncate text-muted-foreground"
                      title={dash.description ?? ""}
                    >
                      {dash.description || "—"}
                    </TableCell>
                    <TableCell>{dash.tile_count}</TableCell>
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
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/dashboards/builder/${dash.id}`)}
                        >
                          <Pencil className="mr-1 h-4 w-4" />
                          编辑
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
    </div>
  );
}
