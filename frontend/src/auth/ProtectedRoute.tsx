import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { canCapture, type UserRole } from "./types";

export function ProtectedRoute({
  children,
  minimumRole,
  requireCapture,
}: {
  children: React.ReactNode;
  minimumRole?: UserRole;
  requireCapture?: boolean;
}) {
  const { user, loading, config } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="auth-loading">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  if (config?.auth_enabled && !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user && requireCapture && !canCapture(user.role)) {
    return <Navigate to="/" replace />;
  }

  if (user && minimumRole) {
    const rank: Record<UserRole, number> = {
      viewer: 1,
      inspector: 2,
      fleet_manager: 3,
      admin: 4,
    };
    if (rank[user.role] < rank[minimumRole] && user.role !== "admin") {
      return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
}
