/* eslint-disable react-refresh/only-export-components */
/**
 * AuthContext — current user state shared across the app.
 *
 * Sits above the router (see main.tsx). On mount it resolves the session
 * via GET /api/auth/me; login()/logout() manage cookies server-side and
 * update local state. Listens for the "auth:expired" event dispatched by
 * the API client when a silent refresh fails (forces re-login).
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Role = "root" | "admin" | "user";

export interface CurrentUser {
  id: number;
  username: string;
  role: Role;
}

export const ROLE_LABELS: Record<Role, string> = {
  root: "超级管理员",
  admin: "管理员",
  user: "用户",
};

interface AuthContextValue {
  user: CurrentUser | null;
  /** True until the initial /api/auth/me check completes */
  loading: boolean;
  isAdmin: boolean;
  isRoot: boolean;
  login: (username: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  setUser: (user: CurrentUser | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(): Promise<CurrentUser | null> {
  const res = await fetch("/api/auth/me", { credentials: "include" });
  if (!res.ok) return null;
  return res.json();
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The API client dispatches this when a silent refresh fails
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<CurrentUser> => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "登录失败" }));
      throw new Error(err.detail || "登录失败");
    }
    const profile: CurrentUser = await res.json();
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } finally {
      setUser(null);
    }
  }, []);

  const isAdmin = user?.role === "admin" || user?.role === "root";
  const isRoot = user?.role === "root";

  return (
    <AuthContext.Provider value={{ user, loading, isAdmin, isRoot, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
