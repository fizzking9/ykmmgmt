import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { UploadProvider } from "@/contexts/UploadContext";
import { AuthProvider } from "@/contexts/AuthContext";
import App from "@/App";

const ADMIN_PROFILE = { id: 1, username: "admin", role: "admin" };

const ANALYSIS_PAYLOAD = {
  sn: "SN123",
  range: "all",
  limit: 100,
  profile: {
    sn: "SN123",
    fields: [{ label: "设备类型", value: "洗衣机" }],
    counts: [{ source: "service_order", source_label: "服务工单列表", count: 1 }],
    total: 1,
  },
  timeline: [
    {
      source: "service_order",
      source_label: "服务工单列表",
      time: "2026-09-11 16:00:20",
      title: "工单 GD001",
      summary: "维修·已完成",
      amount: null,
      fields: [{ label: "状态", value: "已完成" }],
    },
  ],
};

function mockFetch(analysis: unknown = ANALYSIS_PAYLOAD) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
    const url = typeof input === "string" ? input : String(input);
    let body: unknown = [];
    if (url.includes("/api/auth/me")) {
      return Promise.resolve(
        new Response(JSON.stringify(ADMIN_PROFILE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (url.includes("/api/device-analysis/profile")) {
      return Promise.resolve(
        new Response(JSON.stringify(analysis), {
          status: 200,
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
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderApp() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("设备分析 entry + dialog", () => {
  it("shows the 设备分析 tag and opens the dialog with its controls", async () => {
    mockFetch();
    renderApp();

    const tag = await screen.findByRole("button", { name: /设备分析/ });
    fireEvent.click(tag);

    expect(await screen.findByText("设备行为分析")).toBeInTheDocument();
    // time-frame + max-records defaults and the SN search box
    expect(screen.getByText("所有")).toBeInTheDocument();
    expect(screen.getByText("100 条")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("输入设备 SN")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /查询/ })).toBeInTheDocument();
  });

  it("searches an SN and renders the profile + timeline", async () => {
    mockFetch();
    renderApp();

    fireEvent.click(await screen.findByRole("button", { name: /设备分析/ }));
    const input = await screen.findByPlaceholderText("输入设备 SN");
    fireEvent.change(input, { target: { value: "SN123" } });
    fireEvent.click(screen.getByRole("button", { name: /查询/ }));

    expect(await screen.findByText(/设备档案/)).toBeInTheDocument();
    expect(await screen.findByText("工单 GD001")).toBeInTheDocument();
    expect(screen.getByText("2026-09-11 16:00:20")).toBeInTheDocument();
    expect(screen.getAllByText(/服务工单列表/).length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/device-analysis/profile?sn=SN123"),
        expect.anything(),
      );
    });
  });
});
