import { useEffect, useMemo, useState } from "react";
import { Cpu, Loader2, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  LIMIT_OPTIONS,
  RANGE_OPTIONS,
  rangeLabel,
  useDeviceAnalysis,
  type DeviceTimelineItem,
  type RangeKey,
} from "@/hooks/useDeviceAnalysis";
import { cn } from "@/lib/utils";

// Per-source accent palette, assigned by the order sources appear in counts.
const DOT_COLORS = [
  "bg-emerald-500",
  "bg-rose-500",
  "bg-sky-500",
  "bg-amber-500",
  "bg-violet-500",
  "bg-teal-500",
  "bg-orange-500",
  "bg-indigo-500",
];
const TAG_COLORS = [
  "border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-300",
  "border-rose-300 text-rose-700 dark:border-rose-700 dark:text-rose-300",
  "border-sky-300 text-sky-700 dark:border-sky-700 dark:text-sky-300",
  "border-amber-300 text-amber-700 dark:border-amber-700 dark:text-amber-300",
  "border-violet-300 text-violet-700 dark:border-violet-700 dark:text-violet-300",
  "border-teal-300 text-teal-700 dark:border-teal-700 dark:text-teal-300",
  "border-orange-300 text-orange-700 dark:border-orange-700 dark:text-orange-300",
  "border-indigo-300 text-indigo-700 dark:border-indigo-700 dark:text-indigo-300",
];

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "touch-manipulation rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function TimelineCard({ item, index }: { item: DeviceTimelineItem; index: number }) {
  const dot = DOT_COLORS[index % DOT_COLORS.length];
  const tag = TAG_COLORS[index % TAG_COLORS.length];
  return (
    <li className="relative pl-5">
      <span
        className={cn("absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full", dot)}
        aria-hidden="true"
      />
      <div className="mb-1 text-xs text-muted-foreground">{item.time}</div>
      <div className="rounded-md border bg-card p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Badge variant="outline" className={cn("shrink-0", tag)}>
              {item.source_label}
            </Badge>
            <span className="truncate text-sm font-medium" title={item.title}>
              {item.title}
            </span>
          </div>
          {item.amount !== null && (
            <span className="shrink-0 text-sm font-semibold text-rose-600 dark:text-rose-400">
              ¥ {item.amount.toFixed(2)}
            </span>
          )}
        </div>
        {item.summary && <div className="mt-1 text-sm text-muted-foreground">{item.summary}</div>}
        {item.fields.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {item.fields.map((f) => (
              <span key={f.label} className="min-w-0">
                <span className="opacity-70">{f.label}:</span> {f.value}
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function DeviceAnalysisDialog({
  open,
  onClose,
  initialSn = "",
}: {
  open: boolean;
  onClose: () => void;
  /** Pre-fill (and auto-submit) this SN when the dialog opens. */
  initialSn?: string;
}) {
  const [snInput, setSnInput] = useState("");
  const [sn, setSn] = useState("");
  const [range, setRange] = useState<RangeKey>("all");
  const [limit, setLimit] = useState(100);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);

  // Opening with a preset SN (e.g. from 投诉明细) jumps straight to results
  useEffect(() => {
    if (open) {
      setSnInput(initialSn);
      setSn(initialSn);
      setSourceFilter(null);
    }
  }, [open, initialSn]);

  const submitted = sn.trim() !== "";
  const { data, isLoading, isError, error, refetch } = useDeviceAnalysis(
    sn.trim(),
    range,
    limit,
    open && submitted,
  );

  const counts = useMemo(() => data?.profile.counts ?? [], [data]);
  const colorIndex = useMemo(() => {
    const map = new Map<string, number>();
    counts.forEach((c, i) => map.set(c.source, i % DOT_COLORS.length));
    return map;
  }, [counts]);

  const timeline = useMemo(() => {
    const items = data?.timeline ?? [];
    return sourceFilter ? items.filter((i) => i.source === sourceFilter) : items;
  }, [data, sourceFilter]);

  const handleSearch = () => {
    setSourceFilter(null);
    setSn(snInput.trim());
  };

  return (
    <Dialog open={open} onClose={onClose} title="设备行为分析" className="max-w-5xl">
      {/* Toolbar — time frame, max records, refresh */}
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <Select value={range} onValueChange={(v) => setRange(v as RangeKey)}>
          <SelectTrigger className="w-24" aria-label="时间范围">
            <SelectValue>{rangeLabel(range)}</SelectValue>
          </SelectTrigger>
          <SelectContent
            align="start"
            sideOffset={4}
            alignItemWithTrigger={false}
            style={{ width: 96 }}
          >
            {RANGE_OPTIONS.map((o) => (
              <SelectItem key={o.key} value={o.key}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
          <SelectTrigger className="w-24" aria-label="最多记录数">
            <SelectValue>{limit} 条</SelectValue>
          </SelectTrigger>
          <SelectContent
            align="start"
            sideOffset={4}
            alignItemWithTrigger={false}
            style={{ width: 96 }}
          >
            {LIMIT_OPTIONS.map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} 条
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button size="sm" onClick={() => refetch()} disabled={isLoading || !submitted}>
          <RefreshCw className={cn("mr-1 h-4 w-4", isLoading && "animate-spin")} />
          刷新
        </Button>
      </div>

      {/* SN search */}
      <div className="mb-4 flex gap-2">
        <Input
          value={snInput}
          onChange={(e) => setSnInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSearch();
          }}
          placeholder="输入设备 SN"
          aria-label="设备 SN"
        />
        <Button onClick={handleSearch} disabled={!snInput.trim()}>
          <Search className="mr-1 h-4 w-4" />
          查询
        </Button>
      </div>

      {!submitted && (
        <div className="rounded-md bg-muted/30 p-12 text-center">
          <Cpu className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">输入设备 SN 后查询其档案与事件时间线</p>
        </div>
      )}

      {submitted && isLoading && (
        <div className="flex items-center justify-center gap-2 p-12 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          加载中…
        </div>
      )}

      {submitted && isError && (
        <div className="rounded-md bg-destructive/10 p-6 text-center text-sm text-destructive">
          {(error as Error | null)?.message ?? "获取设备分析数据失败"}
        </div>
      )}

      {submitted && data && !isLoading && (
        <>
          {/* Device profile */}
          <section className="mb-4 rounded-lg border bg-card p-4">
            <div className="mb-3 flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">设备档案 {data.profile.sn}</h3>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-4">
              {data.profile.fields.map((f) => (
                <div key={f.label} className="flex min-w-0 gap-2">
                  <dt className="shrink-0 text-muted-foreground">{f.label}</dt>
                  <dd className="truncate font-medium" title={f.value}>
                    {f.value}
                  </dd>
                </div>
              ))}
              <div className="flex min-w-0 gap-2">
                <dt className="shrink-0 text-muted-foreground">记录总数</dt>
                <dd className="font-medium">{data.profile.total}</dd>
              </div>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              {counts
                .filter((c) => c.count > 0)
                .map((c) => (
                  <Badge key={c.source} variant="secondary">
                    {c.source_label} {c.count}
                  </Badge>
                ))}
            </div>
          </section>

          {/* Source filter chips */}
          <div className="mb-3 flex flex-wrap gap-2">
            <FilterChip active={sourceFilter === null} onClick={() => setSourceFilter(null)}>
              全部 ({data.profile.total})
            </FilterChip>
            {counts
              .filter((c) => c.count > 0)
              .map((c) => (
                <FilterChip
                  key={c.source}
                  active={sourceFilter === c.source}
                  onClick={() => setSourceFilter(sourceFilter === c.source ? null : c.source)}
                >
                  {c.source_label} ({c.count})
                </FilterChip>
              ))}
          </div>

          {/* Timeline */}
          <h4 className="mb-2 text-sm font-semibold">时序流 ({timeline.length})</h4>
          {timeline.length === 0 ? (
            <div className="rounded-md bg-muted/30 p-10 text-center text-sm text-muted-foreground">
              该时间范围内暂无事件记录
            </div>
          ) : (
            <ul className="relative space-y-4 before:absolute before:bottom-1 before:left-[4px] before:top-1 before:w-px before:bg-border">
              {timeline.map((item, i) => (
                <TimelineCard
                  key={`${item.source}-${item.time}-${i}`}
                  item={item}
                  index={colorIndex.get(item.source) ?? 0}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </Dialog>
  );
}
