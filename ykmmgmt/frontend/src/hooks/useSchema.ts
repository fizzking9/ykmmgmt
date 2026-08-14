import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

// ── Types ──────────────────────────────────────────────────────────────────

export interface SchemaTableInfo {
  name: string;
  chinese_name: string;
  column_count: number;
  row_count: number;
  read_only: boolean;
  dynamic: boolean;
}

export interface SchemaColumnDetail {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
  unique: boolean;
  foreign_key: string | null;
  label: string;
  description: string | null;
  default: string | null;
  internal: boolean;
}

export interface SchemaTableDetail {
  name: string;
  chinese_name: string;
  read_only: boolean;
  dynamic: boolean;
  upsert_key: string[];
  dedup_enabled: boolean;
  columns: SchemaColumnDetail[];
  sample_rows: Record<string, unknown>[];
}

export interface ColumnTypeInfo {
  key: string;
  label: string;
  has_length: boolean;
  default_length: number | null;
}

export interface ColumnDefinitionPayload {
  name: string;
  type: string;
  length?: number | null;
  nullable?: boolean;
  unique?: boolean;
  primary_key?: boolean;
  foreign_key?: string | null;
  label?: string | null;
  description?: string | null;
  default?: string | null;
}

export interface InferCsvResponse {
  columns: ColumnDefinitionPayload[];
  row_count: number;
  suggested_table_name: string;
}

export interface DependencyRef {
  id: string;
  name: string;
}

export interface FkDependencyRef {
  table: string;
  column: string;
  references: string;
}

export interface DependencyInfo {
  views: DependencyRef[];
  visualizations: DependencyRef[];
  tables: FkDependencyRef[];
}

export interface CreateTablePayload {
  name: string;
  display_name?: string | null;
  columns: ColumnDefinitionPayload[];
  /** Upsert key column names (optional; defaults to the user PK). */
  upsert_key?: string[] | null;
  /** Keyless-table exact-duplicate dedup toggle. */
  dedup_enabled?: boolean;
}

export interface ModifyColumnPayload {
  /** New column name (rename). */
  name?: string;
  type?: string;
  length?: number | null;
  nullable?: boolean;
  unique?: boolean;
  label?: string;
  description?: string;
  default?: string;
  foreign_key?: string;
}

export interface RenameTablePayload {
  /** New English table name (rename). */
  name?: string;
  /** New Chinese display name. */
  display_name?: string;
  /** New upsert key column names; empty list clears to PK/no-key. */
  upsert_key?: string[];
  /** Keyless-table exact-duplicate dedup toggle. */
  dedup_enabled?: boolean;
}

export interface FkColumnOption {
  name: string;
  label: string;
  type: string;
  primary_key: boolean;
  unique: boolean;
}

export interface FkTableOption {
  table: string;
  chinese_name: string;
  columns: FkColumnOption[];
}

// ── API helpers ────────────────────────────────────────────────────────────

async function parseError(res: Response, fallback: string): Promise<Error> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string" && detail) return new Error(detail);
  if (detail && typeof detail === "object" && detail.message) return new Error(detail.message);
  return new Error(`${fallback}（HTTP ${res.status}）`);
}

async function fetchSchemaTables(): Promise<SchemaTableInfo[]> {
  const res = await fetch("/api/schema/tables");
  if (!res.ok) throw await parseError(res, "获取数据表列表失败");
  return res.json();
}

async function fetchSchemaTableDetail(name: string): Promise<SchemaTableDetail> {
  const res = await fetch(`/api/schema/tables/${name}`);
  if (!res.ok) throw await parseError(res, "获取表结构失败");
  return res.json();
}

async function fetchColumnTypes(): Promise<ColumnTypeInfo[]> {
  const res = await fetch("/api/schema/column-types");
  if (!res.ok) throw await parseError(res, "获取列类型失败");
  return res.json();
}

async function fetchDependencies(name: string, column?: string): Promise<DependencyInfo> {
  const params = column ? `?column=${encodeURIComponent(column)}` : "";
  const res = await fetch(`/api/schema/tables/${name}/dependencies${params}`);
  if (!res.ok) throw await parseError(res, "获取依赖信息失败");
  return res.json();
}

async function fetchFkOptions(): Promise<FkTableOption[]> {
  const res = await fetch("/api/schema/fk-options");
  if (!res.ok) throw await parseError(res, "获取外键选项失败");
  return res.json();
}

async function createTable(payload: CreateTablePayload): Promise<SchemaTableDetail> {
  const res = await fetch("/api/schema/tables", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res, "创建数据表失败");
  return res.json();
}

async function inferFromCsv(file: File): Promise<InferCsvResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/schema/infer-from-csv", { method: "POST", body: form });
  if (!res.ok) throw await parseError(res, "CSV 结构推断失败");
  return res.json();
}

async function addColumn(table: string, col: ColumnDefinitionPayload): Promise<SchemaTableDetail> {
  const res = await fetch(`/api/schema/tables/${table}/columns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(col),
  });
  if (!res.ok) throw await parseError(res, "添加列失败");
  return res.json();
}

async function dropColumn(
  table: string,
  column: string,
): Promise<{ deleted_column: string; dependencies: DependencyInfo }> {
  const res = await fetch(`/api/schema/tables/${table}/columns/${column}`, {
    method: "DELETE",
  });
  if (!res.ok) throw await parseError(res, "删除列失败");
  return res.json();
}

async function modifyColumn(
  table: string,
  column: string,
  payload: ModifyColumnPayload,
): Promise<{ modified_column: string; warning: string | null }> {
  const res = await fetch(`/api/schema/tables/${table}/columns/${column}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res, "修改列失败");
  return res.json();
}

async function renameTable(table: string, payload: RenameTablePayload): Promise<SchemaTableDetail> {
  const res = await fetch(`/api/schema/tables/${table}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await parseError(res, "重命名数据表失败");
  return res.json();
}

async function deleteTable(
  table: string,
  confirm: boolean,
): Promise<{ deleted: string; dependencies: DependencyInfo }> {
  const res = await fetch(`/api/schema/tables/${table}?confirm=${confirm}`, {
    method: "DELETE",
  });
  if (!res.ok) throw await parseError(res, "删除数据表失败");
  return res.json();
}

// ── Query hooks ────────────────────────────────────────────────────────────

export function useSchemaTables() {
  return useQuery({
    queryKey: ["schemaTables"],
    queryFn: fetchSchemaTables,
    staleTime: 30_000,
  });
}

export function useSchemaTableDetail(name: string | undefined) {
  return useQuery({
    queryKey: ["schemaTableDetail", name],
    queryFn: () => fetchSchemaTableDetail(name!),
    enabled: !!name,
    staleTime: 10_000,
  });
}

export function useColumnTypes() {
  return useQuery({
    queryKey: ["columnTypes"],
    queryFn: fetchColumnTypes,
    staleTime: 5 * 60_000,
  });
}

export function useTableDependencies(name: string | undefined, column?: string) {
  return useQuery({
    queryKey: ["tableDependencies", name, column ?? null],
    queryFn: () => fetchDependencies(name!, column),
    enabled: !!name,
    staleTime: 10_000,
  });
}

export function useFkOptions() {
  return useQuery({
    queryKey: ["fkOptions"],
    queryFn: fetchFkOptions,
    staleTime: 60_000,
  });
}

// ── Mutations ──────────────────────────────────────────────────────────────

function useInvalidateSchema() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["schemaTables"] });
    queryClient.invalidateQueries({ queryKey: ["schemaTableDetail"] });
    queryClient.invalidateQueries({ queryKey: ["tables"] });
    queryClient.invalidateQueries({ queryKey: ["tableSchema"] });
  };
}

export function useCreateTable() {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: createTable,
    onSuccess: () => {
      invalidate();
      toast.success("数据表创建成功");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useInferCsv() {
  return useMutation({
    mutationFn: inferFromCsv,
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useAddColumn(table: string) {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: (col: ColumnDefinitionPayload) => addColumn(table, col),
    onSuccess: () => {
      invalidate();
      toast.success("列添加成功");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useDropColumn(table: string) {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: (column: string) => dropColumn(table, column),
    onSuccess: () => {
      invalidate();
      toast.success("列已删除");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useModifyColumn(table: string) {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: ({ column, ...payload }: { column: string } & ModifyColumnPayload) =>
      modifyColumn(table, column, payload),
    onSuccess: (data) => {
      invalidate();
      if (data.warning) {
        toast.warning(data.warning);
      } else {
        toast.success("列已更新");
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useRenameTable(table: string) {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: (payload: RenameTablePayload) => renameTable(table, payload),
    onSuccess: () => {
      invalidate();
      toast.success("数据表已重命名");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useDeleteTable() {
  const invalidate = useInvalidateSchema();
  return useMutation({
    mutationFn: ({ table, confirm }: { table: string; confirm: boolean }) =>
      deleteTable(table, confirm),
    onSuccess: () => {
      invalidate();
      toast.success("数据表已删除");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
