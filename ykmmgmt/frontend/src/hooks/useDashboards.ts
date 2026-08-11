import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchViewFullData, type ViewDataResponse } from "@/hooks/useViews";

// ── Types ───────────────────────────────────────────────────────────────────

export type TileType = "visualization" | "text" | "kpi_card";

export interface KpiTileConfig {
  view_id: string;
  value_column: string;
  label: string;
  agg: "SUM" | "COUNT" | "AVG" | "MIN" | "MAX";
}

export interface DashboardTile {
  i: string;
  tile_type: TileType;
  visualization_id?: string | null;
  x: number;
  y: number;
  w: number;
  h: number;
  content?: string | null;
  config?: KpiTileConfig | null;
  [extra: string]: unknown;
}

export interface DashboardResponse {
  id: string;
  name: string;
  description: string | null;
  layout_json: DashboardTile[];
  created_at: string;
  updated_at: string;
}

export interface DashboardListResponse {
  id: string;
  name: string;
  description: string | null;
  tile_count: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardPayload {
  name: string;
  description?: string | null;
  layout_json: DashboardTile[];
}

// ── API helpers ─────────────────────────────────────────────────────────────

async function fetchDashboards(): Promise<DashboardListResponse[]> {
  const res = await fetch("/api/dashboards");
  if (!res.ok) throw new Error("获取仪表盘列表失败");
  return res.json();
}

async function fetchDashboard(id: string): Promise<DashboardResponse> {
  const res = await fetch(`/api/dashboards/${id}`);
  if (!res.ok) throw new Error("获取仪表盘详情失败");
  return res.json();
}

async function createDashboard(data: DashboardPayload): Promise<DashboardResponse> {
  const res = await fetch("/api/dashboards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "创建仪表盘失败" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "创建仪表盘失败");
  }
  return res.json();
}

async function updateDashboard(
  id: string,
  data: Partial<DashboardPayload>,
): Promise<DashboardResponse> {
  const res = await fetch(`/api/dashboards/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "更新仪表盘失败" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "更新仪表盘失败");
  }
  return res.json();
}

async function deleteDashboard(id: string): Promise<void> {
  const res = await fetch(`/api/dashboards/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "删除仪表盘失败" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "删除仪表盘失败");
  }
}

// ── Hooks ───────────────────────────────────────────────────────────────────

export function useDashboards() {
  return useQuery({
    queryKey: ["dashboards"],
    queryFn: fetchDashboards,
    staleTime: 30_000,
  });
}

export function useDashboard(id: string | undefined) {
  return useQuery({
    queryKey: ["dashboards", id],
    queryFn: () => fetchDashboard(id!),
    enabled: !!id,
  });
}

export function useCreateDashboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDashboard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      toast.success("仪表盘保存成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useUpdateDashboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<DashboardPayload>) =>
      updateDashboard(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      queryClient.invalidateQueries({ queryKey: ["dashboards", variables.id] });
      toast.success("仪表盘更新成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useDeleteDashboard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDashboard,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      queryClient.removeQueries({ queryKey: ["dashboards", id] });
      toast.success("仪表盘已删除");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

// ── KPI tile data ───────────────────────────────────────────────────────────
// Ad-hoc KPI tiles fetch their view's full data and aggregate client-side.
// Cached until the tile's manual 刷新 button invalidates the key.

export function useKpiTileData(viewId: string | undefined) {
  return useQuery<ViewDataResponse>({
    queryKey: ["kpiTileData", viewId],
    queryFn: () => fetchViewFullData(viewId!),
    enabled: !!viewId,
    staleTime: Infinity,
    // No background retries — surface errors in the tile immediately
    retry: false,
  });
}

/** Compute the configured aggregation over a numeric column client-side. */
export function computeAggregation(
  rows: Record<string, unknown>[],
  column: string,
  agg: KpiTileConfig["agg"],
): number | null {
  const values = rows
    .map((r) => r[column])
    .filter((v) => v !== null && v !== undefined)
    .map((v) => Number(v))
    .filter((v) => !isNaN(v) && isFinite(v));
  if (agg === "COUNT") return rows.length;
  if (!values.length) return null;
  switch (agg) {
    case "SUM":
      return values.reduce((a, b) => a + b, 0);
    case "AVG":
      return values.reduce((a, b) => a + b, 0) / values.length;
    case "MIN":
      return Math.min(...values);
    case "MAX":
      return Math.max(...values);
  }
}
