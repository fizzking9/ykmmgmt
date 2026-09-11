import { apiFetch } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

// ── Types (mirror the declarative payload of GET /api/home/overview) ───────

export interface HomeKpi {
  key: string;
  label: string;
  format: "int" | "currency";
  value: number | null;
  /** Same metric for the previous day, for the day-over-day change badge. */
  prev_value: number | null;
  /** Metric polarity: whether an increase is a good thing (drives change color). */
  higher_is_better: boolean;
}

export interface HomeTrendGroup {
  key: string;
  label: string;
  series: string[];
}

export interface HomeTrendSeries {
  key: string;
  label: string;
  values: number[];
}

export interface HomeOverview {
  date: string;
  kpis: HomeKpi[];
  trend: {
    groups: HomeTrendGroup[];
    hours: string[];
    series: HomeTrendSeries[];
  };
}

async function fetchHomeOverview(date: string): Promise<HomeOverview> {
  const res = await apiFetch(`/api/home/overview?date=${encodeURIComponent(date)}`);
  if (!res.ok) throw new Error("获取看板数据失败");
  return res.json();
}

/** Fixed home-dashboard data for a single day; refetched on demand. */
export function useHomeOverview(date: string) {
  return useQuery({
    queryKey: ["home-overview", date],
    queryFn: () => fetchHomeOverview(date),
    // The board is a live view — always refetch when revisited/refreshed
    staleTime: 0,
    retry: false,
  });
}

// ── Complaint detail (投诉明细) ───────────────────────────────────────────────

export interface HomeComplaintRow {
  order_no: string | null;
  device_sn: string | null;
  register_time: string | null;
  finish_time: string | null;
  status: string | null;
  /** Not yet derived from business data — rendered as a placeholder. */
  source: string | null;
  accused_subject: string | null;
  category: string | null;
  content: string | null;
  supplement: string | null;
  handler: string | null;
}

export interface HomeComplaints {
  total: number;
  rows: HomeComplaintRow[];
}

async function fetchHomeComplaints(date: string): Promise<HomeComplaints> {
  const res = await apiFetch(`/api/home/complaints?date=${encodeURIComponent(date)}`);
  if (!res.ok) throw new Error("获取投诉明细失败");
  return res.json();
}

/** Complaint work-order rows for a single day; refetched on demand. */
export function useHomeComplaints(date: string) {
  return useQuery({
    queryKey: ["home-complaints", date],
    queryFn: () => fetchHomeComplaints(date),
    staleTime: 0,
    retry: false,
  });
}
