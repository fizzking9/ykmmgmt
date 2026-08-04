import { useMutation } from "@tanstack/react-query";

export interface UploadResult {
  import_job_id: number;
  target_table: string;
  status: string;
  total_rows: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped: number;
  rows_rejected: number;
  cleaning_report: {
    steps: string[];
    warnings_per_column: Record<string, string[]>;
    rows_before: number;
    rows_after: number;
  };
  errors: Array<{ row: number; error: string }>;
}

async function uploadFile(file: File, targetTable: string): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("target_table", targetTable);

  const res = await fetch("/api/imports", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail ?? "上传失败");
  }

  return res.json();
}

export function useUploadFile() {
  return useMutation({
    mutationFn: ({ file, targetTable }: { file: File; targetTable: string }) =>
      uploadFile(file, targetTable),
  });
}
