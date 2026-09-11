import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FilterDropdown, type FilterOption } from "@/components/home/FilterDropdown";
import { useDeviceAnalysisContext } from "@/contexts/DeviceAnalysisContext";
import { useHomeComplaints, type HomeComplaintRow } from "@/hooks/useHomeOverview";
import { cn } from "@/lib/utils";

// 结果/状态 badge tones; unknown statuses fall back to a neutral outline.
const STATUS_STYLES: Record<string, string> = {
  已完成:
    "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  待处理:
    "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-300",
  处理中:
    "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300",
  终止:
    "border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400",
};
const SUBJECT_STYLE =
  "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300";

// Sentinel for empty values inside filter option lists
const NULL_KEY = "__null__";

type SortKey = "register_time" | "finish_time";
interface SortState {
  key: SortKey;
  dir: "asc" | "desc";
}
type FilterKey = "status" | "category" | "accused_subject";
type FilterState = Record<FilterKey, string[]>;

const EMPTY_FILTERS: FilterState = { status: [], category: [], accused_subject: [] };

/** "2026-09-11T16:57:00" → "09-11 16:57" like the reference board. */
function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Distinct non-empty values as filter options, plus a "(空)" entry. */
function buildOptions(
  rows: HomeComplaintRow[],
  get: (r: HomeComplaintRow) => string | null,
): FilterOption[] {
  const seen = new Set<string>();
  let hasNull = false;
  for (const r of rows) {
    const v = get(r);
    if (v === null || v === "") hasNull = true;
    else seen.add(v);
  }
  const opts = [...seen]
    .sort((a, b) => a.localeCompare(b, "zh-CN"))
    .map((v) => ({ value: v, label: v }));
  if (hasNull) opts.push({ value: NULL_KEY, label: "(空)" });
  return opts;
}

function matchesFilter(value: string | null, selected: string[]): boolean {
  if (selected.length === 0) return true;
  const norm = value === null || value === "" ? NULL_KEY : value;
  return selected.includes(norm);
}

function ComplaintRowCells({
  row,
  onOpenAnalysis,
}: {
  row: HomeComplaintRow;
  onOpenAnalysis: (sn: string) => void;
}) {
  return (
    <>
      <TableCell>{formatDateTime(row.register_time)}</TableCell>
      <TableCell>{formatDateTime(row.finish_time)}</TableCell>
      <TableCell>
        {row.device_sn ? (
          <button
            type="button"
            onClick={() => onOpenAnalysis(row.device_sn!)}
            title={`在设备分析中查看 ${row.device_sn}`}
            className="text-primary underline-offset-4 hover:underline"
          >
            {row.device_sn}
          </button>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell>
        {row.status ? (
          <Badge variant="outline" className={STATUS_STYLES[row.status] ?? ""}>
            {row.status}
          </Badge>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">{row.source ?? "—"}</TableCell>
      <TableCell>
        {row.accused_subject ? (
          <Badge variant="outline" className={SUBJECT_STYLE} title={row.accused_subject}>
            {row.accused_subject}
          </Badge>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell>{row.category ?? "—"}</TableCell>
      <TableCell className="max-w-md truncate" title={row.content ?? undefined}>
        {row.content ?? "—"}
      </TableCell>
      <TableCell className="text-muted-foreground">{row.supplement ?? "—"}</TableCell>
      <TableCell>
        {row.handler ? (
          <span className="text-primary">{row.handler}</span>
        ) : (
          <span className="text-muted-foreground">未分配</span>
        )}
      </TableCell>
    </>
  );
}

/** 投诉明细 — the day's complaint work orders as a sortable/filterable table. */
export function ComplaintTable({ date }: { date: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const [sort, setSort] = useState<SortState | null>(null);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const { data, isPending } = useHomeComplaints(date);
  const { openDeviceAnalysis } = useDeviceAnalysisContext();

  // Memoize against the stable query payload so the `?? []` fallback doesn't
  // produce a fresh array (and fresh memo deps) on every render.
  const rows = useMemo(() => data?.rows ?? [], [data]);
  const total = data?.total ?? 0;

  // A new day invalidates the previous day's filter/sort selection
  useEffect(() => {
    setFilters(EMPTY_FILTERS);
    setSort(null);
  }, [date]);

  const statusOptions = useMemo(() => buildOptions(rows, (r) => r.status), [rows]);
  const categoryOptions = useMemo(() => buildOptions(rows, (r) => r.category), [rows]);
  const accusedOptions = useMemo(() => buildOptions(rows, (r) => r.accused_subject), [rows]);

  const visibleRows = useMemo(() => {
    const filtered = rows.filter(
      (r) =>
        matchesFilter(r.status, filters.status) &&
        matchesFilter(r.category, filters.category) &&
        matchesFilter(r.accused_subject, filters.accused_subject),
    );
    if (!sort) return filtered;
    return [...filtered].sort((a, b) => {
      const av = a[sort.key] ?? "";
      const bv = b[sort.key] ?? "";
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, filters, sort]);

  function toggleSort(key: SortKey) {
    setSort((prev) =>
      prev?.key === key
        ? { key, dir: prev.dir === "desc" ? "asc" : "desc" }
        : { key, dir: "desc" },
    );
  }

  function setFilter(key: FilterKey, next: string[]) {
    setFilters((prev) => ({ ...prev, [key]: next }));
  }

  function sortHeader(key: SortKey, label: string) {
    const active = sort?.key === key;
    return (
      <button
        type="button"
        onClick={() => toggleSort(key)}
        title="按时间排序"
        className={cn("flex items-center gap-1 font-medium", active && "text-primary")}
      >
        {label}
        {active ? (
          sort.dir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>
    );
  }

  return (
    <section className="rounded-lg border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
        <div className="flex items-baseline gap-2">
          <h2 className="text-base font-semibold">投诉明细</h2>
          <span className="text-xs text-muted-foreground">
            共 {total} 条 · 当前 {visibleRows.length} 条
          </span>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
          title={collapsed ? "展开" : "收起"}
          className="touch-manipulation rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <ChevronDown className={cn("h-4 w-4 transition-transform", collapsed && "-rotate-90")} />
        </button>
      </div>

      {!collapsed && (
        <div className="max-h-[28rem] overflow-auto border-t [&_[data-slot=table-container]]:overflow-visible">
          {isPending ? (
            <div className="flex h-40 items-center justify-center text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : rows.length === 0 ? (
            <div className="p-10 text-center text-sm text-muted-foreground">当日暂无投诉工单</div>
          ) : (
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead>{sortHeader("register_time", "登记时间")}</TableHead>
                  <TableHead>{sortHeader("finish_time", "完成时间")}</TableHead>
                  <TableHead>设备SN</TableHead>
                  <TableHead>
                    <FilterDropdown
                      label="结果/状态"
                      options={statusOptions}
                      selected={filters.status}
                      onChange={(next) => setFilter("status", next)}
                    />
                  </TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead>
                    <FilterDropdown
                      label="被投诉主体"
                      options={accusedOptions}
                      selected={filters.accused_subject}
                      onChange={(next) => setFilter("accused_subject", next)}
                    />
                  </TableHead>
                  <TableHead>
                    <FilterDropdown
                      label="分类"
                      options={categoryOptions}
                      selected={filters.category}
                      onChange={(next) => setFilter("category", next)}
                    />
                  </TableHead>
                  <TableHead className="min-w-64">投诉内容</TableHead>
                  <TableHead>补充</TableHead>
                  <TableHead>处理/跟进</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} className="p-10 text-center text-muted-foreground">
                      无符合筛选条件的记录
                    </TableCell>
                  </TableRow>
                ) : (
                  visibleRows.map((row, i) => (
                    <TableRow key={`${row.order_no ?? "row"}-${i}`}>
                      <ComplaintRowCells row={row} onOpenAnalysis={openDeviceAnalysis} />
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </div>
      )}
    </section>
  );
}
