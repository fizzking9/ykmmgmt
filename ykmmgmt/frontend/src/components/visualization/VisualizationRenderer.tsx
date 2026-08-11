/* eslint-disable react-refresh/only-export-components */
import { useMemo } from "react";
import {
  BarChartPreview,
  BoxplotChartPreview,
  HistogramChartPreview,
  KpiCardPreview,
  LineChartPreview,
  PieChartPreview,
  ScatterChartPreview,
  TablePreview,
  isDateColumn,
} from "@/pages/VisualizationBuilderPage";
import {
  COLOR_THEMES,
  DEFAULT_NUMBER_FORMAT,
  type ChartType,
  type NumberFormat,
} from "@/contexts/VisualizationBuilderContext";

// ── Shared rendering for saved visualizations ──────────────────────────────
// Reused by the Phase 7 builder preview (via the same *Preview components),
// the Phase 8 list-page thumbnails and the full-size view page.

/** Chart types that get a thumbnail on the visualizations list page. */
export const THUMBNAIL_CHART_TYPES: ChartType[] = [
  "bar",
  "line",
  "pie",
  "scatter",
  "histogram",
  "boxplot",
];

export function isThumbnailChartType(chartType: string): boolean {
  return THUMBNAIL_CHART_TYPES.includes(chartType as ChartType);
}

/** Resolve theme colors / number format persisted inside config_json. */
function themeColorsFromConfig(config: Record<string, unknown>): string[] {
  const theme = COLOR_THEMES.find((t) => t.name === (config._colorTheme as string));
  return theme?.colors ?? COLOR_THEMES[0].colors;
}

function numberFormatFromConfig(config: Record<string, unknown>): NumberFormat {
  return (config._numberFormat as NumberFormat) ?? DEFAULT_NUMBER_FORMAT;
}

export function VisualizationRenderer({
  chartType,
  config,
  columns,
  rows,
  height = 480,
  fill = false,
}: {
  chartType: ChartType;
  config: Record<string, unknown>;
  columns: string[];
  rows: Record<string, unknown>[];
  /** Chart height in px (default 480). */
  height?: number;
  /** Fill a height-constrained parent (dashboard tiles) instead of a fixed height. */
  fill?: boolean;
}) {
  const colors = useMemo(() => themeColorsFromConfig(config), [config]);
  const numberFormat = useMemo(() => numberFormatFromConfig(config), [config]);

  const dateColumns = useMemo(() => {
    if (!rows.length || !columns.length) return [];
    return columns.filter((col) => isDateColumn(rows.map((r) => r[col])));
  }, [columns, rows]);

  if (!rows.length) {
    return (
      <div className="flex h-32 items-center justify-center text-muted-foreground">暂无数据</div>
    );
  }

  const chartHeight = height;

  const content = (() => {
    switch (chartType) {
      case "table":
        return <TablePreview config={config} columns={columns} rows={rows} />;
      case "kpi_card":
        return (
          <KpiCardPreview
            config={config}
            rows={rows}
            numberFormat={numberFormat}
            height={fill ? undefined : chartHeight}
          />
        );
      case "bar":
        return (
          <BarChartPreview
            config={config}
            rows={rows}
            colors={colors}
            dateColumns={dateColumns}
            height={chartHeight}
            fill={fill}
            numberFormat={numberFormat}
          />
        );
      case "line":
        return (
          <LineChartPreview
            config={config}
            rows={rows}
            colors={colors}
            dateColumns={dateColumns}
            height={chartHeight}
            fill={fill}
            numberFormat={numberFormat}
          />
        );
      case "pie":
        return (
          <PieChartPreview
            config={config}
            rows={rows}
            colors={colors}
            height={chartHeight}
            fill={fill}
          />
        );
      case "scatter":
        return (
          <ScatterChartPreview
            config={config}
            rows={rows}
            colors={colors}
            dateColumns={dateColumns}
            height={chartHeight}
            fill={fill}
            numberFormat={numberFormat}
          />
        );
      case "histogram":
        return (
          <HistogramChartPreview
            config={config}
            rows={rows}
            colors={colors}
            height={chartHeight}
            fill={fill}
          />
        );
      case "boxplot":
        return (
          <BoxplotChartPreview
            config={config}
            rows={rows}
            colors={colors}
            height={chartHeight}
            fill={fill}
          />
        );
    }
  })();

  return content;
}
