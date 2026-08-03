import { useQuery } from "@tanstack/react-query";

export interface TableOption {
  name: string;
  chinese_name: string;
}

async function fetchTables(): Promise<TableOption[]> {
  const res = await fetch("/api/imports/tables");
  if (!res.ok) throw new Error("获取数据表列表失败");
  const data = await res.json();
  return data.tables;
}

export function useTables() {
  return useQuery({
    queryKey: ["tables"],
    queryFn: fetchTables,
    staleTime: 60_000,
  });
}
