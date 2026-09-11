import { apiFetch } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

// ── Types (mirror GET /api/device-analysis/profile) ─────────────────────────

export interface DeviceField {
  label: string;
  value: string;
}

export interface DeviceSourceCount {
  source: string;
  source_label: string;
  count: number;
}

export interface DeviceProfile {
  sn: string;
  fields: DeviceField[];
  counts: DeviceSourceCount[];
  total: number;
}

export interface DeviceTimelineItem {
  source: string;
  source_label: string;
  time: string;
  title: string;
  summary: string;
  amount: number | null;
  fields: DeviceField[];
}

export interface DeviceAnalysis {
  sn: string;
  range: string;
  limit: number;
  profile: DeviceProfile;
  timeline: DeviceTimelineItem[];
}

// ── Time-frame / record-count options (template: 当天…所有, N 条) ────────────

export type RangeKey = "day" | "week" | "month" | "quarter" | "half" | "year" | "all";

export const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "day", label: "当天" },
  { key: "week", label: "一周" },
  { key: "month", label: "一个月" },
  { key: "quarter", label: "三个月" },
  { key: "half", label: "半年" },
  { key: "year", label: "一年" },
  { key: "all", label: "所有" },
];

export const LIMIT_OPTIONS = [50, 100, 200, 500];

export function rangeLabel(key: string): string {
  return RANGE_OPTIONS.find((o) => o.key === key)?.label ?? key;
}

async function fetchDeviceAnalysis(
  sn: string,
  range: string,
  limit: number,
): Promise<DeviceAnalysis> {
  const params = new URLSearchParams({ sn, range, limit: String(limit) });
  const res = await apiFetch(`/api/device-analysis/profile?${params.toString()}`);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? "获取设备分析数据失败");
  }
  return res.json();
}

/** Device profile + cross-table incident timeline for one SN. */
export function useDeviceAnalysis(sn: string, range: string, limit: number, enabled: boolean) {
  return useQuery({
    queryKey: ["device-analysis", sn, range, limit],
    queryFn: () => fetchDeviceAnalysis(sn, range, limit),
    enabled,
    // The analysis is a live view — always refetch on demand
    staleTime: 0,
    retry: false,
  });
}
