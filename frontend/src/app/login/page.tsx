"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const PRESETS: [string, string][] = [
  ["Hospital admin", "admin@stmarys.demo"],
  ["Campaign manager", "campaign@stmarys.demo"],
  ["Clinician", "clinical@stmarys.demo"],
  ["Platform admin", "admin@platform.local"],
];

export default function LoginPage() {
  const [email, setEmail] = useState("admin@stmarys.demo");
  const [password, setPassword] = useState("Demo@123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((body as { detail?: string }).detail ?? "Login failed");
      window.localStorage.setItem("access_token", (body as { access_token: string }).access_token);
      window.localStorage.setItem("user_email", email);
      const me = await fetch(`${API}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${(body as { access_token: string }).access_token}` },
      }).then((r) => r.json()).catch(() => null);
            window.localStorage.setItem("user_role", (me as { role?: string } | null)?.role ?? "");
      // Set the role persona so PersonaSwitcher loads in the correct role
      if ((me as { role?: string } | null)?.role) {
        window.localStorage.setItem("active_role", (me as { role: string }).role);
      }
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="login-wrap">
        <div className="login-card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="brand-badge">✚</span>
            <strong style={{ fontSize: 18 }}>CareOutreach</strong>
          </div>
          <p className="kicker">POST-DISCHARGE OUTREACH</p>
          <h1 className="h1" style={{ fontSize: 28 }}>Sign in</h1>
          <p className="sub">Hospital operations console. Backend: {API}</p>
          <form onSubmit={handleSubmit}>
            <label style={{ display: "block", marginBottom: 12 }}>Email
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ marginTop: 4 }} />
            </label>
            <label style={{ display: "block", marginBottom: 12 }}>Password
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ marginTop: 4 }} />
            </label>
            {error && <p className="alert err" role="alert">{error}</p>}
            <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Signing in…" : "Sign in →"}
            </button>
          </form>
          <div className="demo-creds" style={{ marginTop: 16 }}>
            <strong>One-click demo accounts</strong> (password <code>Demo@123</code>)
            <div style={{ marginTop: 8 }}>
              {PRESETS.map(([label, em]) => (
                <button key={em} className="btn ghost" style={{ padding: "6px 10px", fontSize: 12 }}
                  onClick={() => { setEmail(em); setPassword("Demo@123"); }}>{label}</button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

