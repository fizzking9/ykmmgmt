import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, FileUp, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  useColumnTypes,
  useCreateTable,
  useInferCsv,
  type ColumnDefinitionPayload,
} from "@/hooks/useSchema";
import { ForeignKeyPicker } from "@/components/schema/ForeignKeyPicker";
import { useUploadFile } from "@/hooks/useUploadFile";

const NAME_RE = /^[a-z][a-z0-9_]*$/;

const inputCls = "w-full rounded-md border bg-background px-2 py-1.5 text-sm";

function emptyColumn(): ColumnDefinitionPayload {
  return {
    name: "",
    type: "String",
    length: 255,
    nullable: true,
    unique: false,
    primary_key: false,
    foreign_key: "",
    label: "",
    description: "",
    default: "",
  };
}

export default function SchemaCreateTablePage() {
  const navigate = useNavigate();
  const typesQuery = useColumnTypes();
  const inferMutation = useInferCsv();
  const createMutation = useCreateTable();
  const uploadMutation = useUploadFile();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [mode, setMode] = useState<"manual" | "csv">("manual");
  // Source file kept after successful inference so its data can be imported
  // into the new table right after creation.
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [importAfterCreate, setImportAfterCreate] = useState(true);
  const [tableName, setTableName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [columns, setColumns] = useState<ColumnDefinitionPayload[]>([emptyColumn()]);
  // Ingestion settings: upsert key column names + keyless dedup toggle
  const [upsertKey, setUpsertKey] = useState<string[]>([]);
  const [dedupEnabled, setDedupEnabled] = useState(true);

  const typeOptions = typesQuery.data ?? [];

  const updateColumn = (index: number, patch: Partial<ColumnDefinitionPayload>) => {
    setColumns((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  };

  // Only one column can be the primary key — checking one unchecks the rest.
  // A PK is inherently NOT NULL and unique, so those flags are locked too.
  const togglePrimaryKey = (index: number, checked: boolean) => {
    setColumns((prev) =>
      prev.map((c, i) =>
        i === index
          ? {
              ...c,
              primary_key: checked,
              nullable: checked ? false : c.nullable,
              unique: checked ? false : c.unique,
            }
          : { ...c, primary_key: false },
      ),
    );
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    inferMutation.mutate(file, {
      onSuccess: (data) => {
        // Merge over an empty column so every editable field is present;
        // the Chinese labels come straight from the file headers.
        setColumns(data.columns.map((c) => ({ ...emptyColumn(), ...c })));
        setUpsertKey([]); // inferred columns replaced — reset the key choice
        setSourceFile(file);
        if (!tableName) setTableName(data.suggested_table_name);
      },
    });
  };

  const namedColumns = columns.filter((c) => c.name.trim());
  const hasPk = columns.some((c) => c.primary_key);
  const hasUnique = columns.some((c) => c.unique && !c.primary_key);
  const keySelected = upsertKey.length > 0;
  // The dedup toggle only makes sense for keyless tables
  const dedupLocked = hasPk || hasUnique || keySelected;

  const toggleUpsertColumn = (name: string, checked: boolean) => {
    setUpsertKey((prev) => (checked ? [...prev, name] : prev.filter((n) => n !== name)));
  };

  const nameValid = NAME_RE.test(tableName);
  const columnsValid =
    columns.length > 0 && columns.every((c) => NAME_RE.test(c.name.trim()) && c.type);
  const canSubmit =
    nameValid && columnsValid && !createMutation.isPending && !uploadMutation.isPending;

  const handleSubmit = () => {
    // Drop key selections that no longer reference a defined column
    const validKey = upsertKey.filter((n) => namedColumns.some((c) => c.name.trim() === n));
    createMutation.mutate(
      {
        name: tableName.trim(),
        display_name: displayName.trim() || null,
        columns: columns.map((c) => ({
          name: c.name.trim(),
          type: c.type,
          length: c.type === "String" ? (c.length ?? 255) : null,
          nullable: c.nullable ?? true,
          unique: c.unique ?? false,
          primary_key: c.primary_key ?? false,
          foreign_key: c.foreign_key?.trim() || null,
          label: c.label?.trim() || c.name.trim(),
          description: c.description?.trim() || null,
          default: c.default?.trim() || null,
        })),
        upsert_key: validKey.length > 0 ? validKey : null,
        dedup_enabled: dedupLocked ? true : dedupEnabled,
      },
      {
        onSuccess: (data) => {
          // Optionally feed the inferred source file into the fresh table
          if (importAfterCreate && sourceFile) {
            uploadMutation.mutate(
              { file: sourceFile, targetTable: data.name },
              {
                onSuccess: (result) => {
                  toast.success(
                    `数据导入完成：新增 ${result.rows_inserted} 行，更新 ${result.rows_updated} 行，跳过 ${result.rows_skipped} 行`,
                  );
                  navigate(`/schema/tables/${data.name}`);
                },
                onError: (err: Error) => {
                  toast.error(`数据表已创建，但数据导入失败：${err.message}`);
                  navigate(`/schema/tables/${data.name}`);
                },
              },
            );
          } else {
            navigate(`/schema/tables/${data.name}`);
          }
        },
      },
    );
  };

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/schema")}>
          <ArrowLeft className="h-4 w-4" />
          返回
        </Button>
        <h1 className="text-xl font-semibold">新建数据表</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground" htmlFor="table-name">
              英文表名（小写字母、数字、下划线）
            </label>
            <input
              id="table-name"
              className={inputCls}
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="例如：customer_orders"
            />
            {tableName && !nameValid && (
              <p className="mt-1 text-xs text-destructive">
                表名需以小写字母开头，仅包含小写字母、数字和下划线
              </p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground" htmlFor="display-name">
              中文显示名（可选）
            </label>
            <input
              id="display-name"
              className={inputCls}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="例如：客户订单"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>列定义</CardTitle>
          <div className="flex gap-1 rounded-lg border p-1">
            <button
              type="button"
              className={cn(
                "rounded-md px-3 py-1 text-sm",
                mode === "manual" ? "bg-muted font-medium" : "text-muted-foreground",
              )}
              onClick={() => setMode("manual")}
            >
              手动创建
            </button>
            <button
              type="button"
              className={cn(
                "rounded-md px-3 py-1 text-sm",
                mode === "csv" ? "bg-muted font-medium" : "text-muted-foreground",
              )}
              onClick={() => setMode("csv")}
            >
              CSV 导入
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {mode === "csv" && (
            <div className="rounded-md border border-dashed p-4 text-sm">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                aria-label="选择CSV文件"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0])}
              />
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={inferMutation.isPending}
                >
                  <FileUp className="h-4 w-4" />
                  {inferMutation.isPending ? "推断中…" : "选择 CSV / Excel 文件"}
                </Button>
                <span className="text-muted-foreground">
                  上传后自动推断列类型与中文标签，可调整后再创建
                </span>
              </div>
              {inferMutation.data && (
                <p className="mt-2 text-muted-foreground">
                  已推断 {inferMutation.data.columns.length} 列（源文件约{" "}
                  {inferMutation.data.row_count} 行数据）
                </p>
              )}
              {sourceFile && (
                <label className="mt-2 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    aria-label="创建后导入数据"
                    checked={importAfterCreate}
                    onChange={(e) => setImportAfterCreate(e.target.checked)}
                  />
                  创建后导入该文件数据到此表（{sourceFile.name}）
                </label>
              )}
            </div>
          )}

          {columns.length === 0 && (
            <p className="text-sm text-muted-foreground">尚未定义任何列，请先添加。</p>
          )}

          <ul className="space-y-2">
            {columns.map((col, i) => (
              <li key={i} className="space-y-2 rounded-md border p-2">
                <div className="grid grid-cols-2 items-center gap-2 sm:grid-cols-[1fr_10rem_6rem_1fr_auto]">
                  <input
                    aria-label={`第${i + 1}列列名`}
                    className={inputCls}
                    placeholder="列名（英文小写）"
                    value={col.name}
                    onChange={(e) => updateColumn(i, { name: e.target.value })}
                  />
                  <select
                    aria-label={`第${i + 1}列类型`}
                    className={inputCls}
                    value={col.type}
                    onChange={(e) => updateColumn(i, { type: e.target.value })}
                  >
                    {typeOptions.map((t) => (
                      <option key={t.key} value={t.key}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  {col.type === "String" ? (
                    <input
                      aria-label={`第${i + 1}列长度`}
                      className={inputCls}
                      placeholder="长度"
                      value={col.length ?? ""}
                      onChange={(e) => updateColumn(i, { length: Number(e.target.value) || 255 })}
                    />
                  ) : (
                    <span />
                  )}
                  <input
                    aria-label={`第${i + 1}列中文标签`}
                    className={inputCls}
                    placeholder="中文标签"
                    value={col.label ?? ""}
                    onChange={(e) => updateColumn(i, { label: e.target.value })}
                  />
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={`删除第${i + 1}列`}
                    onClick={() => setColumns((prev) => prev.filter((_c, idx) => idx !== i))}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      aria-label={`第${i + 1}列允许为空`}
                      checked={col.primary_key ? false : (col.nullable ?? true)}
                      disabled={!!col.primary_key}
                      onChange={(e) => updateColumn(i, { nullable: e.target.checked })}
                    />
                    可空
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      aria-label={`第${i + 1}列唯一`}
                      checked={col.primary_key ? true : (col.unique ?? false)}
                      disabled={!!col.primary_key}
                      onChange={(e) => updateColumn(i, { unique: e.target.checked })}
                    />
                    唯一
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      aria-label={`第${i + 1}列设为主键`}
                      checked={col.primary_key ?? false}
                      onChange={(e) => togglePrimaryKey(i, e.target.checked)}
                    />
                    主键
                  </label>
                  <ForeignKeyPicker
                    ariaPrefix={`第${i + 1}列`}
                    value={col.foreign_key ?? ""}
                    onChange={(v) => updateColumn(i, { foreign_key: v })}
                  />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input
                    aria-label={`第${i + 1}列描述`}
                    className={inputCls}
                    placeholder="列描述（可选）"
                    value={col.description ?? ""}
                    onChange={(e) => updateColumn(i, { description: e.target.value })}
                  />
                  <input
                    aria-label={`第${i + 1}列默认值`}
                    className={inputCls}
                    placeholder="默认值（可选，不填为 null）"
                    value={col.default ?? ""}
                    onChange={(e) => updateColumn(i, { default: e.target.value })}
                  />
                </div>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              onClick={() => setColumns((prev) => [...prev, emptyColumn()])}
            >
              <Plus className="h-4 w-4" />
              添加列
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {createMutation.isPending || uploadMutation.isPending
                ? uploadMutation.isPending
                  ? "导入数据中…"
                  : "创建中…"
                : "创建数据表"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据导入设置</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="mb-1 text-sm text-muted-foreground">Upsert Key</p>
            {namedColumns.length === 0 ? (
              <p className="text-xs text-muted-foreground">请先在列定义中填写列名</p>
            ) : (
              <div className="flex flex-wrap gap-3 text-sm">
                {namedColumns.map((c) => {
                  const colName = c.name.trim();
                  return (
                    <label key={colName} className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        aria-label={`Upsert键列${colName}`}
                        checked={upsertKey.includes(colName)}
                        onChange={(e) => toggleUpsertColumn(colName, e.target.checked)}
                      />
                      {c.label?.trim() || colName}
                      <span className="font-mono text-xs text-muted-foreground">({colName})</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label="启用完全重复去重"
                checked={dedupLocked ? true : dedupEnabled}
                disabled={dedupLocked}
                onChange={(e) => setDedupEnabled(e.target.checked)}
              />
              去重
            </label>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
