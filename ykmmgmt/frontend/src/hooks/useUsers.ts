import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import type { Role } from "@/contexts/AuthContext";

export interface UserItem {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

async function errDetail(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({ detail: fallback }));
  return err.detail || fallback;
}

async function fetchUsers(): Promise<UserItem[]> {
  const res = await apiFetch("/api/users");
  if (!res.ok) throw new Error(await errDetail(res, "获取用户列表失败"));
  return res.json();
}

export function useUsers(enabled: boolean) {
  return useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
    enabled,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { username: string; password: string; role: "admin" | "user" }) => {
      const res = await apiFetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await errDetail(res, "创建用户失败"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("用户创建成功");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number;
      role?: "admin" | "user";
      password?: string;
    }) => {
      const res = await apiFetch(`/api/users/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await errDetail(res, "更新用户失败"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("用户已更新");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}

export function useUpdateUserStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await apiFetch(`/api/users/${id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active }),
      });
      if (!res.ok) throw new Error(await errDetail(res, "更新用户状态失败"));
      return res.json();
    },
    onSuccess: (user: UserItem) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success(user.is_active ? "用户已启用" : "用户已停用");
    },
    onError: (err: Error) => toast.error(err.message),
  });
}
