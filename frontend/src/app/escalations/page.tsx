"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../lib/api";
type Esc = { id: string; patient_id: string; status: string; severity: string; trigger_reason: string };
export default function EscalationsPage() {
  const [rows, setRows] = useState<Esc[]>([]);
  const [err, setErr] = useState<string | null>(null);
  async function refresh() {
    try { setRows(await apiFetch<Esc[]>("/api/v1/escalations")); setErr(null); }
    catch (e) { setErr(e instanceof Error ? e.message : "Unable to load escalations"); }
  }
  useEffect(() => { refresh(); const t = window.setInterval(refresh, 4000); return () => window.clearInterval(t); }, []);
  async function act(id: string, action: "acknowledge" | "resolve") {
    try {
      await apiFetch(`/api/v1/escalations/${id}/${action}`,
        { method: "POST", body: JSON.stringify(action === "resolve" ? { notes: "Reviewed in UI" } : {}) });
      await refresh();
    } catch (e) { setErr(e instanceof Error ? e.message : "Action failed"); }
  }
  const sev = (s: string) => s === "URGENT" ? "pill red" : s === "HIGH" ? "pill amber" : "pill";
  const st = (s: string) => s === "RESOLVED" ? "pill green" : s === "OPEN" ? "pill red" : "pill amber";
  const open = rows.filter((r) => r.status === "OPEN").length;
  return (
    <Page kicker="CLINICAL SAFETY" title="Escalations" sub={`${open} open · urgent or uncertain AI cases needing human review.`}>
      {err && <p className="alert err" role="alert">{err}</p>}
      <div className="table-wrap"><table className="table">
        <thead><tr><th>Severity</th><th>Status</th><th>Reason</th><th style={{ textAlign: "right" }}>Actions</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.id}>
            <td><span className={sev(r.severity)}>{r.severity}</span></td>
            <td><span className={st(r.status)}>{r.status}</span></td>
            <td style={{ fontSize: 12.5 }}>{r.trigger_reason}</td>
            <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              <button className="btn ghost" style={{ padding: "6px 12px", marginRight: 6 }}
                onClick={() => act(r.id, "acknowledge")} disabled={r.status !== "OPEN"}>Acknowledge</button>
              <button className="btn" style={{ padding: "6px 12px" }}
                onClick={() => act(r.id, "resolve")} disabled={r.status === "RESOLVED"}>Resolve</button>
            </td></tr>))}</tbody>
      </table></div>
      {rows.length === 0 && <p className="sub">No escalations yet — run AI calls and red-flag cases will land here.</p>}
    </Page>);
}
