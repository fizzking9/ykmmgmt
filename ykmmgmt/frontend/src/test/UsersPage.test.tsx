import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import UsersPage from "@/pages/UsersPage";

// ── Helpers ────────────────────────────────────────────────────────────────

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const USER_LIST = [
  {
    id: 1,
    username: "bigboss",
    role: "root",
    is_active: true,
    created_at: "2026-08-01T10:00:00Z",
    updated_at: "2026-08-01T10:00:00Z",
  },
  {
    id: 2,
    username: "operator",
    role: "user",
    is_active: true,
    created_at: "2026-08-02T10:00:00Z",
    updated_at: "2026-08-02T10:00:00Z",
  },
];

function renderUsersPage(asRole: "root" | "admin") {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: URL | RequestInfo) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/api/auth/me")) {
      return jsonResponse({ id: asRole === "root" ? 1 : 3, username: "actor", role: asRole });
    }
    if (url.includes("/api/users")) {
      return jsonResponse(USER_LIST);
    }
    return jsonResponse([]);
  });

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/users"]}>
          <UsersPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe("UsersPage — hierarchy-aware role management", () => {
  it("root sees 修改角色 on manageable user rows but not on the root row", async () => {
    renderUsersPage("root");

    // User list renders
    expect(await screen.findByText("operator")).toBeInTheDocument();

    // Root row renders without action buttons
    const rootRow = screen.getByText("bigboss").closest("tr")!;
    expect(rootRow.textContent).toContain("—");

    // Regular user row has all actions for root
    const userRow = screen.getByText("operator").closest("tr")!;
    expect(userRow.textContent).toContain("重置密码");
    expect(userRow.textContent).toContain("修改角色");
    expect(userRow.textContent).toContain("停用");
  });

  it("admin sees no 修改角色 action (admin can only manage plain users)", async () => {
    renderUsersPage("admin");

    expect(await screen.findByText("operator")).toBeInTheDocument();
    const userRow = screen.getByText("operator").closest("tr")!;
    expect(userRow.textContent).toContain("重置密码");
    expect(userRow.textContent).toContain("停用");
    expect(userRow.textContent).not.toContain("修改角色");
  });

  it("role picker in the create dialog offers 管理员 to root only", async () => {
    renderUsersPage("root");

    fireEvent.click(await screen.findByTestId("create-user-button"));
    // The create dialog is open — its role Select defaults to 用户
    expect(screen.getAllByText("用户").length).toBeGreaterThan(0);
    // Open the dropdown (base-ui opens on pointerdown on the trigger button)
    const trigger = screen.getByRole("combobox");
    fireEvent.pointerDown(trigger, { button: 0 });
    fireEvent.click(trigger);
    // The dropdown now lists both role options
    expect(await screen.findAllByText("管理员")).toHaveLength(1);
  });

  it("role picker for admin offers only 用户", async () => {
    renderUsersPage("admin");

    fireEvent.click(await screen.findByTestId("create-user-button"));
    // No 管理员 option exists anywhere in the dialog for an admin actor
    expect(screen.queryByText("管理员")).not.toBeInTheDocument();
    const trigger = screen.getByRole("combobox");
    fireEvent.pointerDown(trigger, { button: 0 });
    fireEvent.click(trigger);
    await waitFor(() => {
      expect(screen.queryByText("管理员")).not.toBeInTheDocument();
      expect(screen.getAllByText("用户").length).toBeGreaterThan(0);
    });
  });
});
