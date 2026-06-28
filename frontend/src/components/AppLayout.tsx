import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { getFleetStats } from "../api";
import { pageTitle } from "../nav";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppLayout() {
  const { pathname } = useLocation();
  const [trucksBadge, setTrucksBadge] = useState<number | undefined>();

  const loadBadge = useCallback(async () => {
    try {
      const stats = await getFleetStats();
      setTrucksBadge(stats.active_trucks > 0 ? stats.active_trucks : undefined);
    } catch {
      setTrucksBadge(undefined);
    }
  }, []);

  useEffect(() => {
    void loadBadge();
  }, [loadBadge, pathname]);

  return (
    <div className="app">
      <Sidebar trucksBadge={trucksBadge} />
      <div className="main">
        <Topbar title={pageTitle(pathname)} />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
