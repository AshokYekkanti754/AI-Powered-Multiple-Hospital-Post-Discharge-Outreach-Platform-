"use client";

import { useState } from "react";

/**
 * Milestone 1.1 — Platform Admin hospital onboarding UI shell.
 * Requires a PLATFORM_ADMIN bearer token in localStorage (set by /login).
 */
export default function OnboardHospitalPage() {
  const [form, setForm] = useState({
    hospital_name: "",
    timezone: "UTC",
    max_concurrent_calls: 10,
    retry_limit: 3,
    admin_email: "",
    admin_full_name: "",
    admin_password: "",
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    const token = window.localStorage.getItem("access_token");
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/api/v1/hospitals/onboard`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(form),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Onboarding failed");
      }
      const data = await res.json();
      setMessage(`Hospital "${data.name}" onboarded successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onboarding failed");
    }
  }

  return (
    <main style={{ maxWidth: 480, margin: "60px auto", fontFamily: "sans-serif" }}>
      <h1>Onboard a hospital</h1>
      <form onSubmit={handleSubmit}>
        <fieldset style={{ marginBottom: 16 }}>
          <legend>Hospital</legend>
          <input
            placeholder="Hospital name"
            value={form.hospital_name}
            onChange={(e) => update("hospital_name", e.target.value)}
            required
            style={{ display: "block", width: "100%", padding: 8, marginBottom: 8 }}
          />
          <input
            placeholder="Timezone (e.g. America/New_York)"
            value={form.timezone}
            onChange={(e) => update("timezone", e.target.value)}
            style={{ display: "block", width: "100%", padding: 8, marginBottom: 8 }}
          />
        </fieldset>
        <fieldset>
          <legend>Primary hospital admin</legend>
          <input
            type="email"
            placeholder="Admin email"
            value={form.admin_email}
            onChange={(e) => update("admin_email", e.target.value)}
            required
            style={{ display: "block", width: "100%", padding: 8, marginBottom: 8 }}
          />
          <input
            placeholder="Admin full name"
            value={form.admin_full_name}
            onChange={(e) => update("admin_full_name", e.target.value)}
            required
            style={{ display: "block", width: "100%", padding: 8, marginBottom: 8 }}
          />
          <input
            type="password"
            placeholder="Temporary password"
            value={form.admin_password}
            onChange={(e) => update("admin_password", e.target.value)}
            required
            style={{ display: "block", width: "100%", padding: 8, marginBottom: 8 }}
          />
        </fieldset>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        {message && <p style={{ color: "green" }}>{message}</p>}
        <button type="submit" style={{ padding: "8px 16px", marginTop: 8 }}>
          Onboard hospital
        </button>
      </form>
    </main>
  );
}
