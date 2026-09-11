import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  Banknote,
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  Headphones,
  Loader2,
  MessageSquare,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ComplaintTable } from "@/components/home/ComplaintTable";
import { cn } from "@/lib/utils";
import { useHomeOverview, type HomeKpi } from "@/hooks/useHomeOverview";

// ── Presentation constants (match the project's chart theme) ───────────────

const CHART_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea", "#0891b2"];
const AXIS_TICK = { fontSize: 11, fill: "#64748b" };
const AXIS_LINE_STROKE = "#cbd5e1";
const GRID_STROKE = "#e2e8f0";
const TOOLTIP_STYLE: React.CSSProperties = {
  fontSize: 12,
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
};

// KPI accent color + icon per metric key; unknown keys (future metrics)
// fall back to a neutral icon and keep cycling the palette.
const KPI_ICONS: Record<string, LucideIcon> = {
  reception: Headphones,
  sessions: MessageSquare,
  refund_count: AlertCircle,
  refund_amount: Banknote,
  complaints: Bell,
};

// Fixed color per metric key, shared by the KPI accent and the chart series
// (会话数 blue, 接待数 green, 投诉数 red); unknown keys cycle the palette.
const METRIC_COLORS: Record<string, string> = {
  reception: "#16a34a",
  sessions: "#2563eb",
  complaints: "#dc2626",
  refund_count: "#ea580c",
  refund_amount: "#ca8a04",
};

const CHANGE_TONES: Record<"good" | "bad" | "flat", string> = {
  good: "text-emerald-600 dark:text-emerald-400",
  bad: "text-red-600 dark:text-red-400",
  flat: "text-muted-foreground",
};

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

// ── Formatting helpers ─────────────────────────────────────────────────────

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function formatDateCN(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${y}年${m}月${d}日`;
}

function weekdayCN(iso: string): string {
  return WEEKDAYS[new Date(`${iso}T00:00:00`).getDay()];
}

function trimDecimal(x: number): string {
  return x.toFixed(1).replace(/\.0$/, "");
}

/** Compact integer rendering (920 → 920, 2700 → 2.7k) like the reference board. */
function compactCount(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${trimDecimal(n / 1_000_000)}M`;
  if (abs >= 1_000) return `${trimDecimal(n / 1_000)}k`;
  return n.toLocaleString("zh-CN");
}

function formatKpiValue(value: number | null, format: HomeKpi["format"]): string {
  if (value === null || value === undefined) return "—";
  if (format === "currency") {
    return `¥${value.toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  return compactCount(value);
}

function metricColor(key: string, index: number): string {
  return METRIC_COLORS[key] ?? CHART_COLORS[index % CHART_COLORS.length];
}

interface KpiChange {
  text: string;
  delta: number;
}

/** Day-over-day percent change; null when it cannot be computed. */
function formatChange(value: number | null, prev: number | null): KpiChange | null {
  if (value === null || value === undefined || prev === null || prev === undefined || prev === 0) {
    return null;
  }
  const pct = ((value - prev) / prev) * 100;
  const rounded = Math.abs(pct) < 0.05 ? 0 : pct;
  return {
    text: rounded === 0 ? "0%" : `${rounded > 0 ? "↑" : "↓"}${Math.abs(rounded).toFixed(1)}%`,
    delta: rounded,
  };
}

/** Color a change good/bad via metric polarity (increase on a
 *  lower-is-better metric is bad). */
function changeTone(delta: number, higherIsBetter: boolean): "good" | "bad" | "flat" {
  if (delta === 0) return "flat";
  return (delta > 0) === higherIsBetter ? "good" : "bad";
}

function shiftDate(iso: string, delta: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + delta);
  return toISODate(d);
}

// ── KPI card ───────────────────────────────────────────────────────────────

function KpiCard({ kpi, index }: { kpi: HomeKpi; index: number }) {
  const Icon = KPI_ICONS[kpi.key] ?? BarChart3;
  const color = metricColor(kpi.key, index);
  const change = formatChange(kpi.value, kpi.prev_value);
  const tone = change ? changeTone(change.delta, kpi.higher_is_better ?? true) : null;
  return (
    <div className="relative overflow-hidden rounded-lg border bg-card p-4 shadow-sm">
      <span className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: color }} />
      <div className="flex items-center gap-2">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: `${color}1a`, color }}
        >
          <Icon className="h-4 w-4" />
        </span>
        <span className="truncate text-xs text-muted-foreground" title={kpi.label}>
          {kpi.label}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="truncate text-2xl font-semibold tabular-nums">
          {formatKpiValue(kpi.value, kpi.format)}
        </p>
        {change && tone && (
          <span
            className={cn("shrink-0 text-xs font-medium", CHANGE_TONES[tone])}
            title="较前一日"
          >
            {change.text}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [date, setDate] = useState(() => toISODate(new Date()));
  const [activeGroups, setActiveGroups] = useState<string[]>(["reception"]);
  const { data, isPending, isError, isFetching, refetch, dataUpdatedAt } = useHomeOverview(date);

  const kpis = data?.kpis ?? [];
  // Memoize against the stable query payload so the `?? []` fallbacks don't
  // produce fresh arrays (and fresh memo deps) on every render.
  const groups = useMemo(() => data?.trend?.groups ?? [], [data]);
  const hours = useMemo(() => data?.trend?.hours ?? [], [data]);
  const series = useMemo(() => data?.trend?.series ?? [], [data]);

  const isToday = date === toISODate(new Date());

  // Multi-select tabs: the canvas shows the union of the selected groups' series
  const activeSeries = useMemo(() => {
    const keys = new Set<string>();
    for (const g of groups) {
      if (activeGroups.includes(g.key)) for (const s of g.series) keys.add(s);
    }
    return series.filter((s) => keys.has(s.key));
  }, [groups, series, activeGroups]);

  const chartData = useMemo(
    () =>
      hours.map((hour, i) => {
        const row: Record<string, number | string> = { hour };
        for (const s of activeSeries) row[s.key] = s.values[i] ?? 0;
        return row;
      }),
    [hours, activeSeries],
  );

  function toggleGroup(key: string) {
    setActiveGroups((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }

  const updatedAt = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("zh-CN", { hour12: false })
    : null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">
            {isToday ? "今日看板" : "历史看板"}
          </h1>
          <span className="text-sm text-muted-foreground">
            {formatDateCN(date)} {weekdayCN(date)}
          </span>
          {isToday && (
            <Badge className="border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              实时数据
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              title="前一天"
              aria-label="前一天"
              onClick={() => setDate((d) => shiftDate(d, -1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <input
              type="date"
              value={date}
              onChange={(e) => e.target.value && setDate(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              aria-label="选择日期"
            />
            <Button
              variant="outline"
              size="icon-sm"
              title="后一天"
              aria-label="后一天"
              onClick={() => setDate((d) => shiftDate(d, 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
            刷新
          </Button>
          {updatedAt && <span className="text-xs text-muted-foreground">更新于 {updatedAt}</span>}
        </div>
      </div>

      {/* KPI cards */}
      {isPending ? (
        <div className="flex h-40 items-center justify-center text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center text-sm text-destructive">
          看板数据加载失败，请稍后重试
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {kpis.map((kpi, i) => (
              <KpiCard key={kpi.key} kpi={kpi} index={i} />
            ))}
          </div>

          {/* Hourly trend */}
          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-baseline gap-2">
                <h2 className="text-base font-semibold">实时趋势</h2>
                <span className="text-xs text-muted-foreground">当日各时段指标分布</span>
              </div>
              <div className="flex items-center gap-1 rounded-md border p-0.5">
                {groups.map((g) => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => toggleGroup(g.key)}
                    aria-pressed={activeGroups.includes(g.key)}
                    className={cn(
                      "rounded px-3 py-1 text-xs transition-colors",
                      activeGroups.includes(g.key)
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 flex h-72 flex-col">
              {activeSeries.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  请选择至少一个指标
                </div>
              ) : (
                <>
                  {/* Custom legend in exact series order so legend ↔ lines align */}
                  <div className="mb-2 flex flex-wrap items-center justify-center gap-4 text-xs">
                    {activeSeries.map((s, i) => (
                      <span key={s.key} className="flex items-center gap-1.5">
                        <span
                          className="h-2.5 w-2.5 rounded-[2px]"
                          style={{ backgroundColor: metricColor(s.key, i) }}
                        />
                        {s.label}
                      </span>
                    ))}
                  </div>
                  <div className="min-h-0 flex-1">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
                        <XAxis
                          dataKey="hour"
                          tick={AXIS_TICK}
                          tickLine={false}
                          axisLine={{ stroke: AXIS_LINE_STROKE }}
                        />
                        <YAxis
                          width={48}
                          tick={AXIS_TICK}
                          tickLine={false}
                          axisLine={false}
                          tickFormatter={(v: number) => compactCount(Number(v))}
                        />
                        <Tooltip
                          contentStyle={TOOLTIP_STYLE}
                          cursor={{ stroke: "#94a3b8", strokeDasharray: "3 3" }}
                        />
                        {activeSeries.map((s, i) => (
                          <Line
                            key={s.key}
                            type="monotone"
                            dataKey={s.key}
                            name={s.label}
                            stroke={metricColor(s.key, i)}
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4 }}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* Complaint detail table */}
      <ComplaintTable date={date} />
    </div>
  );
}
