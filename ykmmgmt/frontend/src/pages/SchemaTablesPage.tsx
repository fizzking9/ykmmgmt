import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DeleteTableDialog } from "@/components/schema/DeleteTableDialog";
import { InfoTip } from "@/components/dashboard/InfoTip";
import { useSchemaTables, type SchemaTableInfo } from "@/hooks/useSchema";

export default function SchemaTablesPage() {
  const navigate = useNavigate();
  const tablesQuery = useSchemaTables();
  const [deleting, setDeleting] = useState<SchemaTableInfo | null>(null);

  const tables = tablesQuery.data ?? [];

  return (
    <div className="space-y-4 p-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <div className="flex items-center gap-1.5">
              <CardTitle>数据表管理</CardTitle>
              <InfoTip text="查看、创建、编辑和删除数据表。" />
            </div>
          </div>
          <Button onClick={() => navigate("/schema/create")}>
            <Plus className="h-4 w-4" />
            新建数据表
          </Button>
        </CardHeader>
        <CardContent>
          {tablesQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : tablesQuery.isError ? (
            <p className="text-sm text-destructive">加载数据表列表失败，请稍后重试</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>中文名称</TableHead>
                  <TableHead>英文名称</TableHead>
                  <TableHead>列数</TableHead>
                  <TableHead>行数</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tables.map((t) => (
                  <TableRow key={t.name}>
                    <TableCell className="font-medium">{t.chinese_name}</TableCell>
                    <TableCell className="font-mono text-muted-foreground">{t.name}</TableCell>
                    <TableCell>{t.column_count}</TableCell>
                    <TableCell>{t.row_count}</TableCell>
                    <TableCell>
                      {t.read_only ? (
                        <Badge variant="secondary">预置业务表</Badge>
                      ) : (
                        <Badge>自建数据表</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="xs"
                          variant="ghost"
                          title="查看"
                          onClick={() => navigate(`/schema/tables/${t.name}`)}
                        >
                          <Eye className="h-3.5 w-3.5" />
                          查看
                        </Button>
                        {!t.read_only && (
                          <>
                            <Button
                              size="xs"
                              variant="ghost"
                              title="编辑"
                              onClick={() => navigate(`/schema/tables/${t.name}?edit=1`)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              编辑
                            </Button>
                            <Button
                              size="xs"
                              variant="ghost"
                              title="删除"
                              onClick={() => setDeleting(t)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
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
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            提示：数据浏览请前往{" "}
            <Link to="/data-browser" className="text-primary underline-offset-2 hover:underline">
              数据浏览
            </Link>{" "}
            页面。
          </p>
        </CardContent>
      </Card>

      <DeleteTableDialog
        tableName={deleting?.name ?? null}
        chineseName={deleting?.chinese_name ?? ""}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
