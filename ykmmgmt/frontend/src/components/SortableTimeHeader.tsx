/* eslint-disable react-refresh/only-export-components */

// ── Sortable time column header ────────────────────────────────────────────
// Click cycles asc (▲) → desc (▼) → none (↕), matching the Data Browser
// sorting pattern. Used by the views and visualizations list pages.

export type TimeSortCol = "created_at" | "updated_at";
export type SortDir = "asc" | "desc" | null;

export function nextSortDir(dir: SortDir): SortDir {
  if (dir === null) return "asc";
  if (dir === "asc") return "desc";
  return null;
}

export function SortableTimeHeader({
  label,
  col,
  sortCol,
  sortDir,
  onSort,
}: {
  label: string;
  col: TimeSortCol;
  sortCol: TimeSortCol;
  sortDir: SortDir;
  onSort: (col: TimeSortCol) => void;
}) {
  const active = sortCol === col;
  const arrow = active ? (sortDir === "asc" ? "▲" : "▼") : "↕";
  return (
    <button
      type="button"
      onClick={() => onSort(col)}
      className="inline-flex items-center gap-1 hover:text-foreground"
      title="点击切换排序"
    >
      {label}
      <span className={`text-xs ${active ? "text-primary" : "text-muted-foreground/50"}`}>
        {arrow}
      </span>
    </button>
  );
}
