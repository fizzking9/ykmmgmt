/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { DeviceAnalysisDialog } from "@/components/analysis/DeviceAnalysisDialog";

/**
 * Global 设备分析 dialog access.
 *
 * The dialog is rendered once here so any page (the top-bar tag, the home
 * page's 投诉明细 SN links, …) can open it — optionally pre-filled with a
 * device SN and auto-submitted so the caller lands straight on the results.
 */
interface DeviceAnalysisContextValue {
  openDeviceAnalysis: (sn?: string) => void;
}

const DeviceAnalysisContext = createContext<DeviceAnalysisContextValue | null>(null);

export function DeviceAnalysisProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [initialSn, setInitialSn] = useState("");

  const openDeviceAnalysis = useCallback((sn?: string) => {
    setInitialSn(sn?.trim() ?? "");
    setOpen(true);
  }, []);

  const value = useMemo(() => ({ openDeviceAnalysis }), [openDeviceAnalysis]);

  return (
    <DeviceAnalysisContext.Provider value={value}>
      {children}
      <DeviceAnalysisDialog open={open} initialSn={initialSn} onClose={() => setOpen(false)} />
    </DeviceAnalysisContext.Provider>
  );
}

export function useDeviceAnalysisContext(): DeviceAnalysisContextValue {
  const ctx = useContext(DeviceAnalysisContext);
  if (!ctx) {
    throw new Error("useDeviceAnalysisContext must be used within DeviceAnalysisProvider");
  }
  return ctx;
}
