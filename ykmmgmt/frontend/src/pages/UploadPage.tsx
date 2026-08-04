import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Upload, FileUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTables } from "@/hooks/useTables";
import { useUploadFile } from "@/hooks/useUploadFile";
import { useUploadContext } from "@/contexts/UploadContext";
import { cn } from "@/lib/utils";

const ALLOWED_TYPES = [".csv", ".xlsx"];

function isValidFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_TYPES.includes(ext)) {
    return `不支持的文件类型：${ext}。仅支持 .csv 和 .xlsx 文件`;
  }
  return null;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { state, setFile, setTargetTable, setResult, setIsUploading } = useUploadContext();
  const [dragOver, setDragOver] = useState(false);

  const { data: tablesData, isLoading: tablesLoading } = useTables();
  const uploadMutation = useUploadFile();

  const selectedChineseName = tablesData?.find((t) => t.name === state.targetTable)?.chinese_name;

  const triggerWrapperRef = useRef<HTMLDivElement>(null);
  const [triggerWidth, setTriggerWidth] = useState<number>(0);

  useEffect(() => {
    const el = triggerWrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setTriggerWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleFile = useCallback(
    (f: File) => {
      const error = isValidFile(f);
      if (error) {
        toast.error(error);
        return;
      }
      setFile(f);
      setResult(null);
    },
    [setFile, setResult],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) handleFile(selected);
    },
    [handleFile],
  );

  const handleUpload = async () => {
    if (!state.file || !state.targetTable) return;
    setIsUploading(true);
    try {
      const data = await uploadMutation.mutateAsync({
        file: state.file,
        targetTable: state.targetTable,
      });
      setResult(data);
      toast.success("文件上传成功！");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "上传失败，请重试");
    } finally {
      setIsUploading(false);
    }
  };

  const canUpload = state.file && state.targetTable && !state.isUploading;

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold tracking-tight">上传数据</h2>

      {/* Drag-and-drop zone */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div
            className={cn(
              "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors",
              state.isUploading ? "pointer-events-none opacity-50" : "cursor-pointer",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50",
              state.file && "border-green-500 bg-green-50",
            )}
            onClick={() => !state.isUploading && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              if (!state.isUploading) setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            {state.file ? (
              <div className="text-center">
                <FileUp className="mx-auto mb-2 h-10 w-10 text-green-600" />
                <p className="font-medium text-green-700">{state.file.name}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {(state.file.size / 1024).toFixed(1)} KB · 点击更换文件
                </p>
              </div>
            ) : (
              <div className="text-center">
                <Upload className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
                <p className="font-medium">拖拽文件到此处，或点击选择文件</p>
                <p className="mt-1 text-sm text-muted-foreground">支持 .csv 和 .xlsx 格式</p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
        </CardContent>
      </Card>

      {/* Target table selector */}
      <Card className="mb-6 overflow-visible">
        <CardContent className="flex items-end gap-4 overflow-visible pt-6">
          <div className="flex-1" ref={triggerWrapperRef}>
            <label className="mb-2 block text-sm font-medium">目标数据表</label>
            <Select
              value={state.targetTable}
              onValueChange={(v) => {
                if (v) setTargetTable(v);
                setResult(null);
              }}
              disabled={tablesLoading || state.isUploading}
            >
              <SelectTrigger className="w-full">
                <SelectValue>
                  {selectedChineseName ?? (tablesLoading ? "加载中..." : "请选择目标数据表")}
                </SelectValue>
              </SelectTrigger>
              <SelectContent
                align="start"
                sideOffset={4}
                alignItemWithTrigger={false}
                style={triggerWidth > 0 ? { width: triggerWidth } : undefined}
              >
                {(tablesData ?? []).map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.chinese_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleUpload} disabled={!canUpload} className="min-w-[100px]">
            {state.isUploading ? (
              <>
                <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                上传中...
              </>
            ) : (
              "上传"
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Upload result */}
      {state.result && (
        <Card>
          <CardHeader>
            <CardTitle>导入结果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div>
                <p className="text-sm text-muted-foreground">目标表</p>
                <p className="font-medium">{state.result.target_table}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">总处理行数</p>
                <p className="font-medium">{state.result.total_rows}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">新增行数</p>
                <p className="font-medium text-green-600">{state.result.rows_inserted}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">更新行数</p>
                <p className="font-medium text-blue-600">{state.result.rows_updated}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">跳过行数</p>
                <p className="font-medium text-yellow-600">{state.result.rows_skipped}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">拒绝行数</p>
                <p className="font-medium text-red-600">{state.result.rows_rejected}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">清洗前/后行数</p>
                <p className="font-medium">
                  {state.result.cleaning_report.rows_before} →{" "}
                  {state.result.cleaning_report.rows_after}
                </p>
              </div>
            </div>

            {state.result.errors.length > 0 && (
              <div className="rounded-md bg-red-50 p-4">
                <p className="mb-2 text-sm font-medium text-red-700">
                  错误详情（{state.result.errors.length} 条）
                </p>
                <ul className="max-h-40 space-y-1 overflow-auto text-sm text-red-600">
                  {state.result.errors.slice(0, 10).map((err, i) => (
                    <li key={i}>
                      第 {err.row} 行：{err.error}
                    </li>
                  ))}
                  {state.result.errors.length > 10 && (
                    <li className="text-red-400">
                      ...还有 {state.result.errors.length - 10} 条错误
                    </li>
                  )}
                </ul>
              </div>
            )}

            <Button variant="outline" onClick={() => navigate("/imports")} className="mt-2">
              查看导入历史
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
