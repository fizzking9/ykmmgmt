import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { ForeignKeyPicker } from "@/components/schema/ForeignKeyPicker";
import {
  useAddColumn,
  useColumnTypes,
  useDropColumn,
  useModifyColumn,
  useRenameTable,
  useSchemaTableDetail,
  type ModifyColumnPayload,
  type SchemaColumnDetail,
} from "@/hooks/useSchema";

interface EditTableDialogProps {
  /** English table name; null keeps the dialog closed. */
  tableName: string | null;
  onClose: () => void;
  /** Called with the new English name after a successful table rename. */
  onRenamed?: (newName: string) => void;
}

const inputCls = "w-full rounded-md border bg-background px-2 py-1.5 text-sm";

/** Add / drop / modify columns of a dynamic table; rename the table itself. */
export function EditTableDialog({ tableName, onClose, onRenamed }: EditTableDialogProps) {
  if (!tableName) return null;
  return (
    <EditTableDialogContent
      key={tableName}
      tableName={tableName}
      onClose={onClose}
      onRenamed={onRenamed}
    />
  );
}

interface ColumnDraft {
  name: string;
  label: string;
  type: string;
  length: number;
  nullable: boolean;
  unique: boolean;
  description: string;
  default: string;
  foreign_key: string;
}

function draftFromColumn(col: SchemaColumnDetail): ColumnDraft {
  return {
    name: col.name,
    label: col.label,
    type: colTypeKey(col.type),
    length: colLength(col.type) ?? 255,
    nullable: col.nullable,
    unique: col.unique,
    description: col.description ?? "",
    default: col.default ?? "",
    foreign_key: col.foreign_key ?? "",
  };
}

/** Diff a draft against the current column; only changed fields are sent. */
function buildPayload(col: SchemaColumnDetail, d: ColumnDraft): ModifyColumnPayload | null {
  const p: ModifyColumnPayload = {};
  if (d.name.trim() && d.name.trim() !== col.name) p.name = d.name.trim();
  if (d.label !== col.label) p.label = d.label;
  const origType = colTypeKey(col.type);
  if (d.type !== origType) {
    p.type = d.type;
    p.length = d.type === "String" ? d.length : null;
  } else if (d.type === "String" && d.length !== (colLength(col.type) ?? 255)) {
    p.length = d.length;
  }
  if (d.nullable !== col.nullable) p.nullable = d.nullable;
  if (d.unique !== col.unique) p.unique = d.unique;
  if (d.description !== (col.description ?? "")) p.description = d.description;
  if (d.default !== (col.default ?? "")) p.default = d.default;
  if ((d.foreign_key || "") !== (col.foreign_key ?? "")) p.foreign_key = d.foreign_key || "";
  return Object.keys(p).length > 0 ? p : null;
}

function EditTableDialogContent({
  tableName,
  onClose,
  onRenamed,
}: {
  tableName: string;
  onClose: () => void;
  onRenamed?: (newName: string) => void;
}) {
  const detailQuery = useSchemaTableDetail(tableName);
  const typesQuery = useColumnTypes();
  const addMutation = useAddColumn(tableName);
  const dropMutation = useDropColumn(tableName);
  const modifyMutation = useModifyColumn(tableName);
  const renameMutation = useRenameTable(tableName);

  // Table-level rename drafts (English name + Chinese display name)
  const [tableNameDraft, setTableNameDraft] = useState(tableName);
  const [displayNameDraft, setDisplayNameDraft] = useState("");
  // Ingestion settings drafts (upsert key columns + keyless dedup toggle)
  const [upsertKeyDraft, setUpsertKeyDraft] = useState<string[]>([]);
  const [dedupDraft, setDedupDraft] = useState(true);

  // New-column form state
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("String");
  const [newLength, setNewLength] = useState("255");
  const [newLabel, setNewLabel] = useState("");
  const [newNullable, setNewNullable] = useState(true);
  const [newForeignKey, setNewForeignKey] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newDefault, setNewDefault] = useState("");

  // Per-column edit drafts keyed by the current column name
  const [drafts, setDrafts] = useState<Record<string, ColumnDraft>>({});
  // Per-row delete confirmation
  const [confirmingDrop, setConfirmingDrop] = useState<string | null>(null);

  const columns = detailQuery.data?.columns ?? [];
  const businessColumns = columns.filter((c) => !c.internal);
  const typeOptions = typesQuery.data ?? [];

  // Re-seed the drafts whenever the server-side column state changes
  const initKey = columns
    .map(
      (c) =>
        `${c.name}|${c.type}|${c.nullable}|${c.unique}|${c.label}|${c.description ?? ""}|` +
        `${c.default ?? ""}|${c.foreign_key ?? ""}`,
    )
    .join(";");
  useEffect(() => {
    setDrafts(Object.fromEntries(businessColumns.map((c) => [c.name, draftFromColumn(c)])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initKey]);

  // Seed the table-rename drafts from the loaded detail
  const tableKey =
    `${detailQuery.data?.name ?? ""}|${detailQuery.data?.chinese_name ?? ""}|` +
    `${(detailQuery.data?.upsert_key ?? []).join(",")}|${detailQuery.data?.dedup_enabled ?? true}`;
  useEffect(() => {
    if (detailQuery.data) {
      setTableNameDraft(detailQuery.data.name);
      setDisplayNameDraft(detailQuery.data.chinese_name);
      setUpsertKeyDraft(detailQuery.data.upsert_key ?? []);
      setDedupDraft(detailQuery.data.dedup_enabled ?? true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableKey]);

  const updateDraft = (column: string, patch: Partial<ColumnDraft>) => {
    setDrafts((prev) => ({ ...prev, [column]: { ...prev[column], ...patch } }));
  };

  const handleAdd = () => {
    addMutation.mutate(
      {
        name: newName.trim(),
        type: newType,
        length: newType === "String" ? Number(newLength) || 255 : null,
        nullable: newNullable,
        foreign_key: newForeignKey.trim() || null,
        label: newLabel.trim() || newName.trim(),
        description: newDescription.trim() || null,
        default: newDefault.trim() || null,
      },
      {
        onSuccess: () => {
          setNewName("");
          setNewLabel("");
          setNewType("String");
          setNewLength("255");
          setNewNullable(true);
          setNewForeignKey("");
          setNewDescription("");
          setNewDefault("");
        },
      },
    );
  };

  const handleSave = (col: SchemaColumnDetail) => {
    const draft = drafts[col.name];
    if (!draft) return;
    const payload = buildPayload(col, draft);
    if (!payload) return;
    modifyMutation.mutate({ column: col.name, ...payload });
  };

  const handleDrop = (column: string) => {
    if (confirmingDrop !== column) {
      setConfirmingDrop(column);
      return;
    }
    setConfirmingDrop(null);
    dropMutation.mutate(column);
  };

  const currentDisplay = detailQuery.data?.chinese_name ?? tableName;
  const nameChanged = tableNameDraft.trim() && tableNameDraft.trim() !== tableName;
  const displayChanged = displayNameDraft.trim() && displayNameDraft.trim() !== currentDisplay;

  // Ingestion settings change detection
  const currentKey = detailQuery.data?.upsert_key ?? [];
  const currentDedup = detailQuery.data?.dedup_enabled ?? true;
  const keyChanged = upsertKeyDraft.join(",") !== currentKey.join(",");
  const dedupChanged = dedupDraft !== currentDedup;
  const hasPk = businessColumns.some((c) => c.primary_key);
  const hasUnique = businessColumns.some((c) => c.unique && !c.primary_key);
  const dedupLocked = hasPk || hasUnique || upsertKeyDraft.length > 0;

  const renameEnabled =
    Boolean(nameChanged || displayChanged || keyChanged || dedupChanged) &&
    !renameMutation.isPending;

  const toggleUpsertColumn = (colName: string, checked: boolean) => {
    setUpsertKeyDraft((prev) => (checked ? [...prev, colName] : prev.filter((n) => n !== colName)));
  };

  const handleRename = () => {
    const payload: {
      name?: string;
      display_name?: string;
      upsert_key?: string[];
      dedup_enabled?: boolean;
    } = {};
    if (nameChanged) payload.name = tableNameDraft.trim();
    if (displayChanged) payload.display_name = displayNameDraft.trim();
    if (keyChanged) {
      const validNames = businessColumns.map((c) => c.name);
      payload.upsert_key = upsertKeyDraft.filter((n) => validNames.includes(n));
    }
    if (dedupChanged && !dedupLocked) payload.dedup_enabled = dedupDraft;
    if (Object.keys(payload).length === 0) return;
    renameMutation.mutate(payload, {
      onSuccess: (data) => {
        if (nameChanged && data.name !== tableName) {
          onRenamed?.(data.name);
        }
      },
    });
  };

  return (
    <Dialog open onClose={onClose} title={`编辑表结构 — ${tableName}`} className="max-w-3xl">
      <div className="space-y-6">
        {/* Table-level rename */}
        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            表信息
            <InfoTooltip
              ariaLabel="表信息注意事项"
              content="注意：尽量不要更改表名。更改表名可能导致应用到该表的数据清洗步骤缺失。显示名可以随意更改。"
            />
          </h3>
          <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>表名（英文小写）</span>
              <input
                aria-label="修改表名"
                className={inputCls}
                value={tableNameDraft}
                onChange={(e) => setTableNameDraft(e.target.value)}
              />
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>显示名（中文）</span>
              <input
                aria-label="修改显示名"
                className={inputCls}
                value={displayNameDraft}
                onChange={(e) => setDisplayNameDraft(e.target.value)}
              />
            </label>
            <Button onClick={handleRename} disabled={!renameEnabled}>
              {renameMutation.isPending ? "保存中…" : "保存表设置"}
            </Button>
          </div>
          {nameChanged && (
            <p className="mt-1 text-xs text-muted-foreground">
              修改表名将物理重命名数据表；被视图/可视化引用时会被阻止。
            </p>
          )}
          <div className="mt-3 space-y-2">
            <p className="text-xs text-muted-foreground">Upsert Key</p>
            <div className="flex flex-wrap gap-3 text-sm">
              {businessColumns.map((c) => (
                <label key={c.name} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    aria-label={`Upsert键列${c.name}`}
                    checked={upsertKeyDraft.includes(c.name)}
                    onChange={(e) => toggleUpsertColumn(c.name, e.target.checked)}
                  />
                  {c.label || c.name}
                  <span className="font-mono text-xs text-muted-foreground">({c.name})</span>
                </label>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label="启用完全重复去重"
                checked={dedupLocked ? true : dedupDraft}
                disabled={dedupLocked}
                onChange={(e) => setDedupDraft(e.target.checked)}
              />
              去重
            </label>
          </div>
        </section>

        {/* Add a new column */}
        <section>
          <h3 className="mb-2 text-sm font-semibold">添加新列</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <input
              aria-label="新列名"
              className={inputCls}
              placeholder="列名（英文小写）"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <select
              aria-label="新列类型"
              className={inputCls}
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {typeOptions.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
            {newType === "String" ? (
              <input
                aria-label="新列长度"
                className={inputCls}
                placeholder="长度"
                value={newLength}
                onChange={(e) => setNewLength(e.target.value)}
              />
            ) : (
              <span />
            )}
            <input
              aria-label="新列中文标签"
              className={inputCls}
              placeholder="中文标签"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
            />
            <Button onClick={handleAdd} disabled={!newName.trim() || addMutation.isPending}>
              {addMutation.isPending ? "添加中…" : "添加列"}
            </Button>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input
              aria-label="新列描述"
              className={inputCls}
              placeholder="列描述（可选）"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            <input
              aria-label="新列默认值"
              className={inputCls}
              placeholder="默认值（可选，不填为 null）"
              value={newDefault}
              onChange={(e) => setNewDefault(e.target.value)}
            />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label="新列允许为空"
                checked={newNullable}
                onChange={(e) => setNewNullable(e.target.checked)}
              />
              允许为空
            </label>
            <ForeignKeyPicker
              ariaPrefix="新列"
              value={newForeignKey}
              onChange={(v) => setNewForeignKey(v)}
            />
          </div>
        </section>

        {/* Existing columns */}
        <section>
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            现有列
            <InfoTooltip
              ariaLabel="修改列注意事项"
              content="注意：中文标签被用来与文件的列名匹配，更改可导致数据上传失败。"
            />
          </h3>
          {detailQuery.isLoading && (
            <p className="text-sm text-muted-foreground">正在加载表结构…</p>
          )}
          <ul className="space-y-3">
            {businessColumns.map((col) => {
              const draft = drafts[col.name] ?? draftFromColumn(col);
              const payload = buildPayload(col, draft);
              return (
                <li key={col.name} className="space-y-2 rounded-md border p-2 text-sm">
                  <div className="grid grid-cols-2 items-center gap-2 sm:grid-cols-[1fr_1fr_10rem_6rem_auto_auto]">
                    <input
                      aria-label={`修改列 ${col.name} 的列名`}
                      className={inputCls}
                      value={draft.name}
                      onChange={(e) => updateDraft(col.name, { name: e.target.value })}
                    />
                    <input
                      aria-label={`修改列 ${col.name} 的中文标签`}
                      className={inputCls}
                      placeholder="中文标签"
                      value={draft.label}
                      onChange={(e) => updateDraft(col.name, { label: e.target.value })}
                    />
                    <select
                      aria-label={`修改列 ${col.name} 的类型`}
                      className={inputCls}
                      disabled={col.primary_key}
                      value={draft.type}
                      onChange={(e) => updateDraft(col.name, { type: e.target.value })}
                    >
                      {typeOptions.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                    {draft.type === "String" ? (
                      <input
                        aria-label={`修改列 ${col.name} 的长度`}
                        className={inputCls}
                        placeholder="长度"
                        value={draft.length}
                        onChange={(e) =>
                          updateDraft(col.name, { length: Number(e.target.value) || 255 })
                        }
                      />
                    ) : (
                      <span />
                    )}
                    <Button
                      size="sm"
                      disabled={!payload || modifyMutation.isPending}
                      onClick={() => handleSave(col)}
                    >
                      保存修改
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={dropMutation.isPending}
                      onClick={() => handleDrop(col.name)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {confirmingDrop === col.name ? "确认删除" : "删除"}
                    </Button>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                    <label className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        aria-label={`修改列 ${col.name} 允许为空`}
                        checked={col.primary_key ? false : draft.nullable}
                        disabled={col.primary_key}
                        onChange={(e) => updateDraft(col.name, { nullable: e.target.checked })}
                      />
                      可空
                    </label>
                    <label className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        aria-label={`修改列 ${col.name} 唯一`}
                        checked={col.primary_key ? true : draft.unique}
                        disabled={col.primary_key}
                        onChange={(e) => updateDraft(col.name, { unique: e.target.checked })}
                      />
                      唯一
                    </label>
                    {col.primary_key && <span>（主键：不可空且隐式唯一）</span>}
                    <ForeignKeyPicker
                      ariaPrefix={`列 ${col.name} 的`}
                      value={draft.foreign_key}
                      onChange={(v) => updateDraft(col.name, { foreign_key: v })}
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input
                      aria-label={`修改列 ${col.name} 的描述`}
                      className={inputCls}
                      placeholder="列描述（可选）"
                      value={draft.description}
                      onChange={(e) => updateDraft(col.name, { description: e.target.value })}
                    />
                    <input
                      aria-label={`修改列 ${col.name} 的默认值`}
                      className={inputCls}
                      placeholder="默认值（留空清除）"
                      value={draft.default}
                      onChange={(e) => updateDraft(col.name, { default: e.target.value })}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

/** Map a raw SQL type string (e.g. VARCHAR(200)) back to a picker key. */
function colTypeKey(sqlType: string): string {
  const t = sqlType.toUpperCase();
  if (t.startsWith("VARCHAR") || t.startsWith("CHARACTER VARYING")) return "String";
  if (t === "TEXT") return "Text";
  if (t === "BIGINT") return "BigInteger";
  if (t === "INTEGER") return "Integer";
  if (t.startsWith("NUMERIC") || t.startsWith("DECIMAL")) return "Numeric";
  if (t === "BOOLEAN") return "Boolean";
  if (t === "DATE") return "Date";
  if (t.startsWith("TIMESTAMP")) return "DateTime";
  if (t === "JSON" || t === "JSONB") return "JSON";
  return "Text";
}

/** Extract the length from a SQL type like VARCHAR(200). */
function colLength(sqlType: string): number | null {
  const m = sqlType.match(/\((\d+)\)/);
  return m ? Number(m[1]) : null;
}
