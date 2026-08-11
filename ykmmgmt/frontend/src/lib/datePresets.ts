// ── Quick date-range presets for the dashboard global time filter ────────

export type DatePresetKey = "last7" | "last30" | "thisMonth" | "last3months" | "thisYear";

export const DATE_PRESETS: { key: DatePresetKey; label: string }[] = [
  { key: "last7", label: "最近7天" },
  { key: "last30", label: "最近30天" },
  { key: "thisMonth", label: "本月" },
  { key: "last3months", label: "最近3个月" },
  { key: "thisYear", label: "今年" },
];

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Compute the inclusive [start, end] range for a preset, relative to today. */
export function computePresetRange(
  key: DatePresetKey,
  today: Date = new Date(),
): { start: string; end: string } {
  const end = toIsoDate(today);
  const startDate = new Date(today);
  switch (key) {
    case "last7":
      startDate.setDate(today.getDate() - 6);
      break;
    case "last30":
      startDate.setDate(today.getDate() - 29);
      break;
    case "thisMonth":
      startDate.setDate(1);
      break;
    case "last3months":
      startDate.setMonth(today.getMonth() - 3);
      break;
    case "thisYear":
      startDate.setMonth(0, 1);
      break;
  }
  return { start: toIsoDate(startDate), end };
}
