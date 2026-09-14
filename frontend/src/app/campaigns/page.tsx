"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../lib/api";
type Campaign = { id: string; name: string; status: string };
type QueueStatus = { active_calls: number; max_capacity: number; utilization: number; pending_tasks: Record<string, number> };
export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [queue, setQueue] = useState<QueueStatus | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function refresh() {
    try {
      const [rows, status] = await Promise.all([
        apiFetch<Campaign[]>("/api/v1/campaigns"), apiFetch<QueueStatus>("/api/v1/queue/status")]);
      setCampaigns(rows); setQueue(status); setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load campaigns"); }
  }
  useEffect(() => { refresh(); const t = window.setInterval(refresh, 5000); return () => window.clearInterval(t); }, []);
  async function createCampaign(e: React.FormEvent) {
    e.preventDefault();
    try { await apiFetch("/api/v1/campaigns", { method: "POST", body: JSON.stringify({ name }) }); setName(""); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to create campaign"); }
  }
  async function transition(id: string, action: "start" | "pause") {
    try { await apiFetch(`/api/v1/campaigns/${id}/${action}`, { method: "POST" }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to update campaign"); }
  }
  const pct = queue?.max_capacity ? Math.min(100, ((queue?.active_calls ?? 0) / queue.max_capacity) * 100) : 0;
  const pill = (s: string) => s === "RUNNING" ? "pill green" : s === "PAUSED" ? "pill amber" : s === "COMPLETED" ? "pill" : "pill";
  return (
    <Page kicker="OUTBOUND OPERATIONS" title="Campaigns" sub="Create → Start (fills queue) → Pause/Resume. Queue auto-refreshes.">
      <div className="panel" style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
          <strong>Queue capacity</strong><span>{queue?.active_calls ?? 0} / {queue?.max_capacity ?? 0} active</span></div>
        <div className="progress" style={{ marginTop: 8 }}><div style={{ width: `${pct}%` }} /></div>
        <div style={{ fontSize: 12.5, color: "#5b7170", marginTop: 6 }}>
          {Object.entries(queue?.pending_tasks ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"}</div>
      </div>
      <form onSubmit={createCampaign} style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input className="input" placeholder="New campaign name (e.g. Cardiac 48h follow-up)" value={name}
          onChange={(e) => setName(e.target.value)} required />
        <button className="btn" type="submit">Create draft</button>
      </form>
      {error && <p className="alert err" role="alert">{error}</p>}
      <div className="table-wrap"><table className="table">
        <thead><tr><th>Campaign</th><th>Status</th><th style={{ textAlign: "right" }}>Action</th></tr></thead>
        <tbody>{campaigns.map((c) => (
          <tr key={c.id}><td><strong>{c.name}</strong><div style={{ fontSize: 11, color: "#64748b" }}>{c.id.slice(0, 8)}</div></td>
            <td><span className={pill(c.status)}>{c.status}</span></td>
            <td style={{ textAlign: "right" }}>{c.status === "RUNNING"
              ? <button className="btn ghost" onClick={() => transition(c.id, "pause")}>Pause</button>
              : <button className="btn" disabled={c.status === "COMPLETED"} onClick={() => transition(c.id, "start")}>Start</button>}</td></tr>))}
        </tbody>
      </table></div>
      {campaigns.length === 0 && <p className="sub">No campaigns yet — create one, Start it, then run AI calls from the dashboard.</p>}
    </Page>);
}

