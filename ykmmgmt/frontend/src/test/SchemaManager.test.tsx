import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SchemaTablesPage from "@/pages/SchemaTablesPage";
import SchemaCreateTablePage from "@/pages/SchemaCreateTablePage";
import { EditTableDialog } from "@/components/schema/EditTableDialog";
import { DeleteTableDialog } from "@/components/schema/DeleteTableDialog";

// ── Fixtures ───────────────────────────────────────────────────────────────

const COLUMN_TYPES = [
  { key: "String", label: "字符串", has_length: true, default_length: 255 },
  { key: "Text", label: "长文本", has_length: false, default_length: null },
  { key: "Integer", label: "整数", has_length: false, default_length: null },
  { key: "Numeric", label: "小数", has_length: false, default_length: null },
  { key: "DateTime", label: "日期时间", has_length: false, default_length: null },
];

const TABLES = [
  {
    name: "refund_orders",
    chinese_name: "退费单",
    column_count: 12,
    row_count: 100,
    read_only: true,
    dynamic: false,
  },
  {
    name: "customer_orders",
    chinese_name: "客户订单",
    column_count: 4,
    row_count: 3,
    read_only: false,
    dynamic: true,
  },
];

const INFERRED = {
  columns: [
    {
      name: "order_no",
      label: "订单号",
      type: "String",
      length: 50,
      nullable: true,
      unique: false,
    },
    { name: "amount", label: "金额", type: "Numeric", length: null, nullable: true, unique: false },
    {
      name: "order_date",
      label: "下单日期",
      type: "Date",
      length: null,
      nullable: true,
      unique: false,
    },
  ],
  row_count: 3,
  suggested_table_name: "orders",
};

// ── Mock state ─────────────────────────────────────────────────────────────

const createMutateMock = vi.fn();
const inferMutateMock = vi.fn();
const addColumnMutateMock = vi.fn();
const deleteMutateMock = vi.fn();
const modifyMutateMock = vi.fn();
const renameMutateMock = vi.fn();

const FK_OPTIONS = [
  {
    table: "departments",
    chinese_name: "部门",
    columns: [
      { name: "dept_id", label: "部门编号", type: "INTEGER", primary_key: true, unique: false },
    ],
  },
];

vi.mock("@/hooks/useSchema", async () => {
  return {
    useSchemaTables: () => ({ data: TABLES, isLoading: false, isError: false }),
    useSchemaTableDetail: () => ({
      data: {
        name: "customer_orders",
        chinese_name: "客户订单",
        read_only: false,
        dynamic: true,
        upsert_key: [],
        dedup_enabled: true,
        columns: [
          {
            name: "title",
            type: "VARCHAR(100)",
            nullable: false,
            primary_key: false,
            unique: false,
            foreign_key: null,
            label: "标题",
            description: null,
            default: null,
            internal: false,
          },
          {
            name: "id",
            type: "INTEGER",
            nullable: false,
            primary_key: true,
            unique: false,
            foreign_key: null,
            label: "主键ID",
            description: null,
            default: null,
            internal: true,
          },
        ],
        sample_rows: [],
      },
      isLoading: false,
    }),
    useColumnTypes: () => ({ data: COLUMN_TYPES, isLoading: false }),
    useFkOptions: () => ({ data: FK_OPTIONS, isLoading: false }),
    useTableDependencies: () => ({
      data: {
        views: [{ id: "v1", name: "订单视图" }],
        visualizations: [{ id: "z1", name: "订单图表" }],
        tables: [],
      },
      isLoading: false,
    }),
    useCreateTable: () => ({ mutate: createMutateMock, isPending: false }),
    useInferCsv: () => ({ mutate: inferMutateMock, isPending: false, data: null }),
    useAddColumn: () => ({ mutate: addColumnMutateMock, isPending: false }),
    useDropColumn: () => ({ mutate: vi.fn(), isPending: false }),
    useModifyColumn: () => ({ mutate: modifyMutateMock, isPending: false }),
    useRenameTable: () => ({ mutate: renameMutateMock, isPending: false }),
    useDeleteTable: () => ({ mutate: deleteMutateMock, isPending: false }),
  };
});

// Mock sonner toasts
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderWithProviders(ui: React.ReactElement, initialEntry = "/schema") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Table list ─────────────────────────────────────────────────────────────

describe("数据表列表页", () => {
  it("渲染所有数据表，预置业务表隐藏编辑/删除操作", () => {
    renderWithProviders(
      <Routes>
        <Route path="/schema" element={<SchemaTablesPage />} />
      </Routes>,
    );

    expect(screen.getByText("退费单")).toBeInTheDocument();
    expect(screen.getByText("客户订单")).toBeInTheDocument();
    expect(screen.getByText("预置业务表")).toBeInTheDocument();
    expect(screen.getByText("自建数据表")).toBeInTheDocument();

    // Read-only table: only 查看 action
    const readOnlyRow = screen.getByText("退费单").closest("tr")!;
    expect(readOnlyRow.textContent).toContain("查看");
    expect(readOnlyRow.textContent).not.toContain("编辑");
    expect(readOnlyRow.textContent).not.toContain("删除");

    // Dynamic table: all actions visible
    const dynamicRow = screen.getByText("客户订单").closest("tr")!;
    expect(dynamicRow.textContent).toContain("编辑");
    expect(dynamicRow.textContent).toContain("删除");
  });
});

// ── Create wizard: manual path ─────────────────────────────────────────────

describe("新建数据表（手动）", () => {
  it("填写表名与列定义后提交创建", () => {
    renderWithProviders(<SchemaCreateTablePage />, "/schema/create");

    fireEvent.change(screen.getByLabelText(/英文表名/), {
      target: { value: "test_orders" },
    });
    fireEvent.change(screen.getByLabelText(/中文显示名/), {
      target: { value: "测试订单" },
    });

    // First (only) column row
    fireEvent.change(screen.getByLabelText("第1列列名"), { target: { value: "title" } });
    fireEvent.change(screen.getByLabelText("第1列中文标签"), { target: { value: "标题" } });

    fireEvent.click(screen.getByRole("button", { name: /创建数据表/ }));

    expect(createMutateMock).toHaveBeenCalledTimes(1);
    const payload = createMutateMock.mock.calls[0][0];
    expect(payload.name).toBe("test_orders");
    expect(payload.display_name).toBe("测试订单");
    expect(payload.columns[0]).toMatchObject({
      name: "title",
      type: "String",
      length: 255,
      label: "标题",
    });
  });

  it("表名非法时禁用提交按钮", () => {
    renderWithProviders(<SchemaCreateTablePage />, "/schema/create");
    fireEvent.change(screen.getByLabelText(/英文表名/), { target: { value: "Bad-Name" } });
    fireEvent.change(screen.getByLabelText("第1列列名"), { target: { value: "title" } });
    expect(screen.getByRole("button", { name: /创建数据表/ })).toBeDisabled();
  });

  it("勾选主键后可空/唯一选项被锁定，且提交时主键列强制不可空", () => {
    renderWithProviders(<SchemaCreateTablePage />, "/schema/create");
    fireEvent.change(screen.getByLabelText(/英文表名/), { target: { value: "pk_table" } });
    fireEvent.change(screen.getByLabelText("第1列列名"), { target: { value: "code" } });

    // Nullable starts checked; marking the column as PK locks both flags
    const nullableBox = screen.getByLabelText("第1列允许为空");
    expect(nullableBox).toBeChecked();
    fireEvent.click(screen.getByLabelText("第1列设为主键"));

    expect(nullableBox).not.toBeChecked();
    expect(nullableBox).toBeDisabled();
    const uniqueBox = screen.getByLabelText("第1列唯一");
    expect(uniqueBox).toBeChecked();
    expect(uniqueBox).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /创建数据表/ }));
    const payload = createMutateMock.mock.calls[0][0];
    expect(payload.columns[0]).toMatchObject({
      name: "code",
      primary_key: true,
      nullable: false,
    });
  });
});

// ── Create wizard: CSV path ────────────────────────────────────────────────

describe("新建数据表（CSV 推断）", () => {
  it("上传真实 CSV 文件后渲染推断出的列结构", async () => {
    inferMutateMock.mockImplementation(
      (_file: File, opts: { onSuccess?: (d: unknown) => void }) => {
        // Simulate backend inference for the uploaded file
        opts.onSuccess?.(INFERRED);
      },
    );

    renderWithProviders(<SchemaCreateTablePage />, "/schema/create");

    // Switch to CSV mode
    fireEvent.click(screen.getByRole("button", { name: "CSV 导入推断" }));

    // Build a real File from CSV text with Chinese headers
    const csv = "订单号,金额,下单日期\nA001,199.50,2026-08-01\nA002,250.00,2026-08-02\n";
    const file = new File([csv], "orders.csv", { type: "text/csv" });
    const input = screen.getByLabelText("选择CSV文件");
    fireEvent.change(input, { target: { files: [file] } });

    // The uploaded file is passed to the inference mutation
    expect(inferMutateMock).toHaveBeenCalledTimes(1);
    const uploaded = inferMutateMock.mock.calls[0][0] as File;
    expect(uploaded.name).toBe("orders.csv");
    const uploadedText = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(uploaded);
    });
    expect(uploadedText).toBe(csv);

    // Inferred schema is rendered as editable rows
    await waitFor(() => {
      expect(screen.getByLabelText("第1列列名")).toHaveValue("order_no");
    });
    expect(screen.getByLabelText("第1列中文标签")).toHaveValue("订单号");
    expect(screen.getByLabelText("第2列中文标签")).toHaveValue("金额");
    expect(screen.getByLabelText("第3列中文标签")).toHaveValue("下单日期");
    // Suggested table name applied
    expect(screen.getByLabelText(/英文表名/)).toHaveValue("orders");
  });
});

// ── Edit dialog ────────────────────────────────────────────────────────────

describe("编辑表结构对话框", () => {
  it("渲染现有列并支持添加新列", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    // Existing business column editable; internal column hidden
    expect(screen.getByLabelText("修改列 title 的列名")).toHaveValue("title");
    expect(screen.queryByLabelText("修改列 id 的列名")).not.toBeInTheDocument();

    // Add a new column (with description + default)
    fireEvent.change(screen.getByLabelText("新列名"), { target: { value: "remark" } });
    fireEvent.change(screen.getByLabelText("新列中文标签"), { target: { value: "备注" } });
    fireEvent.change(screen.getByLabelText("新列描述"), { target: { value: "备注说明" } });
    fireEvent.change(screen.getByLabelText("新列默认值"), { target: { value: "无" } });
    fireEvent.click(screen.getByRole("button", { name: "添加列" }));

    expect(addColumnMutateMock).toHaveBeenCalledTimes(1);
    expect(addColumnMutateMock.mock.calls[0][0]).toMatchObject({
      name: "remark",
      type: "String",
      label: "备注",
      description: "备注说明",
      default: "无",
    });
  });

  it("支持改列名/标签/描述/可空，仅提交变更字段", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    const saveButton = screen.getByRole("button", { name: "保存修改" });
    expect(saveButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("修改列 title 的列名"), {
      target: { value: "title_new" },
    });
    fireEvent.change(screen.getByLabelText("修改列 title 的中文标签"), {
      target: { value: "新标题" },
    });
    fireEvent.change(screen.getByLabelText("修改列 title 的描述"), {
      target: { value: "标题说明" },
    });
    fireEvent.click(screen.getByLabelText("修改列 title 允许为空"));

    expect(saveButton).not.toBeDisabled();
    fireEvent.click(saveButton);

    expect(modifyMutateMock).toHaveBeenCalledTimes(1);
    expect(modifyMutateMock.mock.calls[0][0]).toMatchObject({
      column: "title",
      name: "title_new",
      label: "新标题",
      description: "标题说明",
      nullable: true,
    });
  });

  it("外键通过下拉选择目标表与目标列", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    const tableSelect = screen.getByLabelText("列 title 的外键目标表");
    fireEvent.change(tableSelect, { target: { value: "departments" } });

    // First eligible column is preselected
    expect(screen.getByLabelText("列 title 的外键目标列")).toHaveValue("dept_id");

    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    expect(modifyMutateMock.mock.calls[0][0]).toMatchObject({
      column: "title",
      foreign_key: "departments.dept_id",
    });
  });

  it("支持重命名表名与中文显示名", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    const renameButton = screen.getByRole("button", { name: "保存表设置" });
    // Seeded with current values → nothing to save yet
    expect(screen.getByLabelText("修改表名")).toHaveValue("customer_orders");
    expect(screen.getByLabelText("修改显示名")).toHaveValue("客户订单");
    expect(renameButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("修改表名"), {
      target: { value: "customer_orders_v2" },
    });
    fireEvent.change(screen.getByLabelText("修改显示名"), {
      target: { value: "客户订单二" },
    });
    expect(renameButton).not.toBeDisabled();
    fireEvent.click(renameButton);

    expect(renameMutateMock).toHaveBeenCalledTimes(1);
    expect(renameMutateMock.mock.calls[0][0]).toMatchObject({
      name: "customer_orders_v2",
      display_name: "客户订单二",
    });
  });

  it("支持配置 Upsert 键与去重开关", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    // Select the title column as the upsert key
    fireEvent.click(screen.getByLabelText("Upsert键列title"));
    // The dedup toggle is locked while a key is configured
    expect(screen.getByLabelText("启用完全重复去重")).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "保存表设置" }));
    expect(renameMutateMock).toHaveBeenCalledTimes(1);
    expect(renameMutateMock.mock.calls[0][0]).toMatchObject({
      upsert_key: ["title"],
    });
  });

  it("重命名与改列注意事项通过提示气泡展示", () => {
    renderWithProviders(<EditTableDialog tableName="customer_orders" onClose={() => {}} />);

    expect(screen.getByLabelText("表信息注意事项")).toBeInTheDocument();
    expect(screen.getByLabelText("修改列注意事项")).toBeInTheDocument();
    // Key caveats are rendered inside the tooltip bodies
    expect(screen.getByText(/尽量不要更改表名/)).toBeInTheDocument();
    expect(screen.getByText(/中文标签被用来与文件的列名匹配/)).toBeInTheDocument();
  });
});

// ── Delete confirmation ────────────────────────────────────────────────────

describe("删除数据表确认", () => {
  it("展示依赖警告，输入表名后才允许确认删除", () => {
    renderWithProviders(
      <DeleteTableDialog tableName="customer_orders" chineseName="客户订单" onClose={() => {}} />,
    );

    // Dependency warning surfaces views and visualizations
    expect(screen.getByText(/订单视图/)).toBeInTheDocument();
    expect(screen.getByText(/订单图表/)).toBeInTheDocument();

    const confirmButton = screen.getByRole("button", { name: /确认删除/ });
    expect(confirmButton).toBeDisabled();

    // Wrong text keeps the button disabled
    fireEvent.change(screen.getByLabelText(/以确认删除/), { target: { value: "wrong" } });
    expect(confirmButton).toBeDisabled();

    // Matching the table name enables and triggers deletion
    fireEvent.change(screen.getByLabelText(/以确认删除/), {
      target: { value: "customer_orders" },
    });
    expect(confirmButton).not.toBeDisabled();
    fireEvent.click(confirmButton);
    expect(deleteMutateMock).toHaveBeenCalledWith(
      { table: "customer_orders", confirm: true },
      expect.anything(),
    );
  });
});
