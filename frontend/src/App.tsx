import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { DashboardPage } from "./pages/DashboardPage";
import { CapturePage } from "./pages/CapturePage";
import { LoginPage } from "./pages/LoginPage";

function AppRoutes() {
  const { status, needsSignIn } = useAuth();

  if (status === "loading") {
    return <div className="app-loading">Loading…</div>;
  }

  if (needsSignIn) {
    return <LoginPage />;
  }

  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/capture" element={<CapturePage />} />
      <Route path="/capture/:truckId" element={<CapturePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
