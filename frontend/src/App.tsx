import { Navigate, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { CapturePage } from "./pages/CapturePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/capture" element={<CapturePage />} />
      <Route path="/capture/:truckId" element={<CapturePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
