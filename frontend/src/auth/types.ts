export type UserRole = "admin" | "fleet_manager" | "inspector" | "viewer";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  fleet_id: string | null;
  auth_provider: string;
}

export interface AuthConfig {
  auth_enabled: boolean;
  provider: "local" | "supabase";
  supabase_url: string | null;
  supabase_anon_key: string | null;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

const RANK: Record<UserRole, number> = {
  viewer: 1,
  inspector: 2,
  fleet_manager: 3,
  admin: 4,
};

export function hasMinRole(role: UserRole, minimum: UserRole): boolean {
  return RANK[role] >= RANK[minimum];
}

export function canCapture(role: UserRole): boolean {
  return hasMinRole(role, "inspector");
}

export function canManageFleet(role: UserRole): boolean {
  return hasMinRole(role, "fleet_manager");
}

export function canAccessSettings(role: UserRole): boolean {
  return hasMinRole(role, "fleet_manager");
}

export function canAccessAdmin(role: UserRole): boolean {
  return role === "admin";
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  fleet_manager: "Fleet manager",
  inspector: "Inspector",
  viewer: "Viewer",
};

export const NAV_MIN_ROLE: Record<string, UserRole> = {
  overview: "viewer",
  trucks: "viewer",
  inspections: "viewer",
  findings: "viewer",
  reports: "viewer",
  history: "viewer",
  samsara: "fleet_manager",
  settings: "fleet_manager",
};

export function canAccessNav(role: UserRole, navId: string): boolean {
  const min = NAV_MIN_ROLE[navId] ?? "viewer";
  return hasMinRole(role, min);
}
