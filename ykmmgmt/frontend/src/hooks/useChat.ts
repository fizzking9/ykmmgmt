import { apiFetch } from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// ── Types ───────────────────────────────────────────────────────────────────

export interface AskResponse {
  answer: string;
  session_id: string;
  matched_question: string | null;
  matched_variant_index: number | null;
  similarity_score: number | null;
  matched: boolean;
}

export interface ChatSession {
  id: string;
  created_at: string;
  last_active_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  matched_qa_id: string | null;
  matched_variant_index: number | null;
  similarity_score: number | null;
  created_at: string;
}

export interface ChatMessagePage {
  items: ChatMessage[];
  total: number;
  page: number;
  size: number;
}

// ── API helpers ──────────────────────────────────────────────────────────────

async function errDetail(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({ detail: fallback }));
  return typeof err.detail === "string" ? err.detail : fallback;
}

async function askChat(message: string, sessionId: string | null): Promise<AskResponse> {
  const res = await apiFetch("/api/chat/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await errDetail(res, "提问失败"));
  return res.json();
}

async function fetchSessions(): Promise<ChatSession[]> {
  const res = await apiFetch("/api/chat/sessions");
  if (!res.ok) throw new Error(await errDetail(res, "获取会话列表失败"));
  return res.json();
}

async function createSession(): Promise<ChatSession> {
  const res = await apiFetch("/api/chat/sessions", { method: "POST" });
  if (!res.ok) throw new Error(await errDetail(res, "新建会话失败"));
  return res.json();
}

async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}/messages?size=200`);
  if (!res.ok) throw new Error(await errDetail(res, "获取消息历史失败"));
  const page: ChatMessagePage = await res.json();
  return page.items;
}

async function deleteSession(sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await errDetail(res, "删除会话失败"));
}

async function fetchSuggestions(): Promise<string[]> {
  const res = await apiFetch("/api/chat/suggestions");
  if (!res.ok) throw new Error(await errDetail(res, "获取推荐问题失败"));
  return res.json();
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useAskChat() {
  return useMutation({ mutationFn: ({ message, sessionId }: { message: string; sessionId: string | null }) => askChat(message, sessionId) });
}

export function useChatSuggestions() {
  return useQuery({
    queryKey: ["chat", "suggestions"],
    queryFn: fetchSuggestions,
    staleTime: 5 * 60_000,
  });
}

export function useChatSessions(enabled = true) {
  return useQuery({
    queryKey: ["chat", "sessions"],
    queryFn: fetchSessions,
    enabled,
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ["chat", "messages", sessionId],
    queryFn: () => fetchMessages(sessionId!),
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat", "sessions"] }),
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSession,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["chat", "sessions"] });
      queryClient.removeQueries({ queryKey: ["chat", "messages", id] });
    },
  });
}
