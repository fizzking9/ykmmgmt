import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { UploadProvider } from "@/contexts/UploadContext";
import App from "@/App";

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
      <MemoryRouter initialEntries={[initialRoute]}>
        <UploadProvider>
          <App />
        </UploadProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App Shell — layout and routing", () => {
  it("renders the app title in the sidebar", () => {
    renderWithRouter("/");
    expect(screen.getByText("云客猫管理平台")).toBeInTheDocument();
  });

  it("renders sidebar navigation groups", () => {
    renderWithRouter("/");
    expect(screen.getByText("数据管理")).toBeInTheDocument();
    expect(screen.getByText("数据可视化")).toBeInTheDocument();
  });

  it("renders the home page at /", () => {
    const { container } = renderWithRouter("/");
    // Home page renders an empty div — the main content area should exist
    expect(container.querySelector("main")).toBeInTheDocument();
  });

  it("renders the upload page at /upload", () => {
    renderWithRouter("/upload");
    expect(screen.getByText("上传数据")).toBeInTheDocument();
  });

  it("renders the import history page at /imports", () => {
    renderWithRouter("/imports");
    expect(screen.getByText("导入历史")).toBeInTheDocument();
  });

  it("renders the dashboard placeholder at /dashboard", () => {
    renderWithRouter("/dashboard");
    expect(screen.getByText("仪表盘")).toBeInTheDocument();
    expect(screen.getByText("即将上线")).toBeInTheDocument();
  });
});
