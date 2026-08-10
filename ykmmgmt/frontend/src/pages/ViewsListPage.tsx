import { useState } from "react";
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
import { useViews, useViewData, useDeleteView, type ViewListResponse } from "@/hooks/useViews";
import {
  Eye,
  Pencil,
  Trash2,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  X,
  Loader2,
  RefreshCw,
} from "lucide-react";

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

// ── Delete Confirmation Dialog ─────────────────────────────────────────────

function DeleteConfirmDialog({
  open,
  viewName,
  onConfirm,
  onCancel,
  isPending,
}: {
  open: boolean;
  viewName: string;
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
          确定要删除视图「{viewName}」吗？此操作不可撤销。
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

// ── Preview Dialog ─────────────────────────────────────────────────────────

function PreviewDialog({
  open,
  viewId,
  viewName,
  onClose,
}: {
  open: boolean;
  viewId: string;
  viewName: string;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const size = 20;

  const { data, isLoading, isError, error } = useViewData(open ? viewId : undefined, page, size);

  const totalPages = data ? Math.ceil(data.total / data.size) : 0;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      {/* Dialog */}
      <div className="relative z-10 flex max-h-[85vh] w-full max-w-5xl flex-col rounded-lg border bg-background shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">预览: {viewName}</h3>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="rounded-md bg-red-50 p-6 text-center">
              <p className="text-red-700">
                加载失败：
                {error instanceof Error ? error.message : "未知错误"}
              </p>
            </div>
          ) : data && data.rows.length === 0 ? (
            <div className="rounded-md bg-muted/30 p-12 text-center">
              <p className="text-lg text-muted-foreground">暂无数据</p>
            </div>
          ) : data ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    {data.columns.map((col) => (
                      <TableHead key={col} className="max-w-[250px] truncate whitespace-nowrap">
                        {col}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row, i) => (
                    <TableRow key={i}>
                      {data.columns.map((col) => (
                        <TableCell
                          key={col}
                          className="max-w-[250px] truncate"
                          title={String(row[col] ?? "")}
                        >
                          {row[col] != null ? String(row[col]) : ""}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </div>

        {/* Footer — Pagination */}
        {data && (
          <div className="flex items-center justify-between border-t px-6 py-3">
            <p className="text-sm text-muted-foreground">
              共 {data.total} 条记录，第{" "}
              <input
                type="number"
                min={1}
                max={totalPages || 1}
                value={data.page}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val) && val >= 1 && val <= totalPages) {
                    setPage(val);
                  }
                }}
                className="inline w-16 rounded border px-1 py-0.5 text-center text-sm"
              />{" "}
              / {totalPages || 1} 页（每页最多 {data.size} 条）
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
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function ViewsListPage() {
  const navigate = useNavigate();
  const { data: views, isLoading, isError, error, refetch } = useViews();
  const deleteView = useDeleteView();

  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<ViewListResponse | null>(null);

  const previewView = views?.find((v) => v.id === previewId);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">数据视图</h2>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          刷新
        </Button>
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
                <TableHead>创建时间</TableHead>
                <TableHead className="w-[200px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
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
      {!isLoading && !isError && views && views.length === 0 && (
        <div className="rounded-md bg-muted/30 p-16 text-center">
          <Eye className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">暂无保存的视图，请先创建数据视图</p>
          <Button className="mt-4" variant="outline" onClick={() => navigate("/views/builder")}>
            创建视图
          </Button>
        </div>
      )}

      {/* Table */}
      {!isError && views && views.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>描述</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="w-[240px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {views.map((view) => (
                <TableRow key={view.id}>
                  <TableCell className="font-medium max-w-[200px] truncate" title={view.name}>
                    {view.name}
                  </TableCell>
                  <TableCell
                    className="max-w-[300px] truncate text-muted-foreground"
                    title={view.description ?? ""}
                  >
                    {view.description || "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{formatDate(view.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {/* 可视化 */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/visualizations/builder?view_id=${view.id}`)}
                      >
                        <BarChart3 className="mr-1 h-4 w-4" />
                        可视化
                      </Button>

                      {/* 预览 */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setPreviewId(view.id);
                          setPreviewName(view.name);
                        }}
                      >
                        <Eye className="mr-1 h-4 w-4" />
                        预览
                      </Button>

                      {/* 编辑 */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/views/builder/${view.id}`)}
                      >
                        <Pencil className="mr-1 h-4 w-4" />
                        编辑
                      </Button>

                      {/* 删除 */}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(view)}
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
      )}

      {/* Preview Dialog */}
      {previewId && previewView && (
        <PreviewDialog
          open={!!previewId}
          viewId={previewId}
          viewName={previewName}
          onClose={() => {
            setPreviewId(null);
            setPreviewName("");
          }}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={!!deleteTarget}
        viewName={deleteTarget?.name ?? ""}
        onConfirm={() => {
          if (deleteTarget) {
            deleteView.mutate(deleteTarget.id, {
              onSuccess: () => {
                setDeleteTarget(null);
                refetch();
              },
            });
          }
        }}
        onCancel={() => setDeleteTarget(null)}
        isPending={deleteView.isPending}
      />
    </div>
  );
}
