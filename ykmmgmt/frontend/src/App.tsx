import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import HomePage from "@/pages/HomePage";
import UploadPage from "@/pages/UploadPage";
import ImportHistoryPage from "@/pages/ImportHistoryPage";
import DashboardPage from "@/pages/DashboardPage";
import DataBrowserPage from "@/pages/DataBrowserPage";
import ViewBuilderPage from "@/pages/ViewBuilderPage";

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
        </Route>
      </Routes>
    </>
  );
}
