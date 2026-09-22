import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatWidget } from "@/components/chat/ChatWidget";

// ── Fetch mock ─────────────────────────────────────────────────────────────

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

let askPayloads: unknown[] = [];

beforeEach(() => {
  askPayloads = [];
  localStorage.clear();
  vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/api/chat/suggestions")) {
      return jsonResponse(["如何导入数据？", "怎么新建可视化？"]);
    }
    if (url.includes("/api/chat/ask")) {
      askPayloads.push(JSON.parse(String(init?.body ?? "{}")));
      return jsonResponse({
        answer: "点击侧边栏的数据导入",
        session_id: "sess-1",
        matched_question: "如何导入数据？",
        matched_variant_index: 0,
        similarity_score: 0.91,
        matched: true,
      });
    }
    if (url.includes("/messages")) {
      return jsonResponse({ items: [], total: 0, page: 1, size: 200 });
    }
    return jsonResponse([]);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderWidget() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatWidget />
    </QueryClientProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("ChatWidget", () => {
  it("renders the launcher and opens the panel on click", async () => {
    renderWidget();
    const launcher = screen.getByRole("button", { name: "打开智能问答" });
    fireEvent.click(launcher);
    // Panel opens — welcome copy + suggested questions become visible
    expect(await screen.findByText("您好！我是智能问答助手。")).toBeInTheDocument();
    expect(await screen.findByText("如何导入数据？")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭智能问答" })).toBeInTheDocument();
  });

  it("sends a message and renders the assistant answer", async () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: "打开智能问答" }));

    const input = await screen.findByLabelText("消息输入框");
    fireEvent.change(input, { target: { value: "如何导入数据？" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("点击侧边栏的数据导入")).toBeInTheDocument();
    await waitFor(() => expect(askPayloads.length).toBe(1));
    expect(askPayloads[0]).toMatchObject({ message: "如何导入数据？", session_id: null });
  });

  it("clicking a suggested question sends it", async () => {
    renderWidget();
    fireEvent.click(screen.getByRole("button", { name: "打开智能问答" }));
    fireEvent.click(await screen.findByText("怎么新建可视化？"));
    await waitFor(() => expect(askPayloads.length).toBe(1));
    expect(askPayloads[0]).toMatchObject({ message: "怎么新建可视化？" });
  });
});
