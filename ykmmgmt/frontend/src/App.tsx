import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

type HealthResponse = {
  status: string;
};

function HealthCard() {
  const { data, isLoading, isError, error } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then((res) => res.json()),
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30">
      <div
        className={cn(
          "w-full max-w-sm rounded-lg border bg-card p-8 shadow-sm",
          "text-center",
        )}
      >
        <h1 className="mb-2 text-2xl font-semibold text-card-foreground">YKMMgmt</h1>
        <p className="mb-6 text-sm text-muted-foreground">Project Scaffolding — Phase 1</p>

        {isLoading && (
          <div className="space-y-3">
            <div className="mx-auto h-4 w-24 animate-pulse rounded bg-muted" />
            <div className="mx-auto h-3 w-16 animate-pulse rounded bg-muted" />
          </div>
        )}

        {isError && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            Failed to reach backend: {error?.message ?? "Unknown error"}
          </div>
        )}

        {data && (
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-green-50 px-4 py-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
              <span className="text-sm font-medium text-green-700">Backend Online</span>
            </div>
            <p className="font-mono text-xs text-muted-foreground">
              GET /api/health →{" "}
              <code className="rounded bg-muted px-1 py-0.5">
                {"{"}"status": "{data.status}"{"}"}
              </code>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return <HealthCard />;
}
