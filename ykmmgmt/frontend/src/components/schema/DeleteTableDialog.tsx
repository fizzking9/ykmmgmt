import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useDeleteTable, useTableDependencies } from "@/hooks/useSchema";

interface DeleteTableDialogProps {
  /** English table name; null/empty keeps the dialog closed. */
  tableName: string | null;
  chineseName: string;
  onClose: () => void;
  onDeleted?: () => void;
}

/** Type-to-confirm delete dialog that surfaces dependent views/visualizations. */
export function DeleteTableDialog({
  tableName,
  chineseName,
  onClose,
  onDeleted,
}: DeleteTableDialogProps) {
  const [confirmText, setConfirmText] = useState("");
  const deleteMutation = useDeleteTable();

  const depsQuery = useTableDependencies(tableName ?? undefined);
  const deps = depsQuery.data;
  const hasFkDeps = !!deps && deps.tables.length > 0;
  const hasDeps =
    !!deps && (deps.views.length > 0 || deps.visualizations.length > 0 || deps.tables.length > 0);

  useEffect(() => {
    if (!tableName) setConfirmText("");
  }, [tableName]);

  if (!tableName) return null;

  const confirmed = confirmText === tableName;

  const handleDelete = () => {
    deleteMutation.mutate(
      { table: tableName, confirm: true },
      {
        onSuccess: () => {
          onClose();
          onDeleted?.();
        },
      },
    );
  };

  return (
    <Dialog open onClose={onClose} title="删除数据表">
      <div className="space-y-4">
        <p className="text-sm">
          确定要删除数据表 <span className="font-semibold">{chineseName}</span>（
          <span className="font-mono">{tableName}</span>）吗？该操作会生成删除迁移并立即执行，
          表中的所有数据将一并删除。
        </p>

        {depsQuery.isLoading && <p className="text-sm text-muted-foreground">正在检查依赖…</p>}

        {hasDeps && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <p className="mb-2 flex items-center gap-2 font-medium text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {hasFkDeps
                ? "以下数据表通过外键引用了该表，需先删除它们才能删除本表："
                : "以下资产引用了该表，删除后将无法正常工作："}
            </p>
            {deps!.tables.length > 0 && (
              <p>
                数据表（外键）：
                {deps!.tables.map((t) => `${t.table}（${t.column} → ${t.references}）`).join("、")}
              </p>
            )}
            {deps!.views.length > 0 && (
              <p>
                视图：
                {deps!.views.map((v) => v.name).join("、")}
              </p>
            )}
            {deps!.visualizations.length > 0 && (
              <p>
                可视化：
                {deps!.visualizations.map((v) => v.name).join("、")}
              </p>
            )}
          </div>
        )}

        <div>
          <label className="mb-1 block text-sm text-muted-foreground" htmlFor="delete-confirm">
            请输入表名 <span className="font-mono">{tableName}</span> 以确认删除
          </label>
          <input
            id="delete-confirm"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={tableName}
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={!confirmed || hasFkDeps || deleteMutation.isPending}
            onClick={handleDelete}
          >
            {deleteMutation.isPending ? "删除中…" : "确认删除"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
