/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import type { JoinSpec, PreviewResponse } from "@/hooks/useViews";

// ── Column alias ──────────────────────────────────────────────────────────

export interface ColumnAlias {
  table: string;
  column: string;
  alias: string;
}

// ── Filter ────────────────────────────────────────────────────────────────

export interface FilterItem {
  column: string;
  operator: string;
  value: string;
}

// ── Aggregation ───────────────────────────────────────────────────────────

export interface AggregationItem {
  function: string;
  column: string;
  alias: string;
}

// ── Computed column ────────────────────────────────────────────────────────

export interface ComputedOperandItem {
  type: "column" | "constant";
  table: string;
  column: string;
  value: string;
}

export interface ComputedColumnItem {
  alias: string;
  expression_type: "arithmetic" | "datetime_shift";
  // Arithmetic (chained)
  operands: ComputedOperandItem[];
  operators: string[];
  // Datetime shift
  base_table: string;
  base_column: string;
  shift_value: string;
  shift_unit: string;
}

// ── State ─────────────────────────────────────────────────────────────────

export interface ViewBuilderState {
  name: string;
  description: string;
  fromTables: string[];
  joins: JoinSpec[];
  columns: ColumnAlias[];
  filters: FilterItem[];
  groupBy: string[];
  aggregations: AggregationItem[];
  computedColumns: ComputedColumnItem[];
  selectedComputedColumns: string[];
  previewResult: PreviewResponse | null;
  previewTab: "data" | "sql";
  editingId: string | null;
}

// ── Context value ─────────────────────────────────────────────────────────

export interface ViewBuilderContextValue {
  state: ViewBuilderState;
  setName: (name: string) => void;
  setDescription: (desc: string) => void;
  setFromTables: (tables: string[]) => void;
  setJoins: (joins: JoinSpec[]) => void;
  setColumns: (cols: ColumnAlias[]) => void;
  setFilters: (filters: FilterItem[]) => void;
  setGroupBy: (cols: string[]) => void;
  setAggregations: (aggs: AggregationItem[]) => void;
  setComputedColumns: (cols: ComputedColumnItem[]) => void;
  setSelectedComputedColumns: (cols: string[]) => void;
  setPreviewResult: (result: PreviewResponse | null) => void;
  setPreviewTab: (tab: "data" | "sql") => void;
  setEditingId: (id: string | null) => void;
  resetState: () => void;
  clearConfig: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────

const ViewBuilderContext = createContext<ViewBuilderContextValue | null>(null);

const INITIAL_STATE: ViewBuilderState = {
  name: "",
  description: "",
  fromTables: [],
  joins: [],
  columns: [],
  filters: [],
  groupBy: [],
  aggregations: [],
  computedColumns: [],
  selectedComputedColumns: [],
  previewResult: null,
  previewTab: "data",
  editingId: null,
};

export function ViewBuilderProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ViewBuilderState>(INITIAL_STATE);

  const setName = useCallback((name: string) => {
    setState((prev) => ({ ...prev, name }));
  }, []);
  const setDescription = useCallback((desc: string) => {
    setState((prev) => ({ ...prev, description: desc }));
  }, []);
  const setFromTables = useCallback((tables: string[]) => {
    setState((prev) => ({ ...prev, fromTables: tables, previewResult: null }));
  }, []);
  const setJoins = useCallback((joins: JoinSpec[]) => {
    setState((prev) => ({ ...prev, joins, previewResult: null }));
  }, []);
  const setColumns = useCallback((cols: ColumnAlias[]) => {
    setState((prev) => ({ ...prev, columns: cols, previewResult: null }));
  }, []);
  const setFilters = useCallback((filters: FilterItem[]) => {
    setState((prev) => ({ ...prev, filters, previewResult: null }));
  }, []);
  const setGroupBy = useCallback((cols: string[]) => {
    setState((prev) => ({ ...prev, groupBy: cols, previewResult: null }));
  }, []);
  const setAggregations = useCallback((aggs: AggregationItem[]) => {
    setState((prev) => ({ ...prev, aggregations: aggs, previewResult: null }));
  }, []);
  const setComputedColumns = useCallback((cols: ComputedColumnItem[]) => {
    setState((prev) => ({ ...prev, computedColumns: cols, previewResult: null }));
  }, []);
  const setSelectedComputedColumns = useCallback((cols: string[]) => {
    setState((prev) => ({ ...prev, selectedComputedColumns: cols, previewResult: null }));
  }, []);
  const setPreviewResult = useCallback((result: PreviewResponse | null) => {
    setState((prev) => ({ ...prev, previewResult: result }));
  }, []);
  const setPreviewTab = useCallback((tab: "data" | "sql") => {
    setState((prev) => ({ ...prev, previewTab: tab }));
  }, []);
  const setEditingId = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, editingId: id }));
  }, []);
  const resetState = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);
  const clearConfig = useCallback(() => {
    setState((prev) => ({
      ...prev,
      fromTables: [],
      joins: [],
      columns: [],
      filters: [],
      groupBy: [],
      aggregations: [],
      computedColumns: [],
      selectedComputedColumns: [],
      previewResult: null,
      editingId: null,
    }));
  }, []);

  const value = useMemo(() => ({
    state,
    setName,
    setDescription,
    setFromTables,
    setJoins,
    setColumns,
    setFilters,
    setGroupBy,
    setAggregations,
    setComputedColumns,
    setSelectedComputedColumns,
    setPreviewResult,
    setPreviewTab,
    setEditingId,
    resetState,
    clearConfig,
  }), [state, setName, setDescription, setFromTables, setJoins, setColumns, setFilters, setGroupBy, setAggregations, setComputedColumns, setSelectedComputedColumns, setPreviewResult, setPreviewTab, setEditingId, resetState, clearConfig]);

  return (
    <ViewBuilderContext.Provider
      value={value}
    >
      {children}
    </ViewBuilderContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useViewBuilderContext() {
  const ctx = useContext(ViewBuilderContext);
  if (!ctx) {
    throw new Error(
      "useViewBuilderContext must be used within ViewBuilderProvider",
    );
  }
  return ctx;
}
