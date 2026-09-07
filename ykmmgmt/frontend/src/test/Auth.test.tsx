import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { UploadProvider } from "@/contexts/UploadContext";
import App from "@/App";

// ── Helpers ────────────────────────────────────────────────────────────────

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ── AuthContext: login / logout ────────────────────────────────────────────

function AuthProbe() {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="username">{user?.username ?? "anonymous"}</span>
      <button
        onClick={() => login("admin", "secret123").catch(() => undefined)}
        data-testid="login"
      >
        login
      </button>
      <button onClick={() => logout()} data-testid="logout">
        logout
      </button>
    </div>
  );
}

describe("AuthContext — login/logout flow", () => {
  it("resolves the current user from /api/auth/me on mount", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ id: 7, username: "alice", role: "user" }),
    );

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("username")).toHaveTextContent("alice");
  });

  it("treats a 401 /me as anonymous", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse({ detail: "未登录" }, 401));

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("username")).toHaveTextContent("anonymous");
  });

  it("login stores the profile returned by the API", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/api/auth/login")) {
        return jsonResponse({ id: 3, username: "bob", role: "admin" });
      }
      // /me on mount — anonymous
      return jsonResponse({ detail: "未登录" }, 401);
    });

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("username")).toHaveTextContent("anonymous");
    fireEvent.click(screen.getByTestId("login"));
    expect(await screen.findByTestId("username")).toHaveTextContent("bob");
  });

  it("logout clears the user", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/api/auth/logout")) {
        return jsonResponse({ detail: "已退出登录" });
      }
      return jsonResponse({ id: 9, username: "carol", role: "root" });
    });

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <AuthProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("username")).toHaveTextContent("carol");
    fireEvent.click(screen.getByTestId("logout"));
    await waitFor(() => {
      expect(screen.getByTestId("username")).toHaveTextContent("anonymous");
    });
  });
});

// ── Route guards ───────────────────────────────────────────────────────────

describe("Route guards", () => {
  function renderApp(initialRoute: string, meProfile: object | null) {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/api/auth/me")) {
        return meProfile ? jsonResponse(meProfile) : jsonResponse({ detail: "未登录" }, 401);
      }
      return jsonResponse([]);
    });

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <MemoryRouter initialEntries={[initialRoute]}>
            <UploadProvider>
              <App />
            </UploadProvider>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
  }

  it("redirects unauthenticated users to /login", async () => {
    renderApp("/upload", null);
    expect(await screen.findByText("请登录以继续使用")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /登录/ })).toBeInTheDocument();
  });

  it("keeps authenticated users on the requested page", async () => {
    renderApp("/upload", { id: 1, username: "admin", role: "admin" });
    expect(await screen.findByText("数据导入")).toBeInTheDocument();
    expect(screen.queryByText("请登录以继续使用")).not.toBeInTheDocument();
  });
});

// ── Role-based sidebar ─────────────────────────────────────────────────────

describe("Role-based sidebar visibility", () => {
  function renderAppWithRole(role: "admin" | "user") {
    vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/api/auth/me")) {
        return jsonResponse({ id: 1, username: "someone", role });
      }
      // Sidebar fetches the dashboard list — must be an array
      if (url.includes("/api/dashboards")) {
        return jsonResponse([]);
      }
      return jsonResponse([]);
    });

    render(
      <QueryClientProvider client={createQueryClient()}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/"]}>
            <UploadProvider>
              <App />
            </UploadProvider>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
  }

  async function expandGroup(title: string) {
    fireEvent.click(await screen.findByText(title));
  }

  it("admin sees admin-only nav items", async () => {
    renderAppWithRole("admin");
    await expandGroup("数据管理");
    expect(screen.getByText("数据导入")).toBeInTheDocument();
    expect(screen.getByText("数据表管理")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
  });

  it("L3 user sees no admin-only nav items", async () => {
    renderAppWithRole("user");
    await expandGroup("数据管理");
    expect(screen.getByText("数据浏览")).toBeInTheDocument();
    expect(screen.queryByText("数据导入")).not.toBeInTheDocument();
    expect(screen.queryByText("数据表管理")).not.toBeInTheDocument();
    expect(screen.queryByText("新建数据表")).not.toBeInTheDocument();
    expect(screen.queryByText("用户管理")).not.toBeInTheDocument();
  });

  it("L3 user sees no builder links in the analysis group", async () => {
    renderAppWithRole("user");
    await expandGroup("数据分析");
    expect(screen.getByText("数据视图")).toBeInTheDocument();
    expect(screen.queryByText("视图创建")).not.toBeInTheDocument();
    expect(screen.queryByText("可视化构建")).not.toBeInTheDocument();
    expect(screen.queryByText("看板创建")).not.toBeInTheDocument();
  });

  it("shows the current username and role badge with a logout action", async () => {
    renderAppWithRole("admin");
    expect(await screen.findByText("someone")).toBeInTheDocument();
    expect(screen.getByText("管理员")).toBeInTheDocument();
    expect(screen.getByText("退出登录")).toBeInTheDocument();
  });
});
