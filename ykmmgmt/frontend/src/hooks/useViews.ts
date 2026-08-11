import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ColumnSpec {
  table: string;
  column: string;
  alias?: string | null;
}

export interface JoinSpec {
  left_table: string;
  right_table: string;
  right_alias?: string | null;
  join_type: string;
  left_key: string;
  right_key: string;
}

export interface FilterSpec {
  column: string;
  operator: string;
  value: unknown;
  date_start?: string | null;
  date_end?: string | null;
}

export interface AggregationSpec {
  function: string;
  column: string;
  alias?: string | null;
}

export interface ComputedOperand {
  type: "column" | "constant";
  table?: string | null;
  column?: string | null;
  value?: string | null;
}

export interface ComputedColumnSpec {
  alias: string;
  expression_type: "arithmetic" | "datetime_shift" | "datetime_trunc";
  operands?: ComputedOperand[];
  operators?: string[];
  base_column?: ComputedOperand | null;
  shift_value?: string | null;
  shift_unit?: "days" | "months" | "years" | null;
  trunc_column?: ComputedOperand | null;
  trunc_unit?: "year" | "quarter" | "month" | "week" | "day" | "hour" | "minute" | null;
}

export interface OrderSpec {
  column: string;
  direction: "asc" | "desc";
}

export interface ViewConfig {
  from_tables: string[];
  joins: JoinSpec[];
  columns: ColumnSpec[];
  computed_columns: ComputedColumnSpec[];
  selected_computed_columns: string[];
  filters: FilterSpec[];
  group_by: string[];
  aggregations: AggregationSpec[];
  order_by: OrderSpec[];
  limit: number | null;
}

export interface ViewResponse {
  id: string;
  name: string;
  description: string | null;
  config_json: ViewConfig;
  generated_sql: string | null;
  created_at: string;
  updated_at: string;
}

export interface ViewListResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface PreviewResponse {
  sql: string;
  rows: Record<string, unknown>[];
  columns: string[];
}

export interface ViewDataResponse {
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  size: number;
  columns: string[];
}

export interface ColumnInfo {
  name: string;
  type: string;
  label: string;
}

// ── API helpers ────────────────────────────────────────────────────────────

async function fetchViews(): Promise<ViewListResponse[]> {
  const res = await fetch("/api/views");
  if (!res.ok) throw new Error("获取视图列表失败");
  return res.json();
}

async function fetchView(id: string): Promise<ViewResponse> {
  const res = await fetch(`/api/views/${id}`);
  if (!res.ok) throw new Error("获取视图详情失败");
  return res.json();
}

async function createView(data: {
  name: string;
  description?: string | null;
  config_json: ViewConfig;
}): Promise<ViewResponse> {
  const res = await fetch("/api/views", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "创建视图失败" }));
    throw new Error(err.detail || "创建视图失败");
  }
  return res.json();
}

async function updateView(
  id: string,
  data: {
    name?: string;
    description?: string | null;
    config_json?: ViewConfig;
  },
): Promise<ViewResponse> {
  const res = await fetch(`/api/views/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "更新视图失败" }));
    throw new Error(err.detail || "更新视图失败");
  }
  return res.json();
}

async function previewView(config: ViewConfig): Promise<PreviewResponse> {
  const res = await fetch("/api/views/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_json: config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "预览失败" }));
    throw new Error(err.detail || "预览失败");
  }
  return res.json();
}

async function deleteView(id: string): Promise<void> {
  const res = await fetch(`/api/views/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "删除视图失败" }));
    throw new Error(err.detail || "删除视图失败");
  }
}

async function fetchViewData(id: string, page: number, size: number): Promise<ViewDataResponse> {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  const res = await fetch(`/api/views/${id}/data?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "获取视图数据失败" }));
    throw new Error(err.detail || "获取视图数据失败");
  }
  return res.json();
}

export async function fetchViewFullData(id: string): Promise<ViewDataResponse> {
  const params = new URLSearchParams({ page: "1", size: "0" });
  const res = await fetch(`/api/views/${id}/data?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "获取视图数据失败" }));
    throw new Error(err.detail || "获取视图数据失败");
  }
  return res.json();
}

async function fetchTableSchema(tableName: string): Promise<ColumnInfo[]> {
  const res = await fetch(`/api/tables/${tableName}/schema`);
  if (!res.ok) throw new Error("获取表结构失败");
  return res.json();
}

// ── Hooks ──────────────────────────────────────────────────────────────────

export function useViews() {
  return useQuery({
    queryKey: ["views"],
    queryFn: fetchViews,
    staleTime: 30_000,
  });
}

export function useView(id: string | undefined) {
  return useQuery({
    queryKey: ["views", id],
    queryFn: () => fetchView(id!),
    enabled: !!id,
  });
}

export function useCreateView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createView,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
      toast.success("视图保存成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useUpdateView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      description?: string | null;
      config_json?: ViewConfig;
    }) => updateView(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
      toast.success("视图更新成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useDeleteView() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteView,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["views"] });
      toast.success("视图已删除");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useViewData(id: string | undefined, page: number, size: number) {
  return useQuery({
    queryKey: ["viewData", id, page, size],
    queryFn: () => fetchViewData(id!, page, size),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useViewFullData(id: string | undefined) {
  return useQuery({
    queryKey: ["viewFullData", id],
    queryFn: () => fetchViewFullData(id!),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function usePreviewView() {
  return useMutation({
    mutationFn: previewView,
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useTableSchema(tableName: string | undefined) {
  return useQuery({
    queryKey: ["tableSchema", tableName],
    queryFn: () => fetchTableSchema(tableName!),
    enabled: !!tableName,
    staleTime: 60_000,
  });
}
