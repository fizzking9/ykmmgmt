/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react";
import type { DashboardTile, KpiTileConfig, TileType } from "@/hooks/useDashboards";

// ── State ───────────────────────────────────────────────────────────────────

export interface DashboardBuilderState {
  name: string;
  description: string;
  tiles: DashboardTile[];
  editingId: string | null;
}

const INITIAL_STATE: DashboardBuilderState = {
  name: "",
  description: "",
  tiles: [],
  editingId: null,
};

let tileSeq = 0;
function nextTileKey(): string {
  tileSeq += 1;
  return `tile-${Date.now().toString(36)}-${tileSeq}`;
}

/** Find the next free row below all existing tiles. */
function nextY(tiles: DashboardTile[]): number {
  return tiles.reduce((max, t) => Math.max(max, t.y + t.h), 0);
}

// ── Context value ───────────────────────────────────────────────────────────

export interface DashboardBuilderContextValue {
  state: DashboardBuilderState;
  setName: (name: string) => void;
  setDescription: (desc: string) => void;
  setEditingId: (id: string | null) => void;
  addTile: (tileType: TileType, payload?: Partial<DashboardTile>) => void;
  removeTile: (i: string) => void;
  updateTile: (i: string, patch: Partial<DashboardTile>) => void;
  applyLayout: (layout: { i: string; x: number; y: number; w: number; h: number }[]) => void;
  loadDashboard: (dash: {
    id: string;
    name: string;
    description: string | null;
    layout_json: DashboardTile[];
  }) => void;
  resetState: () => void;
}

const DashboardBuilderContext = createContext<DashboardBuilderContextValue | null>(null);

export function DashboardBuilderProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DashboardBuilderState>(INITIAL_STATE);

  const setName = useCallback((name: string) => {
    setState((prev) => ({ ...prev, name }));
  }, []);

  const setDescription = useCallback((description: string) => {
    setState((prev) => ({ ...prev, description }));
  }, []);

  const setEditingId = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, editingId: id }));
  }, []);

  const addTile = useCallback((tileType: TileType, payload?: Partial<DashboardTile>) => {
    setState((prev) => {
      const size =
        tileType === "visualization"
          ? { w: 6, h: 4 }
          : tileType === "kpi_card"
            ? { w: 3, h: 2 }
            : { w: 6, h: 2 };
      const tile: DashboardTile = {
        i: nextTileKey(),
        tile_type: tileType,
        x: 0,
        y: nextY(prev.tiles),
        w: size.w,
        h: size.h,
        ...payload,
      };
      return { ...prev, tiles: [...prev.tiles, tile] };
    });
  }, []);

  const removeTile = useCallback((i: string) => {
    setState((prev) => ({ ...prev, tiles: prev.tiles.filter((t) => t.i !== i) }));
  }, []);

  const updateTile = useCallback((i: string, patch: Partial<DashboardTile>) => {
    setState((prev) => ({
      ...prev,
      tiles: prev.tiles.map((t) => (t.i === i ? { ...t, ...patch } : t)),
    }));
  }, []);

  /** Merge react-grid-layout geometry (drag/resize results) back into tiles. */
  const applyLayout = useCallback(
    (layout: { i: string; x: number; y: number; w: number; h: number }[]) => {
      const byI = new Map(layout.map((l) => [l.i, l]));
      setState((prev) => ({
        ...prev,
        tiles: prev.tiles.map((t) => {
          const l = byI.get(t.i);
          return l ? { ...t, x: l.x, y: l.y, w: l.w, h: l.h } : t;
        }),
      }));
    },
    [],
  );

  const loadDashboard = useCallback(
    (dash: {
      id: string;
      name: string;
      description: string | null;
      layout_json: DashboardTile[];
    }) => {
      setState({
        name: dash.name,
        description: dash.description ?? "",
        tiles: dash.layout_json.map((t) => ({ ...t })),
        editingId: dash.id,
      });
    },
    [],
  );

  const resetState = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const value = useMemo(
    () => ({
      state,
      setName,
      setDescription,
      setEditingId,
      addTile,
      removeTile,
      updateTile,
      applyLayout,
      loadDashboard,
      resetState,
    }),
    [
      state,
      setName,
      setDescription,
      setEditingId,
      addTile,
      removeTile,
      updateTile,
      applyLayout,
      loadDashboard,
      resetState,
    ],
  );

  return (
    <DashboardBuilderContext.Provider value={value}>{children}</DashboardBuilderContext.Provider>
  );
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useDashboardBuilderContext() {
  const ctx = useContext(DashboardBuilderContext);
  if (!ctx) {
    throw new Error("useDashboardBuilderContext must be used within DashboardBuilderProvider");
  }
  return ctx;
}

export type { KpiTileConfig };
