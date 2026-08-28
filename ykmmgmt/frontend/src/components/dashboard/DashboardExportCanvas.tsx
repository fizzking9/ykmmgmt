// ── Offscreen export canvas for dashboards ──────────────────────────────────
// Renders a full dashboard (fixed 1280px width, no toolbars / time filters)
// off-screen so html2canvas can capture a standalone PNG from the dashboards
// list page. Fires onReady once the dashboard and every tile's data settled.

import { useEffect, useMemo, useRef, useState } from "react";
import { GridLayout, type LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { useDashboard, useKpiTileData, type DashboardTile } from "@/hooks/useDashboards";
import { useVisualizationTileData } from "@/hooks/useVisualizations";
import {
  KpiTileBody,
  TileLoadingBody,
  VisualizationTileBody,
} from "@/components/dashboard/DashboardTiles";
import { TextTileMarkdown } from "@/components/dashboard/TextTileMarkdown";

const EXPORT_WIDTH = 1280;
/** Delay after the last tile is ready so Recharts finishes before capture. */
const SETTLE_DELAY_MS = 500;

// ── Tile bodies with readiness tracking ─────────────────────────────────────
// Each body reports back once its query settled (errors count as settled —
// the capture then simply shows the tile's error placeholder).

function ExportVizTile({ tile, onReady }: { tile: DashboardTile; onReady: () => void }) {
  // No global time filter for exports — same default params as the display page
  const { data, isLoading } = useVisualizationTileData(tile.visualization_id ?? undefined, {});
  const notifiedRef = useRef(false);
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  });

  useEffect(() => {
    if (notifiedRef.current || isLoading) return;
    notifiedRef.current = true;
    onReadyRef.current();
  }, [isLoading]);

  if (isLoading || !data) return <TileLoadingBody />;
  return <VisualizationTileBody data={data} fill={data.chart_type !== "table"} />;
}

function ExportKpiTile({ tile, onReady }: { tile: DashboardTile; onReady: () => void }) {
  // Same query key as KpiTileBody (deduped by react-query) — used only to
  // track when the KPI value has loaded.
  const { isLoading } = useKpiTileData(tile.config?.view_id);
  const notifiedRef = useRef(false);
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  });

  useEffect(() => {
    if (notifiedRef.current || isLoading) return;
    notifiedRef.current = true;
    onReadyRef.current();
  }, [isLoading]);

  return tile.config ? <KpiTileBody config={tile.config} /> : null;
}

// ── Canvas ──────────────────────────────────────────────────────────────────

export function DashboardExportCanvas({
  dashboardId,
  onReady,
}: {
  dashboardId: string;
  /** Fires with false when the dashboard itself failed to load (export is skipped). */
  onReady: (ok: boolean) => void;
}) {
  const { data: dashboard, isLoading, isError } = useDashboard(dashboardId);
  const tiles = useMemo(() => dashboard?.layout_json ?? [], [dashboard]);
  const [readyTiles, setReadyTiles] = useState(0);
  // Set only once the timer FIRES — marking earlier would break under React
  // StrictMode (cancelled timer + ref-guarded re-run = onReady never fires),
  // and also guards against a double fire if the dashboard query refetches
  // mid-export and re-triggers this effect.
  const firedRef = useRef(false);
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  });

  // NOTE: no "reset readiness when dashboardId changes" effect here! React
  // runs CHILD effects before PARENT effects on mount, so a reset effect in
  // this component would wipe the readyTiles increments the tiles already
  // made when all data is cached (the second-export scenario) — their
  // notifiedRef guards would then block re-notifying and onReady would never
  // fire. Fresh state per dashboard is guaranteed instead by the caller
  // rendering this canvas with key={dashboard.id}.

  const dataTileCount = tiles.filter((t) => t.tile_type !== "text").length;

  useEffect(() => {
    if (isLoading) return;
    // NOTE: the error check must come before the !dashboard guard — a failed
    // query has no data, and bailing on !dashboard first would make the
    // isError branch unreachable (export would hang on load failures).
    if (isError) {
      if (firedRef.current) return;
      firedRef.current = true;
      onReadyRef.current(false);
      return;
    }
    if (!dashboard) return;
    // Text tiles render synchronously, so an empty grid or all-text dashboard
    // is ready immediately; otherwise wait for every data tile.
    if (firedRef.current) return;
    if (tiles.length === 0 || readyTiles >= dataTileCount) {
      const t = setTimeout(() => {
        firedRef.current = true;
        onReadyRef.current(true);
      }, SETTLE_DELAY_MS);
      return () => clearTimeout(t);
    }
  }, [isLoading, isError, dashboard, tiles.length, dataTileCount, readyTiles]);

  const layout: LayoutItem[] = useMemo(
    () => tiles.map((t) => ({ i: t.i, x: t.x, y: t.y, w: t.w, h: t.h })),
    [tiles],
  );

  const tileReady = () => setReadyTiles((c) => c + 1);

  if (isLoading || !dashboard) {
    return (
      <div
        className="flex items-center justify-center bg-white text-muted-foreground"
        style={{ width: EXPORT_WIDTH, height: 320 }}
      >
        加载中…
      </div>
    );
  }

  return (
    // pb-4 protects bottom-edge content from html2canvas clipping
    <div className="bg-white p-4 pb-4" style={{ width: EXPORT_WIDTH }}>
      <h2 className="text-2xl font-bold tracking-tight">{dashboard.name}</h2>
      {dashboard.description && (
        <p className="mt-1 mb-4 text-sm text-muted-foreground">{dashboard.description}</p>
      )}
      <GridLayout
        width={EXPORT_WIDTH - 32}
        layout={layout}
        gridConfig={{ cols: 12, rowHeight: 80, margin: [12, 12] }}
        dragConfig={{ enabled: false }}
        resizeConfig={{ enabled: false }}
      >
        {tiles.map((tile) => (
          <div key={tile.i}>
            {/* Read-only tile frame (no hover toolbar — this is a capture) */}
            <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-background shadow-sm">
              <div className="min-h-0 flex-1">
                {tile.tile_type === "visualization" ? (
                  <ExportVizTile tile={tile} onReady={tileReady} />
                ) : tile.tile_type === "kpi_card" ? (
                  <ExportKpiTile tile={tile} onReady={tileReady} />
                ) : (
                  <TextTileMarkdown content={tile.content ?? ""} />
                )}
              </div>
            </div>
          </div>
        ))}
      </GridLayout>
    </div>
  );
}
