/** Route paths and page titles for the dashboard shell. */

export const ROUTES = {
  overview: "/",
  trucks: "/trucks",
  truckDetail: (id: string) => `/trucks/${id}`,
  inspections: "/inspections",
  inspectionDetail: (id: string) => `/inspections/${id}`,
  findings: "/findings",
  reports: "/reports",
  reportDetail: (inspectionId: string) => `/reports/${inspectionId}`,
  history: "/history",
  samsara: "/integrations/samsara",
  settings: "/settings",
  capture: "/capture",
} as const;

export function pageTitle(pathname: string): string {
  if (pathname.startsWith("/trucks/") && pathname !== "/trucks") return "Truck detail";
  if (pathname === ROUTES.trucks) return "Trucks";
  if (pathname.startsWith("/inspections/") && pathname !== "/inspections") {
    return "Inspection detail";
  }
  if (pathname === ROUTES.inspections) return "Inspections";
  if (pathname.startsWith("/reports/") && pathname !== "/reports") return "Report";
  if (pathname === ROUTES.reports) return "Reports";
  if (pathname === ROUTES.findings) return "Findings";
  if (pathname === ROUTES.history) return "History";
  if (pathname === ROUTES.samsara) return "Samsara integration";
  if (pathname === ROUTES.settings) return "Settings";
  return "Fleet overview";
}
