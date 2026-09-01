import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CurrentUser } from "@/contexts/AuthContext";

async function errDetail(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({ detail: fallback }));
  return err.detail || fallback;
}

export interface UpdateProfileInput {
  /** Confirmation of the current password — required only when
   *  changing the password; username changes need no re-authentication */
  current_password?: string;
  /** New username (omit to keep the current one) */
  username?: string;
  /** New password (omit to keep the current one) */
  new_password?: string;
}

async function updateProfile(data: UpdateProfileInput): Promise<CurrentUser> {
  const res = await apiFetch("/api/auth/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await errDetail(res, "更新个人信息失败"));
  return res.json();
}

/** Self-service profile update — the caller is responsible for syncing the
 *  returned profile into AuthContext (setUser) so the sidebar stays fresh. */
export function useUpdateProfile() {
  return useMutation({ mutationFn: updateProfile });
}
