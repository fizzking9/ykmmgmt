import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import QAManagementPage from "@/pages/QAManagementPage";

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

const QA_PAGE = {
  items: [
    {
      id: "a1",
      question: "如何导入数据？",
      question_variants: ["怎么上传？", "从哪导？"],
      answer: "点击数据导入上传 CSV",
      category: "数据导入",
      is_active: true,
      has_embeddings: true,
      embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
      needs_rebuild: false,
      variant_count: 2,
      created_at: "2026-09-18T10:00:00Z",
      updated_at: "2026-09-18T10:00:00Z",
    },
    {
      id: "b2",
      question: "怎么新建可视化？",
      question_variants: [],
      answer: "可视化 → 新建",
      category: null,
      is_active: false,
      has_embeddings: true,
      embedding_model: "BAAI/bge-m3",
      needs_rebuild: true,
      variant_count: 0,
      created_at: "2026-09-17T09:00:00Z",
      updated_at: "2026-09-17T09:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  size: 20,
};

const EMBEDDING_MODELS = {
  items: [
    {
      name: "paraphrase-multilingual-MiniLM-L12-v2",
      label: "MiniLM-L12 v2（多语言·轻量）",
      dims: 384,
      note: "默认项；384 维",
    },
    { name: "BAAI/bge-m3", label: "BGE M3（多语言·长文）", dims: 1024, note: "体积较大" },
  ],
  active_model: "paraphrase-multilingual-MiniLM-L12-v2",
  active_label: "MiniLM-L12 v2（多语言·轻量）",
  threshold: 0.79,
  needs_rebuild: 1,
};

function mockRole(role: "admin" | "user") {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/api/auth/me")) {
      return jsonResponse({ id: 1, username: "actor", role });
    }
    if (url.includes("/api/chat/categories")) return jsonResponse(["数据导入"]);
    if (url.includes("/api/chat/embedding-models")) return jsonResponse(EMBEDDING_MODELS);
    if (url.includes("/api/chat/qa-pairs")) return jsonResponse(QA_PAGE);
    return jsonResponse([]);
  });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/admin/qa-pairs"]}>
          <QAManagementPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("QAManagementPage", () => {
  it("renders rows with the +N variant badge and per-row actions", async () => {
    mockRole("admin");
    renderPage();

    expect(await screen.findByText("如何导入数据？")).toBeInTheDocument();
    // First row has two variants → a "+2" badge; second has none (no badge)
    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.queryByText("+0")).not.toBeInTheDocument();
    // Status badges reflect is_active
    expect(screen.getByText("启用")).toBeInTheDocument();
    expect(screen.getByText("停用")).toBeInTheDocument();
    // Actions present
    expect(screen.getAllByText("编辑").length).toBe(2);
  });

  it("opens the create dialog from the toolbar button", async () => {
    mockRole("admin");
    renderPage();
    fireEvent.click(await screen.findByTestId("create-qa-button"));
    expect(await screen.findByText("标准问题")).toBeInTheDocument();
    expect(screen.getByText("添加相似问法")).toBeInTheDocument();
  });

  it("shows the active encoder and flags rows whose vectors came from another one", async () => {
    mockRole("admin");
    renderPage();

    expect(await screen.findByText("向量模型")).toBeInTheDocument();
    expect(screen.getByText("MiniLM-L12 v2（多语言·轻量）")).toBeInTheDocument();
    // 待重建：行内徒章 + 顶部汇总
    expect(screen.getByText("待重建")).toBeInTheDocument();
    expect(screen.getByText("1 条待重建")).toBeInTheDocument();
    expect(
      screen.getByText(/当前生效：MiniLM-L12 v2（多语言·轻量）；阈值 0\.79/),
    ).toBeInTheDocument();
    // 选中项与生效项一致时不显示切换按钮
    expect(screen.queryByText("切换并重建向量")).not.toBeInTheDocument();
  });

  it("blocks non-admin users", async () => {
    mockRole("user");
    renderPage();
    expect(await screen.findByText("无权访问此页面")).toBeInTheDocument();
  });
});
