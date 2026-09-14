"use client";

import { useEffect, useState } from "react";

interface AuditEntry {
  id: string;
  tool_name: string;
  caller_agent_id: string;
  action: string;
  status: string;
}

/**
 * Milestone 1.3 — Mock EHR inspector UI shell.
 * Read-only view of ehr_audit_trail for the caller's own hospital.
 */
export default function EhrInspectorPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = window.localStorage.getItem("access_token");
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/api/v1/ehr/audit-trail`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load audit trail");
        return res.json();
      })
      .then(setEntries)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h1>EHR audit trail</h1>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>
            <th>Tool</th>
            <th>Agent</th>
            <th>Action</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} style={{ borderBottom: "1px solid #eee" }}>
              <td>{e.tool_name}</td>
              <td>{e.caller_agent_id}</td>
              <td>{e.action}</td>
              <td style={{ color: e.status === "success" ? "green" : "crimson" }}>{e.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
