import { useQuery } from "@tanstack/react-query";

export interface ImportJobItem {
  id: number;
  file_name: string;
  target_table: string;
  status: string;
  total_rows: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  rows_rejected: number;
  created_at: string;
}

interface ImportHistoryResponse {
  items: ImportJobItem[];
  page: number;
  page_size: number;
  total: number;
}

async function fetchImportHistory(page: number, pageSize: number): Promise<ImportHistoryResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const res = await fetch(`/api/imports?${params}`);
  if (!res.ok) throw new Error("获取导入历史失败");
  return res.json();
}

export function useImportHistory(page: number = 1, pageSize: number = 20) {
  return useQuery({
    queryKey: ["importHistory", page, pageSize],
    queryFn: () => fetchImportHistory(page, pageSize),
    staleTime: 10_000,
  });
}
