import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

// ── Types ───────────────────────────────────────────────────────────────────

export interface VisualizationResponse {
  id: string;
  name: string;
  view_id: string;
  chart_type: string;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VisualizationListResponse {
  id: string;
  name: string;
  view_id: string;
  chart_type: string;
  created_at: string;
  updated_at: string;
}

export interface VisualizationDataResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  chart_type: string;
  config_json: Record<string, unknown>;
}

// ── API helpers ─────────────────────────────────────────────────────────────

async function fetchVisualizations(): Promise<VisualizationListResponse[]> {
  const res = await fetch("/api/visualizations");
  if (!res.ok) throw new Error("获取可视化列表失败");
  return res.json();
}

async function fetchVisualization(id: string): Promise<VisualizationResponse> {
  const res = await fetch(`/api/visualizations/${id}`);
  if (!res.ok) throw new Error("获取可视化详情失败");
  return res.json();
}

async function createVisualization(data: {
  name: string;
  view_id: string;
  chart_type: string;
  config_json: Record<string, unknown>;
}): Promise<VisualizationResponse> {
  const res = await fetch("/api/visualizations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "创建可视化失败" }));
    throw new Error(err.detail || "创建可视化失败");
  }
  return res.json();
}

async function updateVisualization(
  id: string,
  data: {
    name?: string;
    view_id?: string;
    chart_type?: string;
    config_json?: Record<string, unknown>;
  },
): Promise<VisualizationResponse> {
  const res = await fetch(`/api/visualizations/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "更新可视化失败" }));
    throw new Error(err.detail || "更新可视化失败");
  }
  return res.json();
}

async function deleteVisualization(id: string): Promise<void> {
  const res = await fetch(`/api/visualizations/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "删除可视化失败" }));
    throw new Error(err.detail || "删除可视化失败");
  }
}

async function fetchVisualizationData(id: string): Promise<VisualizationDataResponse> {
  const res = await fetch(`/api/visualizations/${id}/data`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "获取可视化数据失败" }));
    throw new Error(err.detail || "获取可视化数据失败");
  }
  return res.json();
}

// ── Hooks ───────────────────────────────────────────────────────────────────

export function useVisualizations() {
  return useQuery({
    queryKey: ["visualizations"],
    queryFn: fetchVisualizations,
    staleTime: 30_000,
  });
}

export function useVisualization(id: string | undefined) {
  return useQuery({
    queryKey: ["visualizations", id],
    queryFn: () => fetchVisualization(id!),
    enabled: !!id,
  });
}

export function useCreateVisualization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createVisualization,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["visualizations"] });
      toast.success("可视化保存成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useUpdateVisualization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      view_id?: string;
      chart_type?: string;
      config_json?: Record<string, unknown>;
    }) => updateVisualization(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["visualizations"] });
      // Cached render data (staleTime: Infinity) must be dropped so the list
      // thumbnails and full-size view show the updated visualization
      // immediately — without waiting for a manual 刷新.
      queryClient.invalidateQueries({ queryKey: ["visualizationData", variables.id] });
      toast.success("可视化更新成功");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useDeleteVisualization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteVisualization,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["visualizations"] });
      queryClient.removeQueries({ queryKey: ["visualizationData", id] });
      toast.success("可视化已删除");
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });
}

export function useVisualizationData(id: string | undefined) {
  return useQuery({
    queryKey: ["visualizationData", id],
    queryFn: () => fetchVisualizationData(id!),
    enabled: !!id,
    // Data is cached until explicitly invalidated by the manual 刷新 button —
    // revisiting a page (tab/route navigation) must NOT re-query.
    staleTime: Infinity,
  });
}
