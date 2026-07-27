import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

function renderWithClient(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  const { rerender, ...result } = render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
  return {
    ...result,
    rerender: (ui: React.ReactElement) =>
      rerender(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  };
}

describe("App — health check page", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the YKMMgmt heading and phase subtitle", () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      json: () => Promise.resolve({ status: "ok" }),
    } as Response);

    renderWithClient(<App />);

    expect(screen.getByText("YKMMgmt")).toBeInTheDocument();
    expect(screen.getByText("Project Scaffolding — Phase 1")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", () => {
    vi.mocked(fetch).mockReturnValue(
      new Promise(() => {
        /* never resolves */
      }) as Promise<Response>,
    );

    renderWithClient(<App />);

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("displays 'Backend Online' on successful health response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      json: () => Promise.resolve({ status: "ok" }),
    } as Response);

    renderWithClient(<App />);

    expect(await screen.findByText("Backend Online")).toBeInTheDocument();
    expect(screen.getByText(/"status": "ok"/)).toBeInTheDocument();
  });

  it("displays error state when the backend is unreachable", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("Connection refused"));

    renderWithClient(<App />);

    expect(await screen.findByText(/Failed to reach backend/)).toBeInTheDocument();
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
  });

  it("displays 'Unknown error' when fetch rejects without a message", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(null);

    renderWithClient(<App />);

    expect(await screen.findByText(/Unknown error/)).toBeInTheDocument();
  });

  it("shows the health status code block on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      json: () => Promise.resolve({ status: "degraded" }),
    } as Response);

    renderWithClient(<App />);

    expect(await screen.findByText(/"status": "degraded"/)).toBeInTheDocument();
  });
});
