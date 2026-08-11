/* eslint-disable react-refresh/only-export-components */
// ── Shared dashboard tile bodies ──────────────────────────────────────────
// Presentational bodies reused by the dashboard builder (summary mode) and
// the display page (live data). Data fetching stays with the caller except
// for ad-hoc KPI tiles, which always aggregate their view client-side.

import { Skeleton } from "@/components/ui/skeleton";
import { useKpiTileData, computeAggregation, type KpiTileConfig } from "@/hooks/useDashboards";
import { VisualizationRenderer } from "@/components/visualization/VisualizationRenderer";
import type { ChartType } from "@/contexts/VisualizationBuilderContext";
import type { VisualizationDataResponse } from "@/hooks/useVisualizations";
import { Loader2 } from "lucide-react";

export const AGG_LABELS: Record<KpiTileConfig["agg"], string> = {
  SUM: "求和",
  COUNT: "计数",
  AVG: "平均值",
  MIN: "最小值",
  MAX: "最大值",
};

function formatKpiValue(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)} 万`;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

/** Ad-hoc KPI card tile body — fetches view data and aggregates client-side. */
export function KpiTileBody({ config }: { config: KpiTileConfig }) {
  const { data, isLoading, isError, error } = useKpiTileData(config.view_id);

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-32" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex h-full items-center justify-center p-3 text-sm text-red-600">
        数据加载失败：{error instanceof Error ? error.message : "未知错误"}
      </div>
    );
  }

  const value = computeAggregation(data.rows, config.value_column, config.agg);

  return (
    <div
      // Fill the tile; inline-size containment scales the value with tile width
      className="flex h-full w-full flex-col items-center justify-center gap-1 p-2 text-center [container-type:inline-size]"
    >
      <p className="text-xs text-muted-foreground">{config.label}</p>
      <p className="font-bold leading-tight tracking-tight text-[clamp(1.5rem,13cqw,3.25rem)]">
        {value === null ? "—" : formatKpiValue(value)}
      </p>
      <p className="text-[11px] text-muted-foreground">
        {AGG_LABELS[config.agg]} · {config.value_column}
      </p>
    </div>
  );
}

/** Visualization tile body — renders fetched data via the shared renderer. */
export function VisualizationTileBody({
  data,
  height,
}: {
  data: VisualizationDataResponse;
  height?: number;
}) {
  return (
    <VisualizationRenderer
      chartType={data.chart_type as ChartType}
      config={data.config_json}
      columns={data.columns}
      rows={data.rows}
      height={height ?? 300}
    />
  );
}

/** Loading placeholder matching the tile interior. */
export function TileLoadingBody() {
  return (
    <div className="flex h-full items-center justify-center p-3">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}
