"use client";
import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";

export type Role = "CAMPAIGN_MANAGER" | "CLINICAL_REVIEWER" | "HOSPITAL_ADMIN" | "PLATFORM_ADMIN";

export interface NavItem {
  href: string;
  label: string;
}

export interface RoleConfig {
  role: Role;
  label: string;
  badge: string;
  landing: string;
  nav: NavItem[];
}

export const ROLE_CONFIGS: Record<Role, RoleConfig> = {
  CAMPAIGN_MANAGER: {
    role: "CAMPAIGN_MANAGER",
    label: "Campaign Manager",
    badge: "Campaign Manager - Outbound Ops",
    landing: "/dashboard",
    nav: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/campaigns", label: "Campaigns" },
      { href: "/calls", label: "Calls" },
      { href: "/patients", label: "Patients" },
    ],
  },
  CLINICAL_REVIEWER: {
    role: "CLINICAL_REVIEWER",
    label: "Clinical Reviewer",
    badge: "Clinical Reviewer - Safety Triage",
    landing: "/escalations",
    nav: [
      { href: "/escalations", label: "Escalations" },
      { href: "/campaigns/manual-followups", label: "Follow-ups" },
      { href: "/calls", label: "Calls" },
    ],
  },
  HOSPITAL_ADMIN: {
    role: "HOSPITAL_ADMIN",
    label: "Hospital Admin",
    badge: "Hospital Admin - St. Jude Health",
    landing: "/dashboard",
    nav: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/patients", label: "Patients" },
      { href: "/admin/users", label: "Users" },
      { href: "/admin/onboard/ehr", label: "EHR Sync" },
    ],
  },
  PLATFORM_ADMIN: {
    role: "PLATFORM_ADMIN",
    label: "Platform Admin",
    badge: "Platform Admin - System Control",
    landing: "/admin/platform-dashboard",
    nav: [
      { href: "/admin/platform-dashboard", label: "Platform" },
      { href: "/admin/ai-inspector", label: "AI Inspector" },
      { href: "/admin/safety", label: "Safety" },
      { href: "/admin/health", label: "Health" },
      { href: "/admin/onboard", label: "Onboard" },
    ],
  },
};

const STORAGE_KEY = "active_role";

interface RoleContextValue {
  currentRole: Role;
  setRole: (role: Role) => void;
  config: RoleConfig;
  allowedRoutes: string[];
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [currentRole, setCurrentRole] = useState<Role>("CAMPAIGN_MANAGER");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY) as Role | null;
    if (stored && ROLE_CONFIGS[stored]) {
      setCurrentRole(stored);
    }
  }, []);

  const setRole = useCallback(
    (role: Role) => {
      setCurrentRole(role);
      if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, role);
      router.push(ROLE_CONFIGS[role].landing);
    },
    [router],
  );

  const config = ROLE_CONFIGS[currentRole];
  const allowedRoutes = config.nav.map((n) => n.href);

  return (
    <RoleContext.Provider value={{ currentRole, setRole, config, allowedRoutes }}>
      <div data-theme={currentRole} style={{ "--theme-accent": roleAccent(currentRole) } as React.CSSProperties}>
        {children}
      </div>
    </RoleContext.Provider>
  );
}

export function roleAccent(role: Role): string {
  const map: Record<Role, string> = {
    CAMPAIGN_MANAGER: "#0d9488",   // teal/cyan-500
    CLINICAL_REVIEWER: "#f43f5e",  // rose-500
    HOSPITAL_ADMIN: "#475569",     // slate-500
    PLATFORM_ADMIN: "#6366f1",     // indigo-500
  };
  return map[role];
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole must be used within RoleProvider");
  return ctx;
}

