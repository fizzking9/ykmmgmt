import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
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
import { EditTableDialog } from "@/components/schema/EditTableDialog";
import { useSchemaTableDetail } from "@/hooks/useSchema";
import { useNavigate } from "react-router-dom";

export default function SchemaTableDetailPage() {
  const { name } = useParams<{ name: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const detailQuery = useSchemaTableDetail(name);

  const [editOpen, setEditOpen] = useState(searchParams.get("edit") === "1");
  const [deleteOpen, setDeleteOpen] = useState(false);

  const detail = detailQuery.data;

  if (detailQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (detailQuery.isError || !detail) {
    return (
      <div className="p-6">
        <p className="text-sm text-destructive">加载表结构失败，请返回重试</p>
        <Link to="/schema" className="mt-2 inline-block text-sm text-primary">
          返回数据表管理
        </Link>
      </div>
    );
  }

  const visibleColumns = detail.columns.filter((c) => !c.internal);

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/schema")}>
          <ArrowLeft className="h-4 w-4" />
          返回
        </Button>
        <h1 className="text-xl font-semibold">
          {detail.chinese_name}
          <span className="ml-2 font-mono text-sm font-normal text-muted-foreground">
            {detail.name}
          </span>
        </h1>
        {detail.read_only ? (
          <Badge variant="secondary">预置业务表（仅可查看）</Badge>
        ) : (
          <Badge>自建数据表</Badge>
        )}
        <span className="flex-1" />
        {!detail.read_only && (
          <>
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              <Pencil className="h-4 w-4" />
              编辑表结构
            </Button>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4" />
              删除数据表
            </Button>
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>列结构</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>列名</TableHead>
                <TableHead>中文标签</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>可空</TableHead>
                <TableHead>唯一</TableHead>
                <TableHead>主键</TableHead>
                <TableHead>默认值</TableHead>
                <TableHead>描述</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.columns.map((col) => (
                <TableRow key={col.name}>
                  <TableCell className="font-mono">
                    {col.name}
                    {col.internal && (
                      <Badge variant="outline" className="ml-2">
                        系统列
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{col.label}</TableCell>
                  <TableCell className="font-mono text-muted-foreground">
                    {col.type}
                    {col.foreign_key && (
                      <Badge variant="outline" className="ml-2">
                        外键 → {col.foreign_key}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{col.nullable ? "是" : "否"}</TableCell>
                  <TableCell>{col.unique ? "是" : "否"}</TableCell>
                  <TableCell>{col.primary_key ? "是" : "否"}</TableCell>
                  <TableCell className="text-muted-foreground">{col.default ?? "—"}</TableCell>
                  <TableCell className="max-w-56 truncate text-muted-foreground">
                    {col.description ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据预览（前 5 行）</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.sample_rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无数据，可通过“上传数据”页面导入。</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {visibleColumns.map((col) => (
                      <TableHead key={col.name}>{col.label}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.sample_rows.map((row, i) => (
                    <TableRow key={i}>
                      {visibleColumns.map((col) => (
                        <TableCell key={col.name} className="max-w-60 truncate">
                          {row[col.name] === null || row[col.name] === undefined
                            ? ""
                            : String(row[col.name])}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {!detail.read_only && (
        <>
          {editOpen && (
            <EditTableDialog
              tableName={detail.name}
              onClose={() => setEditOpen(false)}
              onRenamed={(newName) => {
                setEditOpen(false);
                if (newName !== detail.name) {
                  navigate(`/schema/tables/${newName}`);
                }
              }}
            />
          )}
          <DeleteTableDialog
            tableName={deleteOpen ? detail.name : null}
            chineseName={detail.chinese_name}
            onClose={() => setDeleteOpen(false)}
            onDeleted={() => navigate("/schema")}
          />
        </>
      )}
    </div>
  );
}
