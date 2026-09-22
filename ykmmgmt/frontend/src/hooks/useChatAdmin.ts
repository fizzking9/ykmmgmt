import { apiFetch } from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

// ── Types ───────────────────────────────────────────────────────────────────

export interface QAPair {
  id: string;
  question: string;
  question_variants: string[];
  answer: string;
  category: string | null;
  is_active: boolean;
  has_embeddings: boolean;
  embedding_model: string | null;
  needs_rebuild: boolean;
  variant_count: number;
  created_at: string;
  updated_at: string;
}

export interface QAPairPayload {
  question: string;
  question_variants: string[];
  answer: string;
  category: string | null;
  is_active: boolean;
}

export interface QAPairPage {
  items: QAPair[];
  total: number;
  page: number;
  size: number;
}

export interface QAPairListParams {
  page: number;
  size: number;
  category: string | null;
}

export interface EmbeddingModelOption {
  name: string;
  label: string;
  dims: number;
  note: string;
}

export interface EmbeddingModelsInfo {
  items: EmbeddingModelOption[];
  active_model: string;
  active_label: string;
  threshold: number;
  needs_rebuild: number;
}

// ── API helpers ──────────────────────────────────────────────────────────────

async function errDetail(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({ detail: fallback }));
  return typeof err.detail === "string" ? err.detail : fallback;
}

async function fetchQAPairs(params: QAPairListParams): Promise<QAPairPage> {
  const qs = new URLSearchParams({ page: String(params.page), size: String(params.size) });
  if (params.category) qs.set("category", params.category);
  const res = await apiFetch(`/api/chat/qa-pairs?${qs.toString()}`);
  if (!res.ok) throw new Error(await errDetail(res, "获取问答列表失败"));
  return res.json();
}

async function fetchCategories(): Promise<string[]> {
  const res = await apiFetch("/api/chat/categories");
  if (!res.ok) throw new Error(await errDetail(res, "获取分类失败"));
  return res.json();
}

async function createQA(payload: QAPairPayload): Promise<QAPair> {
  const res = await apiFetch("/api/chat/qa-pairs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errDetail(res, "创建问答失败"));
  return res.json();
}

async function updateQA({ id, ...payload }: { id: string } & Partial<QAPairPayload>): Promise<QAPair> {
  const res = await apiFetch(`/api/chat/qa-pairs/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errDetail(res, "更新问答失败"));
  return res.json();
}

async function deleteQA(id: string): Promise<void> {
  const res = await apiFetch(`/api/chat/qa-pairs/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await errDetail(res, "删除问答失败"));
}

async function rebuildEmbeddings(): Promise<{ rebuilt: number; model_name: string }> {
  const res = await apiFetch("/api/chat/qa-pairs/rebuild-embeddings", { method: "POST" });
  if (!res.ok) throw new Error(await errDetail(res, "重建向量失败"));
  return res.json();
}

async function fetchEmbeddingModels(): Promise<EmbeddingModelsInfo> {
  const res = await apiFetch("/api/chat/embedding-models");
  if (!res.ok) throw new Error(await errDetail(res, "获取向量模型列表失败"));
  return res.json();
}

async function activateEmbeddingModel(modelName: string): Promise<{ rebuilt: number; model_name: string }> {
  const res = await apiFetch("/api/chat/embedding-models/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_name: modelName }),
  });
  if (!res.ok) throw new Error(await errDetail(res, "切换向量模型失败"));
  return res.json();
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useQAPairs(params: QAPairListParams) {
  return useQuery({
    queryKey: ["chat", "qa-pairs", params],
    queryFn: () => fetchQAPairs(params),
    placeholderData: (prev) => prev, // keep rows while paging to avoid flicker
  });
}

export function useQACategories() {
  return useQuery({ queryKey: ["chat", "categories"], queryFn: fetchCategories, staleTime: 60_000 });
}

function invalidateQA(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["chat", "qa-pairs"] });
  qc.invalidateQueries({ queryKey: ["chat", "categories"] });
}

export function useEmbeddingModels() {
  return useQuery({
    queryKey: ["chat", "embedding-models"],
    queryFn: fetchEmbeddingModels,
    staleTime: 30_000,
  });
}

export function useCreateQA() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createQA,
    onSuccess: () => {
      invalidateQA(qc);
      toast.success("问答已创建");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useUpdateQA() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateQA,
    onSuccess: () => {
      invalidateQA(qc);
      toast.success("问答已更新");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useDeleteQA() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteQA,
    onSuccess: () => {
      invalidateQA(qc);
      toast.success("问答已停用");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useRebuildEmbeddings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: rebuildEmbeddings,
    onSuccess: (data) => {
      invalidateQA(qc);
      qc.invalidateQueries({ queryKey: ["chat", "embedding-models"] });
      toast.success(`已重建 ${data.rebuilt} 条问答的向量`);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useActivateEmbeddingModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: activateEmbeddingModel,
    onSuccess: (data) => {
      invalidateQA(qc);
      qc.invalidateQueries({ queryKey: ["chat", "embedding-models"] });
      toast.success(`已切换向量模型，重建 ${data.rebuilt} 条向量`);
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
