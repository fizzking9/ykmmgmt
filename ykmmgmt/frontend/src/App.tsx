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
import DashboardBuilderPage from "@/pages/DashboardBuilderPage";
import DashboardDisplayPage from "@/pages/DashboardDisplayPage";
import DashboardsListPage from "@/pages/DashboardsListPage";
import SchemaTablesPage from "@/pages/SchemaTablesPage";
import SchemaCreateTablePage from "@/pages/SchemaCreateTablePage";
import SchemaTableDetailPage from "@/pages/SchemaTableDetailPage";

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
          <Route path="/dashboards/builder/:id?" element={<DashboardBuilderPage />} />
          <Route path="/dashboards" element={<DashboardsListPage />} />
          <Route path="/dashboards/:id" element={<DashboardDisplayPage />} />
          <Route path="/schema" element={<SchemaTablesPage />} />
          <Route path="/schema/create" element={<SchemaCreateTablePage />} />
          <Route path="/schema/tables/:name" element={<SchemaTableDetailPage />} />
        </Route>
      </Routes>
    </>
  );
}
