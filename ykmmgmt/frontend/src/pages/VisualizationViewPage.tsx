import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useVisualization, useVisualizationData } from "@/hooks/useVisualizations";
import { CHART_TYPES, type ChartType } from "@/contexts/VisualizationBuilderContext";
import { VisualizationRenderer } from "@/components/visualization/VisualizationRenderer";
import { ArrowLeft, RefreshCw, Loader2, Eye } from "lucide-react";

export default function VisualizationViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: viz,
    isLoading: vizLoading,
    isError: vizError,
  } = useVisualization(id);
  const {
    data,
    isLoading: dataLoading,
    isFetching,
    isError: dataError,
    error: dataFetchError,
    refetch,
  } = useVisualizationData(id);

  // Manual refresh — the ONLY way data is re-fetched (no auto-refresh/polling)
  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["visualizationData", id] });
  };

  const chartTypeLabel =
    CHART_TYPES.find((ct) => ct.value === viz?.chart_type)?.label ?? viz?.chart_type;

  if (vizLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[480px] w-full" />
      </div>
    );
  }

  // Not found (GET /api/visualizations/{id} returned an error)
  if (vizError || !viz) {
    return (
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate("/visualizations")}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回可视化列表
        </Button>
        <div className="mt-8 rounded-md bg-muted/30 p-16 text-center">
          <Eye className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg text-muted-foreground">可视化不存在</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/visualizations")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-2xl font-bold tracking-tight">{viz.name}</h2>
          {chartTypeLabel && <Badge variant="secondary">{chartTypeLabel}</Badge>}
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isFetching}>
          {isFetching ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          刷新
        </Button>
      </div>

      {/* Body */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">数据展示</CardTitle>
        </CardHeader>
        <CardContent>
          {dataLoading || !data ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : dataError ? (
            <div className="rounded-md bg-red-50 p-8 text-center">
              <p className="mb-4 text-red-700">
                数据加载失败：
                {dataFetchError instanceof Error ? dataFetchError.message : "未知错误"}
              </p>
              <Button variant="outline" onClick={() => refetch()}>
                重试
              </Button>
            </div>
          ) : (
            <VisualizationRenderer
              chartType={viz.chart_type as ChartType}
              config={data.config_json}
              columns={data.columns}
              rows={data.rows}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
