import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useTables, TableOption } from "@/hooks/useTables";
import { useDataBrowserContext, type ColumnFilter } from "@/contexts/DataBrowserContext";
import { Database, ChevronLeft, ChevronRight, ArrowUp, ArrowDown, Plus, X } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface ColumnInfo {
  name: string;
  type: string;
  label: string;
}

interface TableDataResponse {
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  size: number;
}

// ── API helpers ────────────────────────────────────────────────────────────

async function fetchSchema(tableName: string): Promise<ColumnInfo[]> {
  const res = await fetch(`/api/tables/${tableName}/schema`);
  if (!res.ok) throw new Error("获取表结构失败");
  return res.json();
}

async function fetchData(
  tableName: string,
  page: number,
  size: number,
  datetimeCol?: string,
  start?: string,
  end?: string,
  columnFilters?: ColumnFilter[],
  sortCol?: string,
  sortDir?: string,
): Promise<TableDataResponse> {
  const params = new URLSearchParams({
    page: String(page),
    size: String(size),
  });
  if (datetimeCol) params.set("datetime_col", datetimeCol);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (columnFilters) {
    for (const f of columnFilters) {
      if (f.col && f.value) {
        params.append("filter_col", f.col);
        params.append("filter_value", f.value);
        params.append("filter_mode", f.mode);
      }
    }
  }
  if (sortCol) params.set("sort_col", sortCol);
  if (sortDir) params.set("sort_dir", sortDir);
  const res = await fetch(`/api/tables/${tableName}/data?${params}`);
  if (!res.ok) throw new Error("获取数据失败");
  return res.json();
}

function isDatetimeColumn(col: ColumnInfo): boolean {
  return col.type.toLowerCase().includes("datetime");
}

// ── Sub-components ─────────────────────────────────────────────────────────

function LoadingSkeleton({ cols }: { cols: number }) {
  return Array.from({ length: 5 }).map((_, i) => (
    <TableRow key={i}>
      {Array.from({ length: cols }).map((_, j) => (
        <TableCell key={j}>
          <Skeleton className="h-5 w-full" />
        </TableCell>
      ))}
    </TableRow>
  ));
}

function EmptyState() {
  return (
    <div className="rounded-md bg-muted/30 p-16 text-center">
      <Database className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
      <p className="text-lg text-muted-foreground">暂无数据</p>
      <p className="mt-1 text-sm text-muted-foreground">当前筛选条件下没有匹配的数据</p>
    </div>
  );
}

function NoTableSelected() {
  return (
    <div className="rounded-md bg-muted/30 p-16 text-center">
      <Database className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
      <p className="text-lg text-muted-foreground">请选择一个数据表</p>
      <p className="mt-1 text-sm text-muted-foreground">从左侧列表中选择要浏览的数据表</p>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function DataBrowserPage() {
  const {
    state,
    setSelectedTable,
    setPage,
    setFilterCol,
    setFilterStart,
    setFilterEnd,
    addColumnFilter,
    updateColumnFilter,
    removeColumnFilter,
    setSortCol,
    setSortDir,
    clearFilter,
  } = useDataBrowserContext();
  const {
    selectedTable,
    page,
    filterCol,
    filterStart,
    filterEnd,
    columnFilters,
    sortCol,
    sortDir,
  } = state;

  const { data: tables, isLoading: tablesLoading } = useTables();

  // ── Select dropdown width tracking (same pattern as UploadPage) ────────
  const filterTriggerRef = useRef<HTMLDivElement>(null);
  const [filterColWidth, setFilterColWidth] = useState<number>(0);

  useEffect(() => {
    const el = filterTriggerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setFilterColWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Column filter Select width tracking (use a shared width from first row)
  const colFilterTriggerRef = useRef<HTMLDivElement>(null);
  const [colFilterWidth, setColFilterWidth] = useState<number>(0);

  useEffect(() => {
    const el = colFilterTriggerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setColFilterWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [columnFilters.length]);

  // Schema query
  const { data: schema, isLoading: schemaLoading } = useQuery({
    queryKey: ["tableSchema", selectedTable],
    queryFn: () => fetchSchema(selectedTable),
    enabled: !!selectedTable,
    staleTime: 60_000,
  });

  const datetimeColumns = (schema ?? []).filter(isDatetimeColumn);

  // Determine active datetime filter params (supports start-only, end-only, or both)
  const activeFilterCol = filterCol && (filterStart || filterEnd) ? filterCol : undefined;
  const activeStart = filterCol && filterStart ? filterStart : undefined;
  const activeEnd = filterCol && filterEnd ? filterEnd : undefined;

  // Data query
  const {
    data: tableData,
    isLoading: dataLoading,
    isError,
    error,
    isPlaceholderData,
  } = useQuery({
    queryKey: [
      "tableData",
      selectedTable,
      page,
      activeFilterCol,
      activeStart,
      activeEnd,
      columnFilters,
      sortCol,
      sortDir,
    ],
    queryFn: () =>
      fetchData(
        selectedTable,
        page,
        20,
        activeFilterCol,
        activeStart,
        activeEnd,
        columnFilters,
        sortCol,
        sortDir,
      ),
    enabled: !!selectedTable,
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  });

  const totalPages = tableData ? Math.ceil(tableData.total / tableData.size) : 0;

  // Handlers
  function handleTableChange(tableName: string) {
    setSelectedTable(tableName);
  }

  function handleApplyFilter() {
    setPage(1);
  }

  function handleClearFilter() {
    clearFilter();
  }

  // ── Preserve scroll position on sort / page change ────────────────────
  const scrollPosRef = useRef<number>(0);

  useLayoutEffect(() => {
    const main = document.querySelector("main");
    if (main && scrollPosRef.current > 0) {
      main.scrollTop = scrollPosRef.current;
    }
  }, [tableData]);

  function handleSortClick(colName: string) {
    const main = document.querySelector("main");
    scrollPosRef.current = main?.scrollTop ?? 0;
    if (sortCol !== colName) {
      setSortCol(colName);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol("");
      setSortDir("asc");
    }
  }

  function handleApplyColumnFilters() {
    setPage(1);
  }

  function handlePageInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val) && val >= 1 && val <= totalPages) {
      scrollPosRef.current = 0;
      setPage(val);
    }
  }

  const showFilter = datetimeColumns.length > 0 && !!selectedTable;
  const isLoading = schemaLoading || dataLoading;

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold tracking-tight">数据浏览</h2>

      <div className="flex gap-6">
        {/* Left: Table Listbox */}
        <div className="w-64 shrink-0">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">数据表</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {tablesLoading ? (
                <div className="space-y-1 p-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col">
                  {(tables ?? []).map((t: TableOption) => (
                    <button
                      key={t.name}
                      type="button"
                      onClick={() => handleTableChange(t.name)}
                      className={cn(
                        "px-4 py-3 text-left text-sm transition-colors hover:bg-accent",
                        "border-l-2",
                        selectedTable === t.name
                          ? "border-l-primary bg-accent font-medium"
                          : "border-l-transparent",
                      )}
                    >
                      {t.chinese_name}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Record count */}
          {selectedTable && tableData && (
            <p className="mt-3 text-center text-sm text-muted-foreground">
              共 {tableData.total} 条记录
            </p>
          )}
        </div>

        {/* Right: Filter + Data */}
        <div className="min-w-0 flex-1">
          {!selectedTable ? (
            <NoTableSelected />
          ) : (
            <>
              {/* Datetime filter — on top of data */}
              {showFilter && (
                <Card className="mb-6 overflow-visible">
                  <CardHeader>
                    <CardTitle className="text-base">时间筛选</CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-visible">
                    <div className="flex flex-wrap items-end gap-4 overflow-visible">
                      <div ref={filterTriggerRef}>
                        <label className="mb-1 block text-sm font-medium">时间列</label>
                        <Select value={filterCol} onValueChange={(v) => v && setFilterCol(v)}>
                          <SelectTrigger>
                            <SelectValue>
                              {datetimeColumns.find((c) => c.name === filterCol)?.label ??
                                "选择时间列"}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent
                            align="start"
                            sideOffset={4}
                            alignItemWithTrigger={false}
                            className="bg-background"
                            style={filterColWidth > 0 ? { width: filterColWidth } : undefined}
                          >
                            {datetimeColumns.map((col) => (
                              <SelectItem key={col.name} value={col.name}>
                                {col.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">起始日期</label>
                        <input
                          type="date"
                          value={filterStart}
                          onChange={(e) => setFilterStart(e.target.value)}
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium">结束日期</label>
                        <input
                          type="date"
                          value={filterEnd}
                          onChange={(e) => setFilterEnd(e.target.value)}
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        />
                      </div>
                      <Button
                        onClick={handleApplyFilter}
                        disabled={!filterCol || (!filterStart && !filterEnd)}
                      >
                        应用筛选
                      </Button>
                      {activeFilterCol && (
                        <Button variant="outline" onClick={handleClearFilter}>
                          清除筛选
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Column value filter */}
              {selectedTable && (
                <Card className="mb-6 overflow-visible">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">筛选条件</CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-visible">
                    {columnFilters.length === 0 ? (
                      <p className="mb-3 text-sm text-muted-foreground">未添加筛选条件</p>
                    ) : (
                      <div className="mb-3 space-y-3">
                        {columnFilters.map((f, i) => (
                          <div key={i} className="flex items-end gap-3">
                            <div className="w-40">
                              <label className="mb-1 block text-xs font-medium">列</label>
                              <div ref={i === 0 ? colFilterTriggerRef : undefined}>
                                <Select
                                  value={f.col}
                                  onValueChange={(v) => v && updateColumnFilter(i, { col: v })}
                                >
                                  <SelectTrigger>
                                    <SelectValue>
                                      {schema?.find((c) => c.name === f.col)?.label ?? "选择列"}
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent
                                    align="start"
                                    sideOffset={4}
                                    alignItemWithTrigger={false}
                                    className="bg-background"
                                    style={
                                      colFilterWidth > 0 ? { width: colFilterWidth } : undefined
                                    }
                                  >
                                    {(schema ?? []).map((col) => (
                                      <SelectItem key={col.name} value={col.name}>
                                        {col.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                            <div className="w-20">
                              <label className="mb-1 block text-xs font-medium">模式</label>
                              <Select
                                value={f.mode}
                                onValueChange={(v) =>
                                  updateColumnFilter(i, { mode: v as "contains" | "exact" })
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue>
                                    {f.mode === "contains" ? "包含" : "精确"}
                                  </SelectValue>
                                </SelectTrigger>
                                <SelectContent
                                  align="start"
                                  sideOffset={4}
                                  alignItemWithTrigger={false}
                                  className="bg-background"
                                >
                                  <SelectItem value="contains">包含</SelectItem>
                                  <SelectItem value="exact">精确</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="flex-1">
                              <label className="mb-1 block text-xs font-medium">值</label>
                              <input
                                type="text"
                                value={f.value}
                                onChange={(e) => updateColumnFilter(i, { value: e.target.value })}
                                placeholder="输入筛选值"
                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                              />
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="shrink-0"
                              onClick={() => removeColumnFilter(i)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={addColumnFilter}>
                        <Plus className="mr-1 h-4 w-4" />
                        添加筛选条件
                      </Button>
                      {columnFilters.length > 0 && (
                        <Button size="sm" onClick={handleApplyColumnFilters}>
                          应用筛选
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Data table */}
              {isError ? (
                <div className="rounded-md bg-red-50 p-8 text-center">
                  <p className="mb-4 text-red-700">
                    加载失败：
                    {error instanceof Error ? error.message : "未知错误"}
                  </p>
                </div>
              ) : (
                <Card>
                  <CardContent className="pt-6">
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            {schema &&
                              schema.map((col) => {
                                const isSorted = sortCol === col.name;
                                return (
                                  <TableHead
                                    key={col.name}
                                    className="cursor-pointer select-none whitespace-nowrap hover:bg-muted/50"
                                    onClick={() => handleSortClick(col.name)}
                                  >
                                    <span className="inline-flex items-center gap-1">
                                      {col.label}
                                      {isSorted && sortDir === "asc" && (
                                        <ArrowUp className="h-3 w-3" />
                                      )}
                                      {isSorted && sortDir === "desc" && (
                                        <ArrowDown className="h-3 w-3" />
                                      )}
                                    </span>
                                  </TableHead>
                                );
                              })}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {isLoading && schema ? (
                            <LoadingSkeleton cols={schema.length} />
                          ) : tableData && tableData.rows.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={schema?.length ?? 1} className="p-0">
                                <EmptyState />
                              </TableCell>
                            </TableRow>
                          ) : (
                            tableData?.rows.map((row, i) => (
                              <TableRow key={i}>
                                {schema?.map((col) => (
                                  <TableCell
                                    key={col.name}
                                    className="max-w-[300px] truncate"
                                    title={String(row[col.name] ?? "")}
                                  >
                                    {row[col.name] != null ? String(row[col.name]) : ""}
                                  </TableCell>
                                ))}
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    </div>

                    {/* Pagination */}
                    {tableData && totalPages > 1 && (
                      <div className="mt-4 flex items-center justify-between">
                        <p className="text-sm text-muted-foreground">
                          共 {tableData.total} 条记录，第{" "}
                          <input
                            type="number"
                            min={1}
                            max={totalPages}
                            value={tableData.page}
                            onChange={handlePageInputChange}
                            className="inline w-16 rounded border px-1 py-0.5 text-center text-sm"
                          />{" "}
                          / {totalPages} 页
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1}
                            onClick={() => {
                              scrollPosRef.current = 0;
                              setPage(Math.max(1, page - 1));
                            }}
                          >
                            <ChevronLeft className="mr-1 h-4 w-4" />
                            上一页
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages}
                            onClick={() => {
                              scrollPosRef.current = 0;
                              setPage(page + 1);
                            }}
                          >
                            下一页
                            <ChevronRight className="ml-1 h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Single-page pagination info */}
                    {tableData && totalPages <= 1 && (
                      <div className="mt-4">
                        <p className="text-sm text-muted-foreground">
                          共 {tableData.total} 条记录，第 {tableData.page} 页
                        </p>
                      </div>
                    )}

                    {/* Skeleton overlay for page transitions */}
                    {isPlaceholderData && (
                      <div className="mt-1 text-center text-xs text-muted-foreground">
                        正在加载...
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
