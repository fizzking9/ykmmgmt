import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import UploadPage from "@/pages/UploadPage";
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
import UsersPage from "@/pages/UsersPage";

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

/** Blocks anonymous access; remembers the requested path for post-login redirect. */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <>
      <Toaster position="top-right" richColors />
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
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
          <Route path="/users" element={<UsersPage />} />
        </Route>

        {/* Fallback — unknown paths redirect home (which itself requires auth) */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
