import { useQuery } from "@tanstack/react-query";

export interface TableOption {
  name: string;
  chinese_name: string;
}

async function fetchTables(): Promise<TableOption[]> {
  const res = await fetch("/api/tables");
  if (!res.ok) throw new Error("获取数据表列表失败");
  return res.json();
}

export function useTables() {
  return useQuery({
    queryKey: ["tables"],
    queryFn: fetchTables,
    staleTime: 60_000,
  });
}
