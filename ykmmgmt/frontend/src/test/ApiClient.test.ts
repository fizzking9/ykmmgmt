import { describe, it, expect, vi, afterEach } from "vitest";
import { apiFetch } from "@/lib/api";

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(async () => {
  vi.restoreAllMocks();
  // apiFetch's single-flight refresh promise resets on a setTimeout(0) —
  // let it clear so state never leaks between tests
  await new Promise((resolve) => setTimeout(resolve, 10));
});

describe("apiFetch — silent refresh on 401", () => {
  it("retries the original request after a successful refresh", async () => {
    const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      calls.push(url);
      if (url === "/api/views") {
        // First call 401, retry succeeds
        if (calls.filter((u) => u === "/api/views").length === 1) {
          return jsonResponse({ detail: "未登录" }, 401);
        }
        return jsonResponse([{ id: "v1" }]);
      }
      if (url === "/api/auth/refresh") {
        return jsonResponse({ id: 1, username: "admin", role: "admin" });
      }
      return jsonResponse([]);
    });

    const res = await apiFetch("/api/views");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual([{ id: "v1" }]);
    // original → refresh → retry
    expect(calls).toEqual(["/api/views", "/api/auth/refresh", "/api/views"]);
  });

  it("dispatches auth:expired when the refresh also fails", async () => {
    const expiredListener = vi.fn();
    window.addEventListener("auth:expired", expiredListener);

    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      if (url === "/api/auth/refresh") {
        return jsonResponse({ detail: "未登录" }, 401);
      }
      return jsonResponse({ detail: "未登录" }, 401);
    });

    const res = await apiFetch("/api/views");
    expect(res.status).toBe(401);
    expect(expiredListener).toHaveBeenCalled();

    window.removeEventListener("auth:expired", expiredListener);
  });

  it("does not attempt a refresh for auth endpoints themselves", async () => {
    const calls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      calls.push(url);
      return jsonResponse({ detail: "用户名或密码错误" }, 401);
    });

    const res = await apiFetch("/api/auth/login", { method: "POST" });
    expect(res.status).toBe(401);
    expect(calls).toEqual(["/api/auth/login"]);
  });

  it("sends credentials with every request", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((_input: URL | RequestInfo, init?: RequestInit) => {
        expect(init?.credentials).toBe("include");
        return jsonResponse([]);
      });

    await apiFetch("/api/tables");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
