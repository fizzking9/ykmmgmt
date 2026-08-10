import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useTables, TableOption } from "@/hooks/useTables";
import {
  useViews,
  useView,
  useCreateView,
  useUpdateView,
  usePreviewView,
  type ViewConfig,
  type JoinSpec,
  type ColumnInfo,
} from "@/hooks/useViews";
import { useViewBuilderContext } from "@/contexts/ViewBuilderContext";
import type { ComputedColumnItem, ColumnAlias } from "@/contexts/ViewBuilderContext";
import {
  Plus,
  X,
  Eye,
  Save,
  Database,
  Loader2,
  ArrowRightLeft,
  Columns3,
  Filter,
  BarChart3,
  Search,
  Calculator,
  Pencil,
  CheckCheck,
  RotateCcw,
} from "lucide-react";

// ── API helpers ────────────────────────────────────────────────────────────

async function fetchTableSchema(tableName: string): Promise<ColumnInfo[]> {
  const res = await fetch(`/api/tables/${tableName}/schema`);
  if (!res.ok) throw new Error("获取表结构失败");
  return res.json();
}

// ── Constants ──────────────────────────────────────────────────────────────

const TEXT_OPERATORS: { value: string; label: string }[] = [
  { value: "eq", label: "等于" },
  { value: "neq", label: "不等于" },
  { value: "contains", label: "包含" },
  { value: "startswith", label: "开头是" },
  { value: "endswith", label: "结尾是" },
  { value: "is_null", label: "为空" },
  { value: "is_not_null", label: "不为空" },
];

const NUMERIC_OPERATORS: { value: string; label: string }[] = [
  { value: "eq", label: "等于" },
  { value: "neq", label: "不等于" },
  { value: "gt", label: "大于" },
  { value: "gte", label: "大于等于" },
  { value: "lt", label: "小于" },
  { value: "lte", label: "小于等于" },
  { value: "is_null", label: "为空" },
  { value: "is_not_null", label: "不为空" },
];

const AGG_FUNCTIONS: { value: string; label: string }[] = [
  { value: "SUM", label: "求和" },
  { value: "COUNT", label: "计数" },
  { value: "AVG", label: "平均值" },
  { value: "MIN", label: "最小值" },
  { value: "MAX", label: "最大值" },
];

const JOIN_TYPES: { value: string; label: string }[] = [
  { value: "INNER", label: "INNER JOIN" },
  { value: "LEFT", label: "LEFT JOIN" },
  { value: "RIGHT", label: "RIGHT JOIN" },
];

type ColumnType = "text" | "number" | "date";

function classifyColumnType(col: ColumnInfo): ColumnType {
  const t = col.type.toLowerCase();
  if (t.includes("int") || t.includes("float") || t.includes("numeric") || t.includes("decimal"))
    return "number";
  if (t.includes("datetime") || t.includes("date")) return "date";
  return "text";
}

function getOperators(colType: ColumnType) {
  if (colType === "number") return NUMERIC_OPERATORS;
  if (colType === "date") return []; // Date columns use date range picker instead
  return TEXT_OPERATORS;
}

// ── Self-join alias helpers ────────────────────────────────────────────────

function baseTableName(name: string): string {
  return name.replace(/_\d+$/, "");
}

function tableDisplayName(logicalName: string, tables: TableOption[] | undefined): string {
  const base = baseTableName(logicalName);
  const chineseName = tables?.find((t) => t.name === base)?.chinese_name || base;
  if (logicalName === base) return chineseName;
  const suffix = logicalName.slice(base.length); // e.g. "_1"
  return chineseName + suffix;
}

// ── Searchable Column Combobox ─────────────────────────────────────────────

interface ColumnOption {
  key: string; // "table.column"
  label: string; // "表名.列名" in Chinese
}

function ColumnCombobox({
  value,
  options,
  onChange,
  placeholder = "搜索列...",
}: {
  value: string;
  options: ColumnOption[];
  onChange: (key: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const filtered = search
    ? options.filter((o) => o.label.toLowerCase().includes(search.toLowerCase()))
    : options;

  const selectedOption = options.find((o) => o.key === value);

  return (
    <div ref={containerRef} className="relative">
      <div
        className="flex h-9 w-full cursor-pointer items-center rounded-md border border-input bg-transparent px-2 text-sm shadow-sm"
        title={selectedOption?.label}
        onClick={() => {
          setOpen(!open);
          setSearch("");
          setTimeout(() => inputRef.current?.focus(), 0);
        }}
      >
        {selectedOption ? (
          <span className="truncate">{selectedOption.label}</span>
        ) : (
          <span className="text-muted-foreground">{placeholder}</span>
        )}
      </div>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 max-h-48 min-w-full w-auto max-w-[80vw] overflow-x-auto rounded-md border bg-background shadow-md">
          <div className="flex items-center border-b px-2">
            <Search className="mr-1 h-3 w-3 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索..."
              className="flex-1 bg-transparent py-1.5 text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div className="max-h-36 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-2 py-3 text-center text-xs text-muted-foreground">无匹配结果</p>
            ) : (
              filtered.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  className="whitespace-nowrap px-2 py-1.5 text-left text-sm hover:bg-accent"
                  onClick={() => {
                    onChange(opt.key);
                    setOpen(false);
                    setSearch("");
                  }}
                >
                  {opt.label}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function ViewBuilderPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const { data: viewsList } = useViews();
  const { data: existingView, isLoading: viewLoading } = useView(id);
  const { data: tables, isLoading: tablesLoading } = useTables();
  const createView = useCreateView();
  const updateView = useUpdateView();
  const previewMutation = usePreviewView();

  const viewBuilder = useViewBuilderContext();
  const { state } = viewBuilder;

  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    targetId: string;
    targetName: string;
  } | null>(null);

  // Guard ref to prevent re-loading the same view on every render
  const loadedViewIdRef = useRef<string | null>(null);

  // ── Load existing view in edit mode ────────────────────────────────────
  useEffect(() => {
    if (existingView && loadedViewIdRef.current !== existingView.id) {
      loadedViewIdRef.current = existingView.id;
      viewBuilder.setEditingId(existingView.id);
      viewBuilder.setName(existingView.name);
      viewBuilder.setDescription(existingView.description || "");
      viewBuilder.setFromTables(existingView.config_json.from_tables);
      viewBuilder.setJoins(existingView.config_json.joins);
      viewBuilder.setColumns(
        existingView.config_json.columns.map((c) => ({
          table: c.table,
          column: c.column,
          alias: c.alias || "",
        })),
      );
      viewBuilder.setFilters(
        existingView.config_json.filters.map((f) => ({
          column: f.column,
          operator: f.operator || "eq",
          value: f.value != null ? String(f.value) : "",
          dateStart: f.date_start || "",
          dateEnd: f.date_end || "",
        })),
      );
      viewBuilder.setGroupBy(existingView.config_json.group_by);
      viewBuilder.setAggregations(
        existingView.config_json.aggregations.map((a) => ({
          function: a.function,
          column: a.column,
          alias: a.alias || "",
        })),
      );
      viewBuilder.setComputedColumns(
        (existingView.config_json.computed_columns || []).map((cc) => ({
          alias: cc.alias,
          expression_type: cc.expression_type,
          operands: (cc.operands || []).map((op) => ({
            type: op.type,
            table: op.table || "",
            column: op.column || "",
            value: op.value || "",
          })),
          operators: cc.operators || [],
          base_table: cc.base_column?.table || "",
          base_column: cc.base_column?.column || "",
          shift_value: cc.shift_value || "",
          shift_unit: cc.shift_unit || "days",
          trunc_table: cc.trunc_column?.table || "",
          trunc_column: cc.trunc_column?.column || "",
          trunc_unit: cc.trunc_unit || "day",
        })),
      );
      viewBuilder.setSelectedComputedColumns(
        existingView.config_json.selected_computed_columns || [],
      );
      viewBuilder.setOrderBy(
        (existingView.config_json.order_by || []).map((o) => ({
          column: o.column,
          direction: o.direction || "asc",
        })),
      );
      viewBuilder.setLimit(existingView.config_json.limit ?? null);
    }
  }, [existingView, viewBuilder]);

  // ── Schema queries for all selected tables ─────────────────────────────
  const primaryTable = state.fromTables[0];
  const allTableNames = [...state.fromTables, ...state.joins.map((j) => j.right_table)].filter(
    Boolean,
  );

  const schemaQueries = useQueries({
    queries: allTableNames.map((tn) => ({
      queryKey: ["tableSchema", tn],
      queryFn: () => fetchTableSchema(tn),
      enabled: !!tn,
      staleTime: 60_000,
    })),
  });

  // Build a map of table → columns info
  const schemaMap: Record<string, ColumnInfo[]> = {};
  let allSchemasLoaded = true;
  for (let i = 0; i < allTableNames.length; i++) {
    const q = schemaQueries[i];
    if (q.data) {
      schemaMap[allTableNames[i]] = q.data;
    } else if (q.isLoading) {
      allSchemasLoaded = false;
    }
  }

  // Expand schemaMap with aliases for self-joined tables
  for (const join of state.joins) {
    if (join.right_alias && schemaMap[join.right_table]) {
      schemaMap[join.right_alias] = schemaMap[join.right_table];
    }
  }

  // Build a flat list of all columns across all tables
  const visibleAllColumns: { table: string; col: ColumnInfo }[] = [];
  for (const [tableName, cols] of Object.entries(schemaMap)) {
    for (const col of cols) {
      visibleAllColumns.push({ table: tableName, col });
    }
  }

  // Build column options for comboboxes
  const columnOptions: ColumnOption[] = visibleAllColumns.map(({ table: t, col }) => {
    const tableLabel = tableDisplayName(t, tables);
    return {
      key: `${t}.${col.name}`,
      label: `${tableLabel}.${col.label}`,
    };
  });

  // Add computed column aliases as selectable options
  for (const cc of state.computedColumns) {
    if (cc.alias) {
      columnOptions.push({
        key: cc.alias,
        label: `计算: ${cc.alias}`,
      });
    }
  }

  // Filtered column options for computed column type filtering
  const numericColumnOptions: ColumnOption[] = visibleAllColumns
    .filter(({ col }) => classifyColumnType(col) === "number")
    .map(({ table: t, col }) => ({
      key: `${t}.${col.name}`,
      label: `${tableDisplayName(t, tables)}.${col.label}`,
    }));

  const dateColumnOptions: ColumnOption[] = visibleAllColumns
    .filter(({ col }) => classifyColumnType(col) === "date")
    .map(({ table: t, col }) => ({
      key: `${t}.${col.name}`,
      label: `${tableDisplayName(t, tables)}.${col.label}`,
    }));

  // ── Compile config ─────────────────────────────────────────────────────
  const compileConfig = useCallback((): ViewConfig => {
    return {
      from_tables: state.fromTables.length > 0 ? state.fromTables : [],
      joins: state.joins.map((j) => ({
        left_table: j.left_table,
        right_table: j.right_table,
        right_alias: j.right_alias || null,
        join_type: j.join_type,
        left_key: j.left_key,
        right_key: j.right_key,
      })),
      columns: state.columns
        .filter((c) => c.column)
        .map((c) => {
          // Use explicit alias if set, otherwise generate Chinese table.column label
          const defaultAlias = (() => {
            const tbl = tableDisplayName(c.table, tables);
            const colInfo = schemaMap[c.table]?.find((sc) => sc.name === c.column);
            const col = colInfo?.label || c.column;
            return `${tbl}.${col}`;
          })();
          return {
            table: c.table,
            column: c.column,
            alias: c.alias || defaultAlias,
          };
        }),
      filters: state.filters
        .filter((f) => f.column)
        .map((f) => ({
          column: f.column,
          operator: f.operator || "eq",
          value: ["is_null", "is_not_null"].includes(f.operator) ? null : f.value || null,
          date_start: f.dateStart || null,
          date_end: f.dateEnd || null,
        })),
      group_by: state.groupBy,
      aggregations: state.aggregations
        .filter((a) => a.function && a.column)
        .map((a) => ({
          function: a.function,
          column: a.column,
          alias: a.alias || null,
        })),
      computed_columns: state.computedColumns
        .filter((cc) => cc.alias)
        .map((cc) => {
          if (cc.expression_type === "arithmetic") {
            return {
              alias: cc.alias,
              expression_type: "arithmetic" as const,
              operands: cc.operands.map((op) => ({
                type: op.type,
                table: op.type === "column" ? op.table || null : null,
                column: op.type === "column" ? op.column || null : null,
                value: op.type === "constant" ? op.value || null : null,
              })),
              operators: cc.operators,
            };
          }
          if (cc.expression_type === "datetime_trunc") {
            return {
              alias: cc.alias,
              expression_type: "datetime_trunc" as const,
              trunc_column: {
                type: "column" as const,
                table: cc.trunc_table || null,
                column: cc.trunc_column || null,
                value: null,
              },
              trunc_unit: cc.trunc_unit as
                "year" | "quarter" | "month" | "week" | "day" | "hour" | "minute",
            };
          }
          return {
            alias: cc.alias,
            expression_type: "datetime_shift" as const,
            base_column: {
              type: "column" as const,
              table: cc.base_table || null,
              column: cc.base_column || null,
              value: null,
            },
            shift_value: cc.shift_value || null,
            shift_unit: cc.shift_unit as "days" | "months" | "years",
          };
        }),
      selected_computed_columns: state.selectedComputedColumns,
      order_by: state.orderBy
        .filter((o) => o.column)
        .map((o) => ({
          column: o.column,
          direction: o.direction,
        })),
      limit: state.limit,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    state.fromTables,
    state.joins,
    state.columns,
    state.filters,
    state.groupBy,
    state.aggregations,
    state.computedColumns,
    state.selectedComputedColumns,
    state.orderBy,
    state.limit,
  ]);

  // ── Handlers ───────────────────────────────────────────────────────────

  // ── Helpers ───────────────────────────────────────────────────────────
  function getColumnDisplayAlias(table: string, colName: string): string {
    const tbl = tableDisplayName(table, tables);
    const colInfo = schemaMap[table]?.find((sc) => sc.name === colName);
    const col = colInfo?.label || colName;
    return `${tbl}.${col}`;
  }

  function handleSelectPrimaryTable(tableName: string | null) {
    if (!tableName) return;
    if (state.fromTables.length === 0) {
      viewBuilder.setFromTables([tableName]);
    } else {
      viewBuilder.setFromTables([tableName, ...state.fromTables.slice(1)]);
    }
  }

  function handleAddJoin() {
    viewBuilder.setJoins([
      ...state.joins,
      {
        left_table: primaryTable || "",
        right_table: "",
        join_type: "INNER",
        left_key: "",
        right_key: "",
      },
    ]);
  }

  function handleUpdateJoin(index: number, update: Partial<JoinSpec>) {
    const updated = [...state.joins];
    updated[index] = { ...updated[index], ...update };
    viewBuilder.setJoins(updated);
  }

  function handleRemoveJoin(index: number) {
    viewBuilder.setJoins(state.joins.filter((_, i) => i !== index));
  }

  function handleToggleColumn(table: string, colName: string) {
    const exists = state.columns.find((c) => c.table === table && c.column === colName);
    if (exists) {
      viewBuilder.setColumns(
        state.columns.filter((c) => !(c.table === table && c.column === colName)),
      );
    } else {
      viewBuilder.setColumns([
        ...state.columns,
        { table, column: colName, alias: getColumnDisplayAlias(table, colName) },
      ]);
    }
  }

  function handleColumnAlias(table: string, colName: string, alias: string) {
    viewBuilder.setColumns(
      state.columns.map((c) => (c.table === table && c.column === colName ? { ...c, alias } : c)),
    );
  }

  function handleSelectAllColumns() {
    const allColumns: ColumnAlias[] = visibleAllColumns.map(({ table: t, col }) => ({
      table: t,
      column: col.name,
      alias: getColumnDisplayAlias(t, col.name),
    }));
    viewBuilder.setColumns(allColumns);
    viewBuilder.setSelectedComputedColumns(
      state.computedColumns.filter((cc) => cc.alias).map((cc) => cc.alias),
    );
  }

  function handleClearAllColumns() {
    viewBuilder.setColumns([]);
    viewBuilder.setSelectedComputedColumns([]);
  }

  function handleInvertColumnSelection() {
    const currentSet = new Set(state.columns.map((c) => `${c.table}.${c.column}`));
    const inverted: ColumnAlias[] = visibleAllColumns
      .filter(({ table: t, col }) => !currentSet.has(`${t}.${col.name}`))
      .map(({ table: t, col }) => ({
        table: t,
        column: col.name,
        alias: getColumnDisplayAlias(t, col.name),
      }));
    viewBuilder.setColumns(inverted);
    // Invert computed column selections
    const selectedSet = new Set(state.selectedComputedColumns);
    const invertedCC = state.computedColumns
      .filter((cc) => cc.alias && !selectedSet.has(cc.alias))
      .map((cc) => cc.alias);
    viewBuilder.setSelectedComputedColumns(invertedCC);
  }

  function handleAddFilter() {
    viewBuilder.setFilters([
      ...state.filters,
      { column: "", operator: "eq", value: "", dateStart: "", dateEnd: "" },
    ]);
  }

  function handleUpdateFilter(
    index: number,
    update: Partial<{
      column: string;
      operator: string;
      value: string;
      dateStart: string;
      dateEnd: string;
    }>,
  ) {
    const updated = [...state.filters];
    updated[index] = { ...updated[index], ...update };
    viewBuilder.setFilters(updated);
  }

  function handleRemoveFilter(index: number) {
    viewBuilder.setFilters(state.filters.filter((_, i) => i !== index));
  }

  function handleAddAggregation() {
    viewBuilder.setAggregations([
      ...state.aggregations,
      { function: "SUM", column: "", alias: "" },
    ]);
  }

  function handleUpdateAggregation(
    index: number,
    update: Partial<{ function: string; column: string; alias: string }>,
  ) {
    const updated = [...state.aggregations];
    updated[index] = { ...updated[index], ...update };
    viewBuilder.setAggregations(updated);
  }

  function handleRemoveAggregation(index: number) {
    viewBuilder.setAggregations(state.aggregations.filter((_, i) => i !== index));
  }

  // ── Computed column draft (local) ──────────────────────────────────────
  const [draftCC, setDraftCC] = useState<ComputedColumnItem | null>(null);
  const [editingCCIndex, setEditingCCIndex] = useState<number | null>(null);

  function handleStartAddCC() {
    setDraftCC({
      alias: "",
      expression_type: "arithmetic",
      operands: [
        { type: "column", table: "", column: "", value: "" },
        { type: "column", table: "", column: "", value: "" },
      ],
      operators: ["+"],
      base_table: "",
      base_column: "",
      shift_value: "",
      shift_unit: "days",
      trunc_table: "",
      trunc_column: "",
      trunc_unit: "day",
    });
    setEditingCCIndex(null);
  }

  function handleStartEditCC(index: number) {
    setDraftCC({ ...state.computedColumns[index] });
    setEditingCCIndex(index);
  }

  function handleUpdateDraftCC(update: Partial<ComputedColumnItem>) {
    setDraftCC((prev) => (prev ? { ...prev, ...update } : null));
  }

  function handleConfirmCC() {
    if (!draftCC || !draftCC.alias.trim()) return;
    const confirmed = { ...draftCC, alias: draftCC.alias.trim() };
    if (editingCCIndex != null) {
      const updated = [...state.computedColumns];
      const oldAlias = updated[editingCCIndex]?.alias;
      updated[editingCCIndex] = confirmed;
      viewBuilder.setComputedColumns(updated);
      // If alias changed, update references in filters/groupBy/aggregations
      if (oldAlias && oldAlias !== confirmed.alias) {
        viewBuilder.setFilters(
          state.filters.map((f) => (f.column === oldAlias ? { ...f, column: confirmed.alias } : f)),
        );
        viewBuilder.setGroupBy(state.groupBy.map((g) => (g === oldAlias ? confirmed.alias : g)));
        viewBuilder.setAggregations(
          state.aggregations.map((a) =>
            a.column === oldAlias ? { ...a, column: confirmed.alias } : a,
          ),
        );
      }
    } else {
      viewBuilder.setComputedColumns([...state.computedColumns, confirmed]);
    }
    setDraftCC(null);
    setEditingCCIndex(null);
  }

  function handleCancelCC() {
    setDraftCC(null);
    setEditingCCIndex(null);
  }

  function handleRemoveComputedColumn(index: number) {
    const removed = state.computedColumns[index];
    viewBuilder.setComputedColumns(state.computedColumns.filter((_, i) => i !== index));
    // Clean up references to the removed computed column
    if (removed?.alias) {
      viewBuilder.setFilters(state.filters.filter((f) => f.column !== removed.alias));
      viewBuilder.setGroupBy(state.groupBy.filter((g) => g !== removed.alias));
      viewBuilder.setAggregations(state.aggregations.filter((a) => a.column !== removed.alias));
    }
    // Close draft if editing the removed one
    if (editingCCIndex === index) {
      setDraftCC(null);
      setEditingCCIndex(null);
    }
  }

  async function handlePreview() {
    if (state.fromTables.length === 0) {
      toast.error("请先选择数据表");
      return;
    }
    const config = compileConfig();
    try {
      const result = await previewMutation.mutateAsync(config);
      viewBuilder.setPreviewResult(result);
    } catch {
      // error handled by mutation
    }
  }

  async function handleSave() {
    if (!state.name.trim()) {
      toast.error("请输入视图名称");
      return;
    }
    if (state.fromTables.length === 0) {
      toast.error("请先选择数据表");
      return;
    }
    const config = compileConfig();
    const trimmedName = state.name.trim();

    // Check if a view with this name already exists
    const existingWithName = viewsList?.find((v) => v.name === trimmedName);

    if (existingWithName) {
      // Name already exists — confirm modification
      setConfirmDialog({
        open: true,
        targetId: existingWithName.id,
        targetName: trimmedName,
      });
      return;
    }

    // Name doesn't exist — create new view
    try {
      const result = await createView.mutateAsync({
        name: trimmedName,
        description: state.description || null,
        config_json: config,
      });
      viewBuilder.setEditingId(result.id);
      loadedViewIdRef.current = result.id;
      navigate(`/views/builder/${result.id}`, { replace: true });
    } catch {
      // error handled by mutation
    }
  }

  async function handleConfirmUpdate() {
    if (!confirmDialog) return;
    const config = compileConfig();
    try {
      const result = await updateView.mutateAsync({
        id: confirmDialog.targetId,
        name: state.name.trim(),
        description: state.description || null,
        config_json: config,
      });
      setConfirmDialog(null);
      viewBuilder.setEditingId(result.id);
      loadedViewIdRef.current = result.id;
      navigate(`/views/builder/${result.id}`, { replace: true });
    } catch {
      // error handled by mutation
    }
  }

  // ── Derived data ───────────────────────────────────────────────────────
  const availableJoinTables = tables ? tables.map((t) => t.name) : [];

  const primaryChinese = tables?.find((t) => t.name === primaryTable)?.chinese_name;

  const isSaving = createView.isPending || updateView.isPending;
  const isPreviewing = previewMutation.isPending;
  const previewResult = state.previewResult;
  const previewTab = state.previewTab;

  if (viewLoading && id) {
    return (
      <div className="p-8 text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">加载视图配置...</p>
      </div>
    );
  }

  return (
    <div className="h-full">
      <h2 className="mb-6 text-2xl font-bold tracking-tight">
        {state.editingId ? "编辑视图" : "新建视图"}
      </h2>

      <div className="flex gap-6" style={{ minHeight: "calc(100vh - 12rem)" }}>
        {/* ── Left: Configuration Panel ─────────────────────────────────── */}
        <div className="w-[520px] shrink-0 space-y-4 overflow-y-auto">
          {/* Name & Description */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">基本信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium">
                  视图名称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={state.name}
                  onChange={(e) => viewBuilder.setName(e.target.value)}
                  placeholder="输入视图名称"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">视图描述</label>
                <input
                  type="text"
                  value={state.description}
                  onChange={(e) => viewBuilder.setDescription(e.target.value)}
                  placeholder="可选描述"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
            </CardContent>
          </Card>

          {/* Source Table Selector */}
          <Card className="overflow-visible">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Database className="h-4 w-4" />
                数据表
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-visible">
              {tablesLoading ? (
                <Skeleton className="h-9 w-full" />
              ) : (
                <Select value={primaryTable || ""} onValueChange={handleSelectPrimaryTable}>
                  <SelectTrigger title={primaryChinese ?? "选择数据表"}>
                    <SelectValue>{primaryChinese ?? "选择数据表"}</SelectValue>
                  </SelectTrigger>
                  <SelectContent
                    align="start"
                    sideOffset={4}
                    alignItemWithTrigger={false}
                    className="bg-background"
                  >
                    {(tables ?? []).map((t: TableOption) => (
                      <SelectItem key={t.name} value={t.name}>
                        {t.chinese_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </CardContent>
          </Card>

          {/* Join Builder */}
          {primaryTable && (
            <Card className="overflow-visible">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ArrowRightLeft className="h-4 w-4" />
                  关联表
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-visible space-y-3">
                {state.joins.map((join, i) => {
                  const rightChinese = join.right_alias
                    ? tableDisplayName(join.right_alias, tables)
                    : tables?.find((t) => t.name === join.right_table)?.chinese_name;
                  const joinTypeLabel =
                    JOIN_TYPES.find((jt) => jt.value === join.join_type)?.label || join.join_type;
                  const leftColLabel =
                    (schemaMap[join.left_table] || schemaMap[primaryTable] || []).find(
                      (c) => c.name === join.left_key,
                    )?.label || join.left_key;
                  const rightColLabel =
                    (schemaMap[join.right_table] || []).find((c) => c.name === join.right_key)
                      ?.label || join.right_key;

                  return (
                    <div key={i} className="relative space-y-2 rounded-md border p-3">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-1 top-1 h-6 w-6"
                        onClick={() => handleRemoveJoin(i)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="mb-1 block text-xs font-medium">关联表</label>
                          <Select
                            value={join.right_table}
                            onValueChange={(v) => {
                              if (v) {
                                // Auto-generate right_alias for self-joins
                                const otherJoins = state.joins.filter((_, ji) => ji !== i);
                                let usageCount = 0;
                                if (primaryTable === v) usageCount++;
                                for (const jj of otherJoins) {
                                  if (jj.right_table === v) usageCount++;
                                }
                                const alias = usageCount > 0 ? `${v}_${usageCount + 1}` : null;
                                handleUpdateJoin(i, {
                                  right_table: v,
                                  right_alias: alias,
                                });
                              }
                            }}
                          >
                            <SelectTrigger title={rightChinese ?? "选择关联表"}>
                              <SelectValue>{rightChinese ?? "选择关联表"}</SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              {[
                                ...(join.right_table
                                  ? [tables?.find((t) => t.name === join.right_table)].filter(
                                      Boolean,
                                    )
                                  : []),
                                ...availableJoinTables
                                  .filter((t) => t !== join.right_table)
                                  .map((t) => tables?.find((tb) => tb.name === t))
                                  .filter(Boolean),
                              ]
                                .filter(Boolean)
                                .map((t) => (
                                  <SelectItem key={t!.name} value={t!.name}>
                                    {t!.chinese_name}
                                  </SelectItem>
                                ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium">连接类型</label>
                          <Select
                            value={join.join_type}
                            onValueChange={(v) => {
                              if (v) handleUpdateJoin(i, { join_type: v });
                            }}
                          >
                            <SelectTrigger title={joinTypeLabel}>
                              <SelectValue>{joinTypeLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              {JOIN_TYPES.map((jt) => (
                                <SelectItem key={jt.value} value={jt.value}>
                                  {jt.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="mb-1 block text-xs font-medium">源表关联列</label>
                          <Select
                            value={join.left_key}
                            onValueChange={(v) => {
                              if (v) handleUpdateJoin(i, { left_key: v });
                            }}
                          >
                            <SelectTrigger title={leftColLabel || "选择列"}>
                              <SelectValue>{leftColLabel || "选择列"}</SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              {(schemaMap[join.left_table] || schemaMap[primaryTable] || []).map(
                                (col) => (
                                  <SelectItem key={col.name} value={col.name}>
                                    {col.label}
                                  </SelectItem>
                                ),
                              )}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium">关联表关联列</label>
                          <Select
                            value={join.right_key}
                            onValueChange={(v) => {
                              if (v) handleUpdateJoin(i, { right_key: v });
                            }}
                          >
                            <SelectTrigger title={rightColLabel || "选择列"}>
                              <SelectValue>{rightColLabel || "选择列"}</SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              {(schemaMap[join.right_alias || join.right_table] || []).map(
                                (col) => (
                                  <SelectItem key={col.name} value={col.name}>
                                    {col.label}
                                  </SelectItem>
                                ),
                              )}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  );
                })}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAddJoin}
                  disabled={availableJoinTables.length === 0}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  添加关联表
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Column Picker */}
          {primaryTable && allSchemasLoaded && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Columns3 className="h-4 w-4" />
                  选择列
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-2 flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSelectAllColumns}
                    className="h-7 text-xs"
                  >
                    <CheckCheck className="mr-1 h-3 w-3" />
                    全选
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearAllColumns}
                    className="h-7 text-xs"
                  >
                    <X className="mr-1 h-3 w-3" />
                    取消全选
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleInvertColumnSelection}
                    className="h-7 text-xs"
                  >
                    <ArrowRightLeft className="mr-1 h-3 w-3" />
                    反选
                  </Button>
                </div>
                <div className="max-h-64 space-y-1 overflow-x-auto overflow-y-auto">
                  {visibleAllColumns.map(({ table: t, col }) => {
                    const isChecked = state.columns.some(
                      (c) => c.table === t && c.column === col.name,
                    );
                    const selectedCol = state.columns.find(
                      (c) => c.table === t && c.column === col.name,
                    );
                    const tableLabel = tableDisplayName(t, tables);
                    const fullLabel = `${tableLabel}.${col.label}`;
                    return (
                      <div
                        key={`${t}.${col.name}`}
                        className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/50"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleColumn(t, col.name)}
                          className="h-4 w-4 shrink-0"
                        />
                        <span className="whitespace-nowrap text-sm" title={fullLabel}>
                          {fullLabel}
                        </span>
                        {isChecked && (
                          <input
                            type="text"
                            value={selectedCol?.alias || ""}
                            onChange={(e) => handleColumnAlias(t, col.name, e.target.value)}
                            placeholder="别名"
                            className="h-7 w-20 shrink-0 rounded border border-input bg-transparent px-1.5 text-xs"
                          />
                        )}
                      </div>
                    );
                  })}

                  {/* Computed column checkboxes */}
                  {state.computedColumns.map((cc) => {
                    if (!cc.alias) return null;
                    const isSelected = state.selectedComputedColumns.includes(cc.alias);
                    return (
                      <div
                        key={`cc-${cc.alias}`}
                        className="flex items-center gap-2 rounded px-1 py-0.5 hover:bg-muted/50"
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {
                            if (isSelected) {
                              viewBuilder.setSelectedComputedColumns(
                                state.selectedComputedColumns.filter((a) => a !== cc.alias),
                              );
                            } else {
                              viewBuilder.setSelectedComputedColumns([
                                ...state.selectedComputedColumns,
                                cc.alias,
                              ]);
                            }
                          }}
                          className="h-4 w-4 shrink-0"
                        />
                        <span className="whitespace-nowrap text-sm" title={`计算: ${cc.alias}`}>
                          计算: {cc.alias}
                        </span>
                        <Badge variant="secondary" className="shrink-0 text-[10px]">
                          {cc.expression_type === "arithmetic"
                            ? "算术"
                            : cc.expression_type === "datetime_shift"
                              ? "日期偏移"
                              : "日期截取"}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
                {visibleAllColumns.length === 0 && (
                  <p className="text-sm text-muted-foreground">暂无可选列</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Computed Columns */}
          {primaryTable && allSchemasLoaded && (
            <Card className="overflow-visible">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Calculator className="h-4 w-4" />
                  计算列
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-visible space-y-3">
                {/* Registered computed columns (collapsed) */}
                {state.computedColumns.map((cc, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-md border px-3 py-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{cc.alias}</span>
                    <Badge variant="secondary" className="shrink-0 text-xs">
                      {cc.expression_type === "arithmetic"
                        ? "算术"
                        : cc.expression_type === "datetime_shift"
                          ? "日期偏移"
                          : "日期截取"}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      title="编辑"
                      onClick={() => handleStartEditCC(i)}
                    >
                      <Pencil className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0 text-destructive"
                      title="删除"
                      onClick={() => handleRemoveComputedColumn(i)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}

                {/* Empty state */}
                {state.computedColumns.length === 0 && !draftCC && (
                  <p className="text-sm text-muted-foreground">
                    未添加计算列。计算列可用于列之间的算术运算、日期偏移或日期截取。
                  </p>
                )}

                {/* Draft editor (expanded) */}
                {draftCC && (
                  <div className="space-y-3 rounded-md border p-3">
                    <span className="text-sm font-medium">
                      {editingCCIndex != null ? "编辑计算列" : "新建计算列"}
                    </span>

                    {/* Expression type */}
                    <div>
                      <label className="mb-1 block text-xs font-medium">表达式类型</label>
                      <Select
                        value={draftCC.expression_type}
                        onValueChange={(v) => {
                          if (v) {
                            if (v === "arithmetic") {
                              handleUpdateDraftCC({
                                expression_type: "arithmetic",
                                operands: [
                                  { type: "column", table: "", column: "", value: "" },
                                  { type: "column", table: "", column: "", value: "" },
                                ],
                                operators: ["+"],
                              });
                            } else if (v === "datetime_shift") {
                              handleUpdateDraftCC({
                                expression_type: "datetime_shift",
                                base_table: "",
                                base_column: "",
                                shift_value: "",
                                shift_unit: "days",
                              });
                            } else {
                              handleUpdateDraftCC({
                                expression_type: "datetime_trunc",
                                trunc_table: "",
                                trunc_column: "",
                                trunc_unit: "day",
                              });
                            }
                          }
                        }}
                      >
                        <SelectTrigger
                          title={
                            draftCC.expression_type === "arithmetic"
                              ? "算术运算"
                              : draftCC.expression_type === "datetime_shift"
                                ? "日期偏移"
                                : "日期截取"
                          }
                        >
                          <SelectValue>
                            {draftCC.expression_type === "arithmetic"
                              ? "算术运算"
                              : draftCC.expression_type === "datetime_shift"
                                ? "日期偏移"
                                : "日期截取"}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent
                          align="start"
                          sideOffset={4}
                          alignItemWithTrigger={false}
                          className="bg-background"
                        >
                          <SelectItem value="arithmetic">算术运算</SelectItem>
                          <SelectItem value="datetime_shift">日期偏移</SelectItem>
                          <SelectItem value="datetime_trunc">日期截取</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {draftCC.expression_type === "arithmetic" ? (
                      <>
                        {/* Chained operands */}
                        {draftCC.operands.map((op, oi) => (
                          <div key={oi}>
                            <label className="mb-1 block text-xs font-medium">
                              操作数 {oi + 1}
                            </label>
                            <div className="grid grid-cols-[80px_1fr] gap-2">
                              <div>
                                <Select
                                  value={op.type}
                                  onValueChange={(v) => {
                                    if (v) {
                                      const newOperands = [...draftCC.operands];
                                      newOperands[oi] = {
                                        type: v as "column" | "constant",
                                        table: "",
                                        column: "",
                                        value: "",
                                      };
                                      handleUpdateDraftCC({ operands: newOperands });
                                    }
                                  }}
                                >
                                  <SelectTrigger title={op.type === "column" ? "列" : "常量"}>
                                    <SelectValue>
                                      {op.type === "column" ? "列" : "常量"}
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent
                                    align="start"
                                    sideOffset={4}
                                    alignItemWithTrigger={false}
                                    className="bg-background"
                                  >
                                    <SelectItem value="column">列</SelectItem>
                                    <SelectItem value="constant">常量</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              <div>
                                {op.type === "column" ? (
                                  <ColumnCombobox
                                    value={op.table && op.column ? `${op.table}.${op.column}` : ""}
                                    options={numericColumnOptions}
                                    onChange={(key) => {
                                      const [table, ...colParts] = key.split(".");
                                      const column = colParts.join(".");
                                      const newOperands = [...draftCC.operands];
                                      newOperands[oi] = {
                                        ...newOperands[oi],
                                        table,
                                        column,
                                      };
                                      handleUpdateDraftCC({ operands: newOperands });
                                    }}
                                    placeholder="选择数值列..."
                                  />
                                ) : (
                                  <input
                                    type="number"
                                    value={op.value}
                                    onChange={(e) => {
                                      const newOperands = [...draftCC.operands];
                                      newOperands[oi] = {
                                        ...newOperands[oi],
                                        value: e.target.value,
                                      };
                                      handleUpdateDraftCC({ operands: newOperands });
                                    }}
                                    placeholder="输入数值"
                                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                  />
                                )}
                              </div>
                            </div>
                            {/* Operator between operands */}
                            {oi < draftCC.operands.length - 1 && (
                              <div className="mt-2 flex items-center gap-2">
                                <Select
                                  value={draftCC.operators[oi] ?? "+"}
                                  onValueChange={(v) => {
                                    if (v) {
                                      const newOperators = [...draftCC.operators];
                                      newOperators[oi] = v;
                                      handleUpdateDraftCC({ operators: newOperators });
                                    }
                                  }}
                                >
                                  <SelectTrigger className="w-16">
                                    <SelectValue>{draftCC.operators[oi] ?? "+"}</SelectValue>
                                  </SelectTrigger>
                                  <SelectContent
                                    align="start"
                                    sideOffset={4}
                                    alignItemWithTrigger={false}
                                    className="bg-background"
                                  >
                                    {(["+", "-", "*", "/"] as const).map((opSym) => (
                                      <SelectItem key={opSym} value={opSym}>
                                        {opSym}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <span className="text-xs text-muted-foreground">运算符</span>
                              </div>
                            )}
                          </div>
                        ))}

                        {/* Add / Remove operand buttons */}
                        <div className="flex gap-2">
                          {draftCC.operands.length < 6 && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                const newOperands = [
                                  ...draftCC.operands,
                                  {
                                    type: "column" as const,
                                    table: "",
                                    column: "",
                                    value: "",
                                  },
                                ];
                                const newOperators = [...draftCC.operators, "+"];
                                handleUpdateDraftCC({
                                  operands: newOperands,
                                  operators: newOperators,
                                });
                              }}
                            >
                              <Plus className="mr-1 h-3 w-3" />
                              添加操作数
                            </Button>
                          )}
                          {draftCC.operands.length > 2 && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                const newOperands = draftCC.operands.slice(0, -1);
                                const newOperators = draftCC.operators.slice(0, -1);
                                handleUpdateDraftCC({
                                  operands: newOperands,
                                  operators: newOperators,
                                });
                              }}
                            >
                              <X className="mr-1 h-3 w-3" />
                              移除最后一个
                            </Button>
                          )}
                        </div>
                      </>
                    ) : draftCC.expression_type === "datetime_shift" ? (
                      <>
                        {/* Datetime shift */}
                        <div>
                          <label className="mb-1 block text-xs font-medium">日期列</label>
                          <ColumnCombobox
                            value={
                              draftCC.base_table && draftCC.base_column
                                ? `${draftCC.base_table}.${draftCC.base_column}`
                                : ""
                            }
                            options={dateColumnOptions}
                            onChange={(key) => {
                              const [table, ...colParts] = key.split(".");
                              const column = colParts.join(".");
                              handleUpdateDraftCC({
                                base_table: table,
                                base_column: column,
                              });
                            }}
                            placeholder="选择日期列..."
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="mb-1 block text-xs font-medium">偏移量</label>
                            <input
                              type="number"
                              value={draftCC.shift_value}
                              onChange={(e) =>
                                handleUpdateDraftCC({
                                  shift_value: e.target.value,
                                })
                              }
                              placeholder="e.g. 30"
                              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            />
                          </div>
                          <div>
                            <label className="mb-1 block text-xs font-medium">单位</label>
                            <Select
                              value={draftCC.shift_unit as string}
                              onValueChange={(v) => {
                                if (v) handleUpdateDraftCC({ shift_unit: v });
                              }}
                            >
                              <SelectTrigger
                                title={
                                  draftCC.shift_unit === "days"
                                    ? "天"
                                    : draftCC.shift_unit === "months"
                                      ? "月"
                                      : "年"
                                }
                              >
                                <SelectValue>
                                  {draftCC.shift_unit === "days"
                                    ? "天"
                                    : draftCC.shift_unit === "months"
                                      ? "月"
                                      : "年"}
                                </SelectValue>
                              </SelectTrigger>
                              <SelectContent
                                align="start"
                                sideOffset={4}
                                alignItemWithTrigger={false}
                                className="bg-background"
                              >
                                <SelectItem value="days">天</SelectItem>
                                <SelectItem value="months">月</SelectItem>
                                <SelectItem value="years">年</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        {/* Datetime trunc */}
                        <div>
                          <label className="mb-1 block text-xs font-medium">日期列</label>
                          <ColumnCombobox
                            value={
                              draftCC.trunc_table && draftCC.trunc_column
                                ? `${draftCC.trunc_table}.${draftCC.trunc_column}`
                                : ""
                            }
                            options={dateColumnOptions}
                            onChange={(key) => {
                              const [table, ...colParts] = key.split(".");
                              const column = colParts.join(".");
                              handleUpdateDraftCC({
                                trunc_table: table,
                                trunc_column: column,
                              });
                            }}
                            placeholder="选择日期列..."
                          />
                        </div>

                        <div>
                          <label className="mb-1 block text-xs font-medium">截取粒度</label>
                          <Select
                            value={draftCC.trunc_unit as string}
                            onValueChange={(v) => {
                              if (v) handleUpdateDraftCC({ trunc_unit: v });
                            }}
                          >
                            <SelectTrigger
                              title={
                                draftCC.trunc_unit === "year"
                                  ? "年"
                                  : draftCC.trunc_unit === "quarter"
                                    ? "季度"
                                    : draftCC.trunc_unit === "month"
                                      ? "月"
                                      : draftCC.trunc_unit === "week"
                                        ? "周"
                                        : draftCC.trunc_unit === "hour"
                                          ? "小时"
                                          : draftCC.trunc_unit === "minute"
                                            ? "分钟"
                                            : "天"
                              }
                            >
                              <SelectValue>
                                {draftCC.trunc_unit === "year"
                                  ? "年"
                                  : draftCC.trunc_unit === "quarter"
                                    ? "季度"
                                    : draftCC.trunc_unit === "month"
                                      ? "月"
                                      : draftCC.trunc_unit === "week"
                                        ? "周"
                                        : draftCC.trunc_unit === "hour"
                                          ? "小时"
                                          : draftCC.trunc_unit === "minute"
                                            ? "分钟"
                                            : "天"}
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              <SelectItem value="year">年</SelectItem>
                              <SelectItem value="quarter">季度</SelectItem>
                              <SelectItem value="month">月</SelectItem>
                              <SelectItem value="week">周</SelectItem>
                              <SelectItem value="day">天</SelectItem>
                              <SelectItem value="hour">小时</SelectItem>
                              <SelectItem value="minute">分钟</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </>
                    )}

                    {/* Alias */}
                    <div>
                      <label className="mb-1 block text-xs font-medium">
                        别名 <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={draftCC.alias}
                        onChange={(e) => handleUpdateDraftCC({ alias: e.target.value })}
                        placeholder="输出列名称（必填）"
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      />
                    </div>

                    {/* Confirm / Cancel */}
                    <div className="flex gap-2">
                      <Button size="sm" disabled={!draftCC.alias.trim()} onClick={handleConfirmCC}>
                        确认
                      </Button>
                      <Button variant="outline" size="sm" onClick={handleCancelCC}>
                        取消
                      </Button>
                    </div>
                  </div>
                )}

                {/* Add button (when draft not open) */}
                {!draftCC && (
                  <Button variant="outline" size="sm" onClick={handleStartAddCC}>
                    <Plus className="mr-1 h-4 w-4" />
                    添加计算列
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          {/* Filter Builder */}
          {primaryTable && allSchemasLoaded && (
            <Card className="overflow-visible">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Filter className="h-4 w-4" />
                  筛选条件
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-visible space-y-3">
                {state.filters.length === 0 && (
                  <p className="text-sm text-muted-foreground">未添加筛选条件</p>
                )}
                {state.filters.map((f, i) => {
                  const selectedColInfo = visibleAllColumns.find(
                    (vc) => vc.col.name === f.column || `${vc.table}.${vc.col.name}` === f.column,
                  );
                  // Check if the filter column is a computed column
                  const computedCol = state.computedColumns.find((cc) => cc.alias === f.column);
                  const colType = selectedColInfo
                    ? classifyColumnType(selectedColInfo.col)
                    : computedCol
                      ? computedCol.expression_type === "arithmetic"
                        ? "number"
                        : "date"
                      : "text";
                  const isDateCol = colType === "date";
                  const operators = getOperators(colType);
                  const opLabel =
                    operators.find((o) => o.value === f.operator)?.label || f.operator;
                  return (
                    <div key={i} className="flex items-end gap-2">
                      <div className="min-w-0 max-w-[150px] flex-1">
                        <label className="mb-1 block text-xs font-medium">列</label>
                        <ColumnCombobox
                          value={f.column}
                          options={columnOptions}
                          onChange={(key) =>
                            handleUpdateFilter(i, {
                              column: key,
                              operator: operators[0]?.value || "eq",
                            })
                          }
                        />
                      </div>
                      {isDateCol ? (
                        <>
                          <div className="min-w-0 flex-1">
                            <label className="mb-1 block text-xs font-medium">开始日期</label>
                            <input
                              type="date"
                              value={f.dateStart || ""}
                              onChange={(e) => handleUpdateFilter(i, { dateStart: e.target.value })}
                              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            />
                          </div>
                          <div className="min-w-0 flex-1">
                            <label className="mb-1 block text-xs font-medium">结束日期</label>
                            <input
                              type="date"
                              value={f.dateEnd || ""}
                              onChange={(e) => handleUpdateFilter(i, { dateEnd: e.target.value })}
                              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            />
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="w-24 shrink-0">
                            <label className="mb-1 block text-xs font-medium">操作符</label>
                            <Select
                              value={f.operator}
                              onValueChange={(v) => {
                                if (v) handleUpdateFilter(i, { operator: v });
                              }}
                            >
                              <SelectTrigger title={opLabel}>
                                <SelectValue>{opLabel}</SelectValue>
                              </SelectTrigger>
                              <SelectContent
                                align="start"
                                sideOffset={4}
                                alignItemWithTrigger={false}
                                className="bg-background"
                              >
                                {operators.map((op) => (
                                  <SelectItem key={op.value} value={op.value}>
                                    {op.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          {!["is_null", "is_not_null"].includes(f.operator) && (
                            <div className="min-w-0 flex-1">
                              <label className="mb-1 block text-xs font-medium">值</label>
                              {colType === "number" ? (
                                <input
                                  type="number"
                                  value={f.value}
                                  onChange={(e) =>
                                    handleUpdateFilter(i, {
                                      value: e.target.value,
                                    })
                                  }
                                  placeholder="输入数值"
                                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                />
                              ) : (
                                <input
                                  type="text"
                                  value={f.value}
                                  onChange={(e) =>
                                    handleUpdateFilter(i, {
                                      value: e.target.value,
                                    })
                                  }
                                  placeholder="输入筛选值"
                                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                />
                              )}
                            </div>
                          )}
                        </>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() => handleRemoveFilter(i)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
                <Button variant="outline" size="sm" onClick={handleAddFilter}>
                  <Plus className="mr-1 h-4 w-4" />
                  添加筛选条件
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Group By & Aggregation */}
          {primaryTable && allSchemasLoaded && (
            <Card className="overflow-visible">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-4 w-4" />
                  分组与聚合
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-visible space-y-3">
                <div>
                  <label className="mb-1 block text-sm font-medium">分组列 (GROUP BY)</label>
                  <div className="flex flex-wrap gap-1">
                    {visibleAllColumns.map(({ table: t, col }) => {
                      const key = `${t}.${col.name}`;
                      const isSelected = state.groupBy.includes(key);
                      const tableLabel = tableDisplayName(t, tables);
                      const fullLabel = `${tableLabel}.${col.label}`;
                      return (
                        <Badge
                          key={key}
                          variant={isSelected ? "default" : "outline"}
                          className="cursor-pointer"
                          title={fullLabel}
                          onClick={() => {
                            if (isSelected) {
                              viewBuilder.setGroupBy(state.groupBy.filter((g) => g !== key));
                            } else {
                              viewBuilder.setGroupBy([...state.groupBy, key]);
                            }
                          }}
                        >
                          {tableLabel}.{col.label}
                        </Badge>
                      );
                    })}
                    {/* Computed column badges */}
                    {state.computedColumns.map((cc) => {
                      if (!cc.alias) return null;
                      const isSelected = state.groupBy.includes(cc.alias);
                      return (
                        <Badge
                          key={`cc-${cc.alias}`}
                          variant={isSelected ? "default" : "outline"}
                          className="cursor-pointer"
                          title={`计算: ${cc.alias}`}
                          onClick={() => {
                            if (isSelected) {
                              viewBuilder.setGroupBy(state.groupBy.filter((g) => g !== cc.alias));
                            } else {
                              viewBuilder.setGroupBy([...state.groupBy, cc.alias]);
                            }
                          }}
                        >
                          计算: {cc.alias}
                        </Badge>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="block text-sm font-medium">聚合函数</label>
                  {state.aggregations.map((agg, i) => {
                    const funcLabel =
                      AGG_FUNCTIONS.find((af) => af.value === agg.function)?.label || agg.function;
                    return (
                      <div key={i} className="flex items-end gap-2">
                        <div className="w-24 shrink-0">
                          <Select
                            value={agg.function}
                            onValueChange={(v) => {
                              if (v) handleUpdateAggregation(i, { function: v });
                            }}
                          >
                            <SelectTrigger title={funcLabel}>
                              <SelectValue>{funcLabel}</SelectValue>
                            </SelectTrigger>
                            <SelectContent
                              align="start"
                              sideOffset={4}
                              alignItemWithTrigger={false}
                              className="bg-background"
                            >
                              {AGG_FUNCTIONS.map((af) => (
                                <SelectItem key={af.value} value={af.value}>
                                  {af.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="min-w-0 max-w-[150px] flex-1">
                          <ColumnCombobox
                            value={agg.column}
                            options={[{ key: "*", label: "* (全部)" }, ...columnOptions]}
                            onChange={(key) => handleUpdateAggregation(i, { column: key })}
                          />
                        </div>
                        <input
                          type="text"
                          value={agg.alias}
                          onChange={(e) =>
                            handleUpdateAggregation(i, {
                              alias: e.target.value,
                            })
                          }
                          placeholder="别名"
                          className="h-9 w-24 shrink-0 rounded-md border border-input bg-transparent px-2 text-sm"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="shrink-0"
                          onClick={() => handleRemoveAggregation(i)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    );
                  })}
                  <Button variant="outline" size="sm" onClick={handleAddAggregation}>
                    <Plus className="mr-1 h-4 w-4" />
                    添加聚合
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Order & Limit */}
          {primaryTable && allSchemasLoaded && (
            <Card className="overflow-visible">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ArrowRightLeft className="h-4 w-4" />
                  排序与限制
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-visible space-y-3">
                {/* ORDER BY */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium">排序 (ORDER BY)</label>
                  {state.orderBy.map((order, i) => (
                    <div key={i} className="flex items-end gap-2">
                      <div className="min-w-0 flex-1">
                        <ColumnCombobox
                          value={order.column}
                          options={columnOptions}
                          onChange={(key) => {
                            const updated = [...state.orderBy];
                            updated[i] = { ...updated[i], column: key };
                            viewBuilder.setOrderBy(updated);
                          }}
                          placeholder="选择排序列..."
                        />
                      </div>
                      <Select
                        value={order.direction}
                        onValueChange={(v) => {
                          if (v) {
                            const updated = [...state.orderBy];
                            updated[i] = {
                              ...updated[i],
                              direction: v as "asc" | "desc",
                            };
                            viewBuilder.setOrderBy(updated);
                          }
                        }}
                      >
                        <SelectTrigger
                          className="w-20 shrink-0"
                          title={order.direction === "asc" ? "升序" : "降序"}
                        >
                          <SelectValue>{order.direction === "asc" ? "升序" : "降序"}</SelectValue>
                        </SelectTrigger>
                        <SelectContent
                          align="start"
                          sideOffset={4}
                          alignItemWithTrigger={false}
                          className="bg-background"
                        >
                          <SelectItem value="asc">升序</SelectItem>
                          <SelectItem value="desc">降序</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() =>
                          viewBuilder.setOrderBy(state.orderBy.filter((_, idx) => idx !== i))
                        }
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      viewBuilder.setOrderBy([...state.orderBy, { column: "", direction: "asc" }])
                    }
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    添加排序
                  </Button>
                </div>

                {/* LIMIT */}
                <div>
                  <label className="mb-1 block text-sm font-medium">行数限制 (LIMIT)</label>
                  <input
                    type="number"
                    value={state.limit ?? ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      viewBuilder.setLimit(val === "" ? null : Math.max(0, Number(val)));
                    }}
                    placeholder="留空表示不限制"
                    min={0}
                    className="flex h-9 w-32 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Save Buttons */}
          <div className="flex gap-2 pb-4">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-1 h-4 w-4" />
              )}
              保存
            </Button>
            <Button
              variant="outline"
              onClick={handlePreview}
              disabled={isPreviewing || state.fromTables.length === 0}
            >
              {isPreviewing ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Eye className="mr-1 h-4 w-4" />
              )}
              预览
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                loadedViewIdRef.current = null;
                viewBuilder.clearConfig();
                viewBuilder.setName("");
                viewBuilder.setDescription("");
                navigate("/views/builder", { replace: true });
              }}
            >
              <RotateCcw className="mr-1 h-4 w-4" />
              清除配置
            </Button>
          </div>

          {/* Confirmation Dialog */}
          {confirmDialog && (
            <div className="fixed inset-0 z-50 flex items-center justify-center">
              <div
                className="absolute inset-0 bg-black/50"
                onClick={() => setConfirmDialog(null)}
              />
              <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg">
                <h3 className="text-lg font-semibold">确认修改</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  视图名称「{confirmDialog.targetName}」已存在，是否修改该视图？
                </p>
                <div className="mt-6 flex justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setConfirmDialog(null)}
                    disabled={isSaving}
                  >
                    取消
                  </Button>
                  <Button onClick={handleConfirmUpdate} disabled={isSaving}>
                    {isSaving ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-1 h-4 w-4" />
                    )}
                    确定
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Right: Preview Panel ──────────────────────────────────────── */}
        <div className="min-w-0 flex-1">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">预览</CardTitle>
                {previewResult && (
                  <div className="flex gap-1">
                    <Button
                      variant={previewTab === "data" ? "default" : "outline"}
                      size="sm"
                      onClick={() => viewBuilder.setPreviewTab("data")}
                    >
                      数据预览
                    </Button>
                    <Button
                      variant={previewTab === "sql" ? "default" : "outline"}
                      size="sm"
                      onClick={() => viewBuilder.setPreviewTab("sql")}
                    >
                      SQL语句
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!previewResult ? (
                <div className="rounded-md bg-muted/30 p-16 text-center">
                  <Eye className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
                  <p className="text-lg text-muted-foreground">点击"预览"查看结果</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    选择数据表和列后，点击预览按钮查看查询结果
                  </p>
                </div>
              ) : previewTab === "data" ? (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {previewResult.columns.map((col) => (
                          <TableHead key={col} className="max-w-[200px] truncate">
                            {col}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewResult.rows.length === 0 ? (
                        <TableRow>
                          <TableCell
                            colSpan={previewResult.columns.length || 1}
                            className="p-8 text-center text-muted-foreground"
                          >
                            暂无数据
                          </TableCell>
                        </TableRow>
                      ) : (
                        previewResult.rows.map((row, i) => (
                          <TableRow key={i}>
                            {previewResult.columns.map((col) => (
                              <TableCell
                                key={col}
                                className="max-w-[200px] truncate"
                                title={String(row[col] ?? "")}
                              >
                                {row[col] != null ? String(row[col]) : ""}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                  {previewResult.rows.length > 0 && (
                    <p className="mt-2 text-center text-xs text-muted-foreground">
                      显示最多 20 条记录
                    </p>
                  )}
                </div>
              ) : (
                <pre className="overflow-x-auto rounded-md bg-muted p-4 text-sm">
                  <code>{previewResult.sql}</code>
                </pre>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
