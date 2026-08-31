import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UploadProvider } from "@/contexts/UploadContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { DataBrowserProvider } from "@/contexts/DataBrowserContext";
import { ViewBuilderProvider } from "@/contexts/ViewBuilderContext";
import { VisualizationBuilderProvider } from "@/contexts/VisualizationBuilderContext";
import { DashboardBuilderProvider } from "@/contexts/DashboardBuilderContext";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <UploadProvider>
          <DataBrowserProvider>
            <ViewBuilderProvider>
              <VisualizationBuilderProvider>
                <DashboardBuilderProvider>
                  <App />
                </DashboardBuilderProvider>
              </VisualizationBuilderProvider>
            </ViewBuilderProvider>
          </DataBrowserProvider>
        </UploadProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
