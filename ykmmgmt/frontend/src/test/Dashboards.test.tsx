import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within, renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import DashboardsListPage from "@/pages/DashboardsListPage";
import { computeAggregation } from "@/hooks/useDashboards";
import { TextTileMarkdown } from "@/components/dashboard/TextTileMarkdown";
import {
  DashboardBuilderProvider,
  useDashboardBuilderContext,
} from "@/contexts/DashboardBuilderContext";

// ── Fixtures ───────────────────────────────────────────────────────────────

const DASH_1 = {
  id: "dash-1",
  name: "运营总览",
  description: "核心指标",
  tile_count: 3,
  created_at: "2026-08-01T10:00:00",
  updated_at: "2026-08-01T10:00:00",
};

const DASH_2 = {
  id: "dash-2",
  name: "退款监控",
  description: null,
  tile_count: 1,
  created_at: "2026-08-02T10:00:00",
  updated_at: "2026-08-02T10:00:00",
};

const refetchListMock = vi.fn();
const updateMutateMock = vi.fn();
const deleteMutateMock = vi.fn();

// ── Hook mocks (keep pure helpers like computeAggregation real) ────────────

vi.mock("@/hooks/useDashboards", async () => {
  const actual =
    await vi.importActual<typeof import("@/hooks/useDashboards")>("@/hooks/useDashboards");
  return {
    ...actual,
    useDashboards: () => ({
      data: [DASH_1, DASH_2],
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchListMock,
      isRefetching: false,
    }),
    useUpdateDashboard: () => ({
      mutate: updateMutateMock,
      isPending: false,
    }),
    useDeleteDashboard: () => ({
      mutate: deleteMutateMock,
      isPending: false,
    }),
  };
});

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderPage() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/dashboards"]}>
        <DashboardBuilderProvider>
          <Routes>
            <Route path="/dashboards" element={<DashboardsListPage />} />
            <Route path="/dashboards/builder" element={<div>新建探针</div>} />
            <Route path="/dashboards/builder/:id" element={<div>编辑探针</div>} />
            <Route path="/dashboards/:id" element={<div>查看探针</div>} />
          </Routes>
        </DashboardBuilderProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── List page tests ─────────────────────────────────────────────────────────

describe("DashboardsListPage", () => {
  it("renders the page title and create button", () => {
    renderPage();
    expect(screen.getByText("仪表盘")).toBeInTheDocument();
    expect(screen.getByText("新建仪表盘")).toBeInTheDocument();
  });

  it("renders rows with tile count and four actions", () => {
    renderPage();
    expect(screen.getByText("运营总览")).toBeInTheDocument();
    expect(screen.getByText("退款监控")).toBeInTheDocument();
    expect(screen.getByText("核心指标")).toBeInTheDocument();
    // Tile counts
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    // Sortable time columns
    expect(screen.getByText("创建时间")).toBeInTheDocument();
    expect(screen.getByText("更新时间")).toBeInTheDocument();
    // Four actions per row
    expect(screen.getAllByText("查看")).toHaveLength(2);
    expect(screen.getAllByText("编辑")).toHaveLength(2);
    expect(screen.getAllByText("重命名")).toHaveLength(2);
    expect(screen.getAllByText("删除")).toHaveLength(2);
  });

  it("navigates to view / edit / create entry points", () => {
    renderPage();
    fireEvent.click(screen.getByText("新建仪表盘"));
    expect(screen.getByText("新建探针")).toBeInTheDocument();
  });

  it("sorts rows by updated time ascending on header click", () => {
    renderPage();
    fireEvent.click(screen.getByText("更新时间"));
    const rows = screen.getAllByRole("row").slice(1); // skip header
    // asc: 运营总览 (08-01) before 退款监控 (08-02)
    expect(within(rows[0]).getByText("运营总览")).toBeInTheDocument();
    expect(within(rows[1]).getByText("退款监控")).toBeInTheDocument();
  });

  it("rename dialog updates the dashboard name", () => {
    renderPage();
    fireEvent.click(screen.getAllByText("重命名")[0]);
    expect(screen.getByText("重命名仪表盘")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("输入新名称");
    fireEvent.change(input, { target: { value: "运营总览 V2" } });
    fireEvent.click(screen.getByText("确定"));
    expect(updateMutateMock).toHaveBeenCalledWith(
      { id: "dash-1", name: "运营总览 V2" },
      expect.anything(),
    );
  });

  it("delete requires confirmation and passes the id on confirm", () => {
    renderPage();
    const deleteButtons = screen.getAllByText("删除");
    fireEvent.click(deleteButtons[0]);
    expect(screen.getByText(/确定要删除仪表盘「运营总览」吗？/)).toBeInTheDocument();

    // Cancel closes the dialog without deleting
    fireEvent.click(screen.getByText("取消"));
    expect(screen.queryByText(/此操作不可撤销/)).not.toBeInTheDocument();
    expect(deleteMutateMock).not.toHaveBeenCalled();

    // Confirm calls the delete mutation with the id
    fireEvent.click(deleteButtons[0]);
    fireEvent.click(screen.getByText("确定"));
    expect(deleteMutateMock).toHaveBeenCalledWith("dash-1", expect.anything());
  });
});

// ── KPI client-side aggregation tests ───────────────────────────────────────

describe("computeAggregation", () => {
  const rows = [{ amount: 10 }, { amount: "20.5" }, { amount: null }, { amount: 5 }] as Record<
    string,
    unknown
  >[];

  it("computes SUM skipping null/non-numeric values", () => {
    expect(computeAggregation(rows, "amount", "SUM")).toBe(35.5);
  });

  it("computes AVG over numeric values only", () => {
    expect(computeAggregation(rows, "amount", "AVG")).toBeCloseTo(11.833, 2);
  });

  it("computes COUNT over all rows", () => {
    expect(computeAggregation(rows, "amount", "COUNT")).toBe(4);
  });

  it("computes MIN and MAX", () => {
    expect(computeAggregation(rows, "amount", "MIN")).toBe(5);
    expect(computeAggregation(rows, "amount", "MAX")).toBe(20.5);
  });

  it("returns null when no numeric values exist", () => {
    expect(computeAggregation([{ s: "abc" }], "s", "SUM")).toBeNull();
  });
});

// ── Text tile markdown tests ────────────────────────────────────────────────

describe("TextTileMarkdown", () => {
  it("renders headings, bold text and bullet lists", () => {
    render(<TextTileMarkdown content={"# 总览\n**重点**指标\n- 项目一\n- 项目二"} />);
    expect(screen.getByText("总览").tagName).toBe("H1");
    expect(screen.getByText("重点").tagName).toBe("STRONG");
    expect(screen.getByText("项目一")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows a placeholder for empty content", () => {
    render(<TextTileMarkdown content="" />);
    expect(screen.getByText("（空文本）")).toBeInTheDocument();
  });
});

// ── Dashboard builder context tests ─────────────────────────────────────────

function builderWrapper({ children }: { children: React.ReactNode }) {
  return <DashboardBuilderProvider>{children}</DashboardBuilderProvider>;
}

describe("DashboardBuilderContext", () => {
  it("adds tiles with per-type default sizes and stacks them vertically", () => {
    const { result } = renderHook(() => useDashboardBuilderContext(), {
      wrapper: builderWrapper,
    });
    act(() => {
      result.current.addTile("text", { content: "## 标题" });
      result.current.addTile("visualization", { visualization_id: "viz-1" });
      result.current.addTile("kpi_card", {
        config: { view_id: "v1", value_column: "amount", label: "总额", agg: "SUM" },
      });
    });

    const tiles = result.current.state.tiles;
    expect(tiles).toHaveLength(3);
    expect(tiles[0]).toMatchObject({ tile_type: "text", w: 6, h: 2, y: 0 });
    expect(tiles[1]).toMatchObject({ tile_type: "visualization", w: 6, h: 4, y: 2 });
    expect(tiles[2]).toMatchObject({ tile_type: "kpi_card", w: 3, h: 2, y: 6 });
  });

  it("applies grid geometry back onto tiles and removes tiles", () => {
    const { result } = renderHook(() => useDashboardBuilderContext(), {
      wrapper: builderWrapper,
    });
    act(() => {
      result.current.addTile("text");
    });
    const key = result.current.state.tiles[0].i;

    act(() => {
      result.current.applyLayout([{ i: key, x: 3, y: 5, w: 9, h: 6 }]);
    });
    expect(result.current.state.tiles[0]).toMatchObject({ x: 3, y: 5, w: 9, h: 6 });

    act(() => {
      result.current.removeTile(key);
    });
    expect(result.current.state.tiles).toHaveLength(0);
  });

  it("loads an existing dashboard into builder state", () => {
    const { result } = renderHook(() => useDashboardBuilderContext(), {
      wrapper: builderWrapper,
    });
    act(() => {
      result.current.loadDashboard({
        id: "dash-9",
        name: "已有仪表盘",
        description: "描述",
        layout_json: [{ i: "t1", tile_type: "text", x: 0, y: 0, w: 6, h: 2, content: "你好" }],
      });
    });
    expect(result.current.state.editingId).toBe("dash-9");
    expect(result.current.state.name).toBe("已有仪表盘");
    expect(result.current.state.tiles[0].content).toBe("你好");
  });
});
