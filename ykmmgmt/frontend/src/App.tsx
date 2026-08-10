import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import HomePage from "@/pages/HomePage";
import UploadPage from "@/pages/UploadPage";
import ImportHistoryPage from "@/pages/ImportHistoryPage";
import DashboardPage from "@/pages/DashboardPage";
import DataBrowserPage from "@/pages/DataBrowserPage";
import ViewBuilderPage from "@/pages/ViewBuilderPage";
import ViewsListPage from "@/pages/ViewsListPage";
import VisualizationBuilderPage from "@/pages/VisualizationBuilderPage";
import VisualizationsListPage from "@/pages/VisualizationsListPage";
import VisualizationViewPage from "@/pages/VisualizationViewPage";

export default function App() {
  return (
    <>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/imports" element={<ImportHistoryPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/data-browser" element={<DataBrowserPage />} />
          <Route path="/views/builder/:id?" element={<ViewBuilderPage />} />
          <Route path="/views" element={<ViewsListPage />} />
          <Route path="/visualizations/builder/:id?" element={<VisualizationBuilderPage />} />
          <Route path="/visualizations" element={<VisualizationsListPage />} />
          <Route path="/visualizations/:id" element={<VisualizationViewPage />} />
        </Route>
      </Routes>
    </>
  );
}
