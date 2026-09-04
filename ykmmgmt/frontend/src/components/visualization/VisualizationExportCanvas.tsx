// ── Offscreen export canvas for saved visualizations ────────────────────────
// Rendered off-screen at full size (704px wide, matching the builder preview)
// so html2canvas can capture a standalone PNG from the visualizations list
// page. Signals onReady once the chart data has loaded and Recharts settled.

import { useEffect, useRef } from "react";
import { useVisualizationData, type VisualizationListResponse } from "@/hooks/useVisualizations";
import type { ChartType } from "@/contexts/VisualizationBuilderContext";
import { VisualizationRenderer } from "@/components/visualization/VisualizationRenderer";

/** Delay after data arrives so Recharts finishes layout before capture. */
const SETTLE_DELAY_MS = 400;

export function VisualizationExportCanvas({
  viz,
  onReady,
}: {
  viz: VisualizationListResponse;
  /** Fires with false when the data failed to load (export is skipped). */
  onReady: (ok: boolean) => void;
}) {
  const { data, isLoading, isError } = useVisualizationData(viz.id);
  // Set only once the timer FIRES — marking earlier would break under React
  // StrictMode, whose mount → unmount → remount cycle cancels the timer via
  // cleanup while the ref would still block re-scheduling it, so onReady
  // would never fire and the export queue would hang forever.
  const notifiedRef = useRef(false);
  // Keep the latest callback so a re-rendering parent never cancels the settle timer
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  });

  useEffect(() => {
    if (isLoading || notifiedRef.current) return;
    const t = setTimeout(() => {
      notifiedRef.current = true;
      onReadyRef.current(!isError && !!data);
    }, SETTLE_DELAY_MS);
    return () => clearTimeout(t);
  }, [isLoading, isError, data]);

  return (
    // pb-4 protects bottom-edge axis text from html2canvas clipping
    <div className="rounded-md border bg-white p-4 pb-4">
      <h3 className="mb-3 text-base font-semibold">{viz.name}</h3>
      {data ? (
        <VisualizationRenderer
          chartType={viz.chart_type as ChartType}
          config={data.config_json}
          columns={data.columns}
          rows={data.rows}
          columnTypes={data.column_types}
          height={480}
        />
      ) : (
        <div className="flex h-[480px] items-center justify-center text-muted-foreground">
          {isError ? "数据加载失败" : "加载中…"}
        </div>
      )}
    </div>
  );
}
