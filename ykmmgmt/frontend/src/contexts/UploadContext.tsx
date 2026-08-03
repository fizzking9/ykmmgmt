/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { UploadResult } from "@/hooks/useUploadFile";

interface UploadState {
  file: File | null;
  targetTable: string;
  result: UploadResult | null;
  isUploading: boolean;
}

interface UploadContextValue {
  state: UploadState;
  setFile: (file: File | null) => void;
  setTargetTable: (table: string) => void;
  setResult: (result: UploadResult | null) => void;
  setIsUploading: (uploading: boolean) => void;
  clearState: () => void;
}

const UploadContext = createContext<UploadContextValue | null>(null);

export function UploadProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UploadState>({
    file: null,
    targetTable: "",
    result: null,
    isUploading: false,
  });

  const setFile = useCallback((file: File | null) => {
    setState((prev) => ({ ...prev, file, result: null }));
  }, []);

  const setTargetTable = useCallback((table: string) => {
    setState((prev) => ({ ...prev, targetTable: table, result: null }));
  }, []);

  const setResult = useCallback((result: UploadResult | null) => {
    setState((prev) => ({ ...prev, result }));
  }, []);

  const setIsUploading = useCallback((uploading: boolean) => {
    setState((prev) => ({ ...prev, isUploading: uploading }));
  }, []);

  const clearState = useCallback(() => {
    setState({ file: null, targetTable: "", result: null, isUploading: false });
  }, []);

  return (
    <UploadContext.Provider
      value={{ state, setFile, setTargetTable, setResult, setIsUploading, clearState }}
    >
      {children}
    </UploadContext.Provider>
  );
}

export function useUploadContext() {
  const ctx = useContext(UploadContext);
  if (!ctx) {
    throw new Error("useUploadContext must be used within UploadProvider");
  }
  return ctx;
}
