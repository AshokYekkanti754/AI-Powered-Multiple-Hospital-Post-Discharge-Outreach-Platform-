"use client";
import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import PersonaSwitcher from "../components/PersonaSwitcher";
import { useRole } from "../context/RoleContext";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://ai-powered-multiple-hospital-post-q5em.onrender.com";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

export function signOut() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("user_email");
  window.location.replace("/login");
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  for (const [k, v] of Object.entries((init.headers ?? {}) as Record<string, string>)) headers[k] = v;
  let res: Response;
  try {
    res = await fetch(API + path, { ...init, headers });
  } catch {
    throw new Error("Cannot reach backend at " + API + ". Check your internet connection.");
  }
  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    if (token) signOut();
    throw new Error((body as { detail?: string }).detail ?? "Not authenticated - please sign in.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = (body as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : "Request failed (" + res.status + ")");
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function Nav() {
  const pathname = usePathname();
  const [email, setEmail] = useState<string>("");
  useEffect(() => { setEmail(window.localStorage.getItem("user_email") ?? ""); }, [pathname]);

  const { config, allowedRoutes } = useRole();

  return (
    <header className="topbar" style={{ borderTop: "2px solid var(--theme-accent)" }}>
      <a className="brand" href="/">
        <span className="brand-badge">O</span>
        <span>CareOutreach</span>
      </a>
      <nav className="nav-links">
        {config.nav.map((item) => {
          if (!allowedRoutes.includes(item.href)) return null;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <a
              key={item.href}
              href={item.href}
              className={active ? "active" : ""}
            >
              {item.label}
            </a>
          );
        })}
      </nav>
      <span className="nav-right">
        <span className="pill" title={config.badge} style={{ fontSize: 11 }}>
          {config.badge}
        </span>
        {email && <span className="pill" title="Signed in user">{email}</span>}
        {email && <PersonaSwitcher />}
        {email
          ? <button className="btn ghost" onClick={signOut}>Sign out</button>
          : <a className="btn" href="/login" style={{ textDecoration: "none" }}>Sign in</a>}
      </span>
    </header>
  );
}

export function Page({ kicker, title, sub, children }: {
  kicker: string; title: string; sub?: string; children: React.ReactNode;
}) {
  return (
    <div className="app-shell">
      <Nav />
      <p className="kicker">{kicker}</p>
      <h1 className="h1">{title}</h1>
      {sub && <p className="sub">{sub}</p>}
      {children}
    </div>
  );
}

export function useMe() {
  const [me, setMe] = useState<{ email: string; role: string; hospital_name?: string | null } | null>(null);
  useEffect(() => {
    apiFetch<{ email: string; role: string; hospital_name?: string | null }>("/api/v1/auth/me")
      .then(setMe).catch(() => setMe(null));
  }, []);
  return me;
}

