import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import ProfilePage from "@/pages/ProfilePage";

// ── Helpers ────────────────────────────────────────────────────────────────

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function renderProfilePage() {
  const putCalls: { url: string; body: Record<string, unknown> }[] = [];
  let currentUsername = "actor";

  vi.spyOn(globalThis, "fetch").mockImplementation(
    (input: URL | RequestInfo, init?: RequestInit) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/api/auth/me")) {
        return jsonResponse({ id: 3, username: currentUsername, role: "user" });
      }
      if (url.includes("/api/auth/profile") && init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        putCalls.push({ url, body });
        if (typeof body.username === "string") currentUsername = body.username;
        return jsonResponse({ id: 3, username: currentUsername, role: "user" });
      }
      return jsonResponse({});
    },
  );

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    </QueryClientProvider>,
  );

  return { putCalls };
}

function inputById(id: string): HTMLInputElement {
  const el = document.getElementById(id);
  if (!(el instanceof HTMLInputElement)) throw new Error(`missing input #${id}`);
  return el;
}

// ── Tests ──────────────────────────────────────────────────────────────────

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProfilePage — self-service username & password", () => {
  it("shows the current username and role", async () => {
    renderProfilePage();

    expect(await screen.findByDisplayValue("actor")).toBeInTheDocument();
    expect(screen.getByText("用户")).toBeInTheDocument();
  });

  it("shows the username panel by default and switches panels via the panel nav", async () => {
    renderProfilePage();
    await screen.findByDisplayValue("actor");

    // Username panel is open, password panel hidden
    expect(screen.getByTestId("username-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("password-panel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /修改密码/ }));
    expect(screen.getByTestId("password-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("username-panel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /修改用户名/ }));
    expect(screen.getByTestId("username-panel")).toBeInTheDocument();
  });

  it("submits a username change WITHOUT any password and refreshes state", async () => {
    const { putCalls } = renderProfilePage();
    await screen.findByDisplayValue("actor");

    fireEvent.change(inputById("new-username"), { target: { value: "renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "保存用户名" }));

    await waitFor(() => expect(putCalls).toHaveLength(1));
    expect(putCalls[0].url).toContain("/api/auth/profile");
    // No current_password needed for a username change
    expect(putCalls[0].body).toEqual({ username: "renamed" });
    // AuthContext updated — the disabled "当前用户名" input shows the new name
    await waitFor(() => expect(screen.getByDisplayValue("renamed")).toBeInTheDocument());
  });

  it("keeps the username save button disabled until the username differs", async () => {
    renderProfilePage();
    await screen.findByDisplayValue("actor");

    const save = screen.getByRole("button", { name: "保存用户名" }) as HTMLButtonElement;
    expect(save).toBeDisabled();

    // Same username → still disabled
    fireEvent.change(inputById("new-username"), { target: { value: "actor" } });
    expect(save).toBeDisabled();

    fireEvent.change(inputById("new-username"), { target: { value: "renamed" } });
    expect(save).not.toBeDisabled();
  });

  it("blocks password save when the confirmation does not match", async () => {
    renderProfilePage();
    await screen.findByDisplayValue("actor");

    fireEvent.click(screen.getByRole("tab", { name: /修改密码/ }));

    fireEvent.change(inputById("current-password"), { target: { value: "old-pass" } });
    fireEvent.change(inputById("new-password"), { target: { value: "fresh-pass-123" } });
    fireEvent.change(inputById("confirm-password"), { target: { value: "different-123" } });

    const save = screen.getByRole("button", { name: "保存密码" }) as HTMLButtonElement;
    expect(save).toBeDisabled();
    expect(screen.getByText("两次输入的新密码不一致")).toBeInTheDocument();
  });

  it("submits a password change with the current password once the confirmation matches", async () => {
    const { putCalls } = renderProfilePage();
    await screen.findByDisplayValue("actor");

    fireEvent.click(screen.getByRole("tab", { name: /修改密码/ }));

    fireEvent.change(inputById("current-password"), { target: { value: "old-pass" } });
    fireEvent.change(inputById("new-password"), { target: { value: "fresh-pass-123" } });
    fireEvent.change(inputById("confirm-password"), { target: { value: "fresh-pass-123" } });

    fireEvent.click(screen.getByRole("button", { name: "保存密码" }));

    await waitFor(() => expect(putCalls).toHaveLength(1));
    expect(putCalls[0].body).toEqual({
      current_password: "old-pass",
      new_password: "fresh-pass-123",
    });
  });
});
