import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { UploadProvider } from "@/contexts/UploadContext";
import { AuthProvider } from "@/contexts/AuthContext";
import App from "@/App";

// Default authenticated admin — individual tests override with mockMe()
const ADMIN_PROFILE = { id: 1, username: "admin", role: "admin" };

function mockMe(profile: object | null = ADMIN_PROFILE) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
    const url = typeof input === "string" ? input : String(input);
    let body: unknown = [];
    if (url.includes("/api/auth/me")) {
      return Promise.resolve(
        new Response(profile ? JSON.stringify(profile) : "null", {
          status: profile ? 200 : 401,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (url.includes("/api/imports")) {
      body = { items: [], total: 0, page: 1, page_size: 20 };
    }
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function renderWithRouter(initialRoute = "/") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App Shell — layout and routing", () => {
  it("renders the app title in the sidebar", async () => {
    mockMe();
    renderWithRouter("/");
    expect(await screen.findByText("云客猫管理平台")).toBeInTheDocument();
  });

  it("renders sidebar navigation groups", async () => {
    mockMe();
    renderWithRouter("/");
    expect(await screen.findByText("数据管理")).toBeInTheDocument();
  });

  it("renders the home page at /", async () => {
    mockMe();
    const { container } = renderWithRouter("/");
    // Wait past the auth-loading spinner
    await screen.findByText("云客猫管理平台");
    // Home page renders an empty div — the main content area should exist
    expect(container.querySelector("main")).toBeInTheDocument();
  });

  it("renders the data import hub at /upload with its method tabs", async () => {
    mockMe();
    renderWithRouter("/upload");
    expect(await screen.findByText("数据导入")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "上传文件" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "数据抓取" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导入历史" })).toBeInTheDocument();
  });

  it("switches to the scrape tab and shows the coming-soon placeholder", async () => {
    mockMe();
    renderWithRouter("/upload");
    await screen.findByRole("button", { name: "数据抓取" });
    fireEvent.click(screen.getByRole("button", { name: "数据抓取" }));
    expect(screen.getByText("功能开发中")).toBeInTheDocument();
  });

  it("switches to the import history tab and loads the history panel", async () => {
    mockMe();
    renderWithRouter("/upload");
    fireEvent.click(await screen.findByRole("button", { name: "导入历史" }));
    expect(await screen.findByText("暂无导入记录")).toBeInTheDocument();
  });

  it("renders the data browser nav item in sidebar", async () => {
    mockMe();
    const { container } = renderWithRouter("/");
    // Expand the collapsible sidebar group to reveal links
    const trigger = await screen.findByText("数据管理");
    fireEvent.click(trigger);
    expect(screen.getByText("数据浏览")).toBeInTheDocument();
    expect(container.querySelector("main")).toBeInTheDocument();
  });
});
