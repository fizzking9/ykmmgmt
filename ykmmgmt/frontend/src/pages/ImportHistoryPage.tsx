import { useImportHistory, ImportJobItem } from "@/hooks/useImportHistory";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { useState } from "react";

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="default">{status === "completed" ? "成功" : status}</Badge>;
    case "failed":
      return <Badge variant="destructive">{status === "failed" ? "失败" : status}</Badge>;
    case "running":
    case "pending":
      return (
        <Badge variant="secondary" className="bg-yellow-100 text-yellow-700">
          处理中
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

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

function HistoryRow({ item }: { item: ImportJobItem }) {
  return (
    <TableRow>
      <TableCell className="font-medium max-w-[180px] truncate" title={item.file_name}>
        {item.file_name}
      </TableCell>
      <TableCell className="whitespace-nowrap">{formatDate(item.created_at)}</TableCell>
      <TableCell>{statusBadge(item.status)}</TableCell>
      <TableCell className="text-right">{item.total_rows}</TableCell>
      <TableCell>{item.target_table}</TableCell>
      <TableCell className="text-right text-green-600">{item.rows_inserted}</TableCell>
      <TableCell className="text-right text-blue-600">{item.rows_updated}</TableCell>
      <TableCell className="text-right text-yellow-600">{item.rows_skipped}</TableCell>
      <TableCell className="text-right text-red-600">{item.rows_rejected}</TableCell>
      <TableCell>
        <Button variant="ghost" size="sm" disabled>
          详情
        </Button>
      </TableCell>
    </TableRow>
  );
}

function LoadingSkeleton() {
  return Array.from({ length: 5 }).map((_, i) => (
    <TableRow key={i}>
      {Array.from({ length: 10 }).map((_, j) => (
        <TableCell key={j}>
          <Skeleton className="h-5 w-full" />
        </TableCell>
      ))}
    </TableRow>
  ));
}

export default function ImportHistoryPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const { data, isLoading, isError, error, refetch } = useImportHistory(page, pageSize);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">导入历史</h2>
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

      {/* Empty state */}
      {!isLoading && !isError && data && data.items.length === 0 && (
        <div className="rounded-md bg-muted/30 p-16 text-center">
          <p className="text-lg text-muted-foreground">暂无导入记录</p>
          <p className="mt-1 text-sm text-muted-foreground">上传文件后将在此显示导入历史</p>
        </div>
      )}

      {/* Table */}
      {!isError && (data?.items.length ?? 0) > 0 && (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>文件名</TableHead>
                  <TableHead className="whitespace-nowrap">上传时间</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">总行数</TableHead>
                  <TableHead>目标数据表</TableHead>
                  <TableHead className="text-right">新增行数</TableHead>
                  <TableHead className="text-right">更新行数</TableHead>
                  <TableHead className="text-right">跳过行数</TableHead>
                  <TableHead className="text-right">拒绝行数</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <LoadingSkeleton />
                ) : (
                  data!.items.map((item) => <HistoryRow key={item.id} item={item} />)
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                共 {data!.total} 条记录，第 {page} / {totalPages} 页
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
