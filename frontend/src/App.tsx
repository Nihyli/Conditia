import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { CapturePage } from "./pages/CapturePage";
import { FindingsPage } from "./pages/FindingsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { InspectionDetailPage } from "./pages/InspectionDetailPage";
import { InspectionsPage } from "./pages/InspectionsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReportDetailPage } from "./pages/ReportDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SamsaraPage } from "./pages/SamsaraPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TruckDetailPage } from "./pages/TruckDetailPage";
import { TrucksPage } from "./pages/TrucksPage";

export function App() {
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
