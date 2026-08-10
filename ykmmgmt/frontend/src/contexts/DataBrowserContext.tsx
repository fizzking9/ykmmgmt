/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export interface ColumnFilter {
  col: string;
  value: string;
  mode: "contains" | "exact";
}

interface DataBrowserState {
  selectedTable: string;
  page: number;
  filterCol: string;
  filterStart: string;
  filterEnd: string;
  columnFilters: ColumnFilter[];
  sortCol: string;
  sortDir: "asc" | "desc";
}

interface DataBrowserContextValue {
  state: DataBrowserState;
  setSelectedTable: (table: string) => void;
  setPage: (page: number) => void;
  setFilterCol: (col: string) => void;
  setFilterStart: (start: string) => void;
  setFilterEnd: (end: string) => void;
  addColumnFilter: () => void;
  updateColumnFilter: (index: number, patch: Partial<ColumnFilter>) => void;
  removeColumnFilter: (index: number) => void;
  setSortCol: (col: string) => void;
  setSortDir: (dir: "asc" | "desc") => void;
  clearFilter: () => void;
  reset: () => void;
}

const DataBrowserContext = createContext<DataBrowserContextValue | null>(null);

const EMPTY_FILTER: ColumnFilter = { col: "", value: "", mode: "contains" };

export function DataBrowserProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DataBrowserState>({
    selectedTable: "",
    page: 1,
    filterCol: "",
    filterStart: "",
    filterEnd: "",
    columnFilters: [],
    sortCol: "",
    sortDir: "asc",
  });

  const setSelectedTable = useCallback((table: string) => {
    setState({
      selectedTable: table,
      page: 1,
      filterCol: "",
      filterStart: "",
      filterEnd: "",
      columnFilters: [],
      sortCol: "",
      sortDir: "asc",
    });
  }, []);

  const setPage = useCallback((page: number) => {
    setState((prev) => ({ ...prev, page }));
  }, []);

  const setFilterCol = useCallback((col: string) => {
    setState((prev) => ({ ...prev, filterCol: col }));
  }, []);

  const setFilterStart = useCallback((start: string) => {
    setState((prev) => ({ ...prev, filterStart: start }));
  }, []);

  const setFilterEnd = useCallback((end: string) => {
    setState((prev) => ({ ...prev, filterEnd: end }));
  }, []);

  const addColumnFilter = useCallback(() => {
    setState((prev) => ({
      ...prev,
      columnFilters: [...prev.columnFilters, { ...EMPTY_FILTER }],
    }));
  }, []);

  const updateColumnFilter = useCallback((index: number, patch: Partial<ColumnFilter>) => {
    setState((prev) => {
      const updated = prev.columnFilters.map((f, i) => (i === index ? { ...f, ...patch } : f));
      return { ...prev, columnFilters: updated };
    });
  }, []);

  const removeColumnFilter = useCallback((index: number) => {
    setState((prev) => ({
      ...prev,
      columnFilters: prev.columnFilters.filter((_, i) => i !== index),
    }));
  }, []);

  const setSortCol = useCallback((col: string) => {
    setState((prev) => ({ ...prev, sortCol: col }));
  }, []);

  const setSortDir = useCallback((dir: "asc" | "desc") => {
    setState((prev) => ({ ...prev, sortDir: dir }));
  }, []);

  const clearFilter = useCallback(() => {
    setState((prev) => ({
      ...prev,
      page: 1,
      filterCol: "",
      filterStart: "",
      filterEnd: "",
      columnFilters: [],
    }));
  }, []);

  const reset = useCallback(() => {
    setState({
      selectedTable: "",
      page: 1,
      filterCol: "",
      filterStart: "",
      filterEnd: "",
      columnFilters: [],
      sortCol: "",
      sortDir: "asc",
    });
  }, []);

  return (
    <DataBrowserContext.Provider
      value={{
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
        reset,
      }}
    >
      {children}
    </DataBrowserContext.Provider>
  );
}

export function useDataBrowserContext() {
  const ctx = useContext(DataBrowserContext);
  if (!ctx) {
    throw new Error("useDataBrowserContext must be used within DataBrowserProvider");
  }
  return ctx;
}
