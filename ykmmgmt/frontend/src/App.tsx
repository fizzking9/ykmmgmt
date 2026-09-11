import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout } from "@/components/layout/AppLayout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useAuth } from "@/contexts/AuthContext";
import { DeviceAnalysisProvider } from "@/contexts/DeviceAnalysisContext";
import { Loader2 } from "lucide-react";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import UploadPage from "@/pages/UploadPage";
import DashboardPage from "@/pages/DashboardPage";
import DataBrowserPage from "@/pages/DataBrowserPage";
import ViewsListPage from "@/pages/ViewsListPage";
import VisualizationsListPage from "@/pages/VisualizationsListPage";
import VisualizationViewPage from "@/pages/VisualizationViewPage";
import DashboardDisplayPage from "@/pages/DashboardDisplayPage";
import DashboardsListPage from "@/pages/DashboardsListPage";
import SchemaTablesPage from "@/pages/SchemaTablesPage";
import SchemaCreateTablePage from "@/pages/SchemaCreateTablePage";
import SchemaTableDetailPage from "@/pages/SchemaTableDetailPage";
import UsersPage from "@/pages/UsersPage";
import ProfilePage from "@/pages/ProfilePage";
import NotFoundPage from "@/pages/NotFoundPage";

// Route-level code-splitting for the two oversized builder pages
// (VisualizationBuilderPage ~143 KB, ViewBuilderPage ~101 KB) so they leave
// the initial bundle and load on demand.
const VisualizationBuilderPage = lazy(() => import("@/pages/VisualizationBuilderPage"));
const ViewBuilderPage = lazy(() => import("@/pages/ViewBuilderPage"));
const DashboardBuilderPage = lazy(() => import("@/pages/DashboardBuilderPage"));
const WelcomePage = lazy(() => import("@/pages/WelcomePage"));

function FullPageSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

function LazyFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

/** Black placeholder while the lazy welcome chunk loads — avoids a white flash. */
function SplashFallback() {
  return <div className="min-h-dvh w-full bg-black" />;
}

/** Public splash: already-authenticated users are sent straight into the app. */
function WelcomeRoute() {
  const { user, loading } = useAuth();
  if (loading) return <SplashFallback />;
  if (user) return <Navigate to="/" replace />;
  return (
    <Suspense fallback={<SplashFallback />}>
      <WelcomePage />
    </Suspense>
  );
}

/** Blocks anonymous access; remembers the requested path for post-login redirect. */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageSpinner />;
  if (!user) {
    // Logged-out visit to the app root → the branded welcome splash. Deep
    // links to any other path still go to /login, preserving the request.
    if (location.pathname === "/") return <Navigate to="/welcome" replace />;
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <Toaster position="top-right" richColors />
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/welcome" element={<WelcomeRoute />} />

        <Route
          element={
            <RequireAuth>
              <DeviceAnalysisProvider>
                <AppLayout />
              </DeviceAnalysisProvider>
            </RequireAuth>
          }
        >
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/data-browser" element={<DataBrowserPage />} />
          <Route
            path="/views/builder/:id?"
            element={
              <Suspense fallback={<LazyFallback />}>
                <ViewBuilderPage />
              </Suspense>
            }
          />
          <Route path="/views" element={<ViewsListPage />} />
          <Route
            path="/visualizations/builder/:id?"
            element={
              <Suspense fallback={<LazyFallback />}>
                <VisualizationBuilderPage />
              </Suspense>
            }
          />
          <Route path="/visualizations" element={<VisualizationsListPage />} />
          <Route path="/visualizations/:id" element={<VisualizationViewPage />} />
          <Route
            path="/dashboards/builder/:id?"
            element={
              <Suspense fallback={<LazyFallback />}>
                <DashboardBuilderPage />
              </Suspense>
            }
          />
          <Route path="/dashboards" element={<DashboardsListPage />} />
          <Route path="/dashboards/:id" element={<DashboardDisplayPage />} />
          <Route path="/schema" element={<SchemaTablesPage />} />
          <Route path="/schema/create" element={<SchemaCreateTablePage />} />
          <Route path="/schema/tables/:name" element={<SchemaTableDetailPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>

        {/* Fallback — unknown paths get a friendly 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ErrorBoundary>
  );
}
