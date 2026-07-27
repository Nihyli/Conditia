import { Component, type ErrorInfo, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { AppLayout } from "./components/AppLayout";
import { CapturePage } from "./pages/CapturePage";
import { FindingsPage } from "./pages/FindingsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { InspectionDetailPage } from "./pages/InspectionDetailPage";
import { InspectionsPage } from "./pages/InspectionsPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SamsaraPage } from "./pages/SamsaraPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TruckDetailPage } from "./pages/TruckDetailPage";
import { TrucksPage } from "./pages/TrucksPage";

function FleetSelectPage() {
  const { session, selectFleet } = useAuth();
  const fleets = session?.available_fleets ?? [];

  return (
    <div className="signin">
      <main className="signin-main">
        <div className="signin-main__inner">
          <h2 className="signin-main__title">Choose a fleet</h2>
          <p className="signin-links__hint">
            Your account belongs to multiple fleets. Pick one to continue.
          </p>
          <div className="signin-form">
            {fleets.map((fleet) => (
              <button
                key={fleet.fleet_id}
                type="button"
                className="signin-submit"
                onClick={() => {
                  void selectFleet(fleet.fleet_id);
                }}
              >
                {fleet.fleet_id.slice(0, 8)}… ({fleet.role})
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

function AppRoutes() {
  const { status, needsSignIn, needsFleetSelection } = useAuth();

  if (status === "loading") {
    return <div className="app-loading">Loading…</div>;
  }

  if (needsSignIn) {
    return <LoginPage />;
  }

  if (needsFleetSelection) {
    return <FleetSelectPage />;
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/trucks" element={<TrucksPage />} />
        <Route path="/trucks/:truckId" element={<TruckDetailPage />} />
        <Route path="/inspections" element={<InspectionsPage />} />
        <Route path="/inspections/:inspectionId" element={<InspectionDetailPage />} />
        <Route path="/findings" element={<FindingsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/:inspectionId" element={<ReportDetailPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/integrations/samsara" element={<SamsaraPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="/capture" element={<CapturePage />} />
      <Route path="/capture/:truckId" element={<CapturePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

interface ErrorBoundaryState {
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Uncaught render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-loading" role="alert">
          <div style={{ textAlign: "center" }}>
            <h1>Something went wrong</h1>
            <p style={{ color: "var(--text-2)", margin: "var(--space-8) 0 var(--space-16)" }}>
              An unexpected error occurred. Please reload the page.
            </p>
            <button
              className="primary-btn"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export function App() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <AppRoutes />
      </ErrorBoundary>
    </AuthProvider>
  );
}
