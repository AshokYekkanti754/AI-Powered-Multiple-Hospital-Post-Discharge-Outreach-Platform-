"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page, useMe } from "../../../lib/api";

type HospitalSummary = {
  id: string;
  name: string;
  summary: {
    hospital_name?: string;
    active_calls: number;
    max_capacity: number;
    pending_tasks: Record<string, number>;
    completion_rate: number;
    patients: number;
    campaigns: number;
    total_calls?: number;
    open_escalations: number;
    manual_followups?: number;
    ai_metrics?: { requests: number; cost: number; disagreement_rate?: number };
    recent_calls?: { id: string; outcome: string }[];
    top_queue?: { id: string; status: string; priority: number }[];
  };
};

type PlatformSummary = {
  hospitals: HospitalSummary[];
  total_patients: number;
  total_campaigns: number;
};

function pillFor(s: string) {
  if (s === "COMPLETED") return "pill green";
  if (s === "ESCALATED" || s === "FAILED") return "pill red";
  if (s.includes("RETRY") || s === "CALLING" || s.includes("CALLBACK")) return "pill amber";
  return "pill";
}

export default function PlatformDashboardPage() {
  const me = useMe();
  const [data, setData] = useState<PlatformSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setData(await apiFetch<PlatformSummary>("/api/v1/dashboard/platform"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load platform dashboard");
    }
  }

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 5000);
    return () => window.clearInterval(t);
  }, []);

  const totalActiveCalls = data?.hospitals.reduce((a, h) => a + (h.summary.active_calls ?? 0), 0) ?? 0;
  const totalPending = data?.hospitals.reduce((a, h) => {
    const s = h.summary.pending_tasks ?? {};
    return a + Object.values(s).reduce((x, y) => x + Number(y), 0);
  }, 0) ?? 0;
  const totalEscalations = data?.hospitals.reduce((a, h) => a + (h.summary.open_escalations ?? 0), 0) ?? 0;
  const totalAiRequests = data?.hospitals.reduce((a, h) => a + (h.summary.ai_metrics?.requests ?? 0), 0) ?? 0;
  const totalCost = data?.hospitals.reduce((a, h) => a + (h.summary.ai_metrics?.cost ?? 0), 0) ?? 0;

  const stat = (label: string, value: string | number, hint?: string) => (
    <article key={label} className="card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </article>
  );

  return (
    <Page
      kicker="PLATFORM ADMINISTRATION"
      title="Platform Dashboard"
      sub={me ? `Signed in as ${me.email} · ${me.role}` : "Auto-refreshes every 5s."}
    >
      {error && <p className="alert err" role="alert">{error}</p>}

      {data && (
        <>
          <section className="grid cards" style={{ marginTop: 14 }}>
            {stat("HOSPITALS", data.hospitals.length)}
            {stat("PATIENTS", data.total_patients)}
            {stat("CAMPAIGNS", data.total_campaigns)}
            {stat("ACTIVE CALLS", totalActiveCalls)}
            {stat("PENDING", totalPending)}
            {stat("ESCALATIONS", totalEscalations)}
            {stat("AI REQUESTS", totalAiRequests)}
            {stat("AI COST", `$${totalCost.toFixed(4)}`)}
          </section>

          <div className="panel" style={{ marginTop: 14 }}>
            <h3 style={{ marginTop: 0 }}>Platform overview by hospital</h3>
            <div className="table-wrap" style={{ marginTop: 10 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Hospital</th>
                    <th>Patients</th>
                    <th>Campaigns</th>
                    <th>Active</th>
                    <th>Escalations</th>
                    <th>Completion</th>
                    <th>AI cost</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hospitals.map((h) => {
                    const s = h.summary;
                    return (
                      <tr key={h.id}>
                        <td>
                          <strong>{h.name}</strong>
                          <div style={{ fontSize: 11, color: "#64748b" }}>{h.id.slice(0, 8)}</div>
                        </td>
                        <td>{s.patients}</td>
                        <td>{s.campaigns}</td>
                        <td>{s.active_calls}/{s.max_capacity}</td>
                        <td>{s.open_escalations}</td>
                        <td>{Math.round(s.completion_rate * 100)}%</td>
                        <td>${(s.ai_metrics?.cost ?? 0).toFixed(4)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {data.hospitals.length === 0 && <p className="sub">No hospitals onboarded yet.</p>}
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <h3 style={{ marginTop: 0 }}>Queue health by hospital</h3>
            <div className="table-wrap" style={{ marginTop: 10 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Hospital</th>
                    <th>Pending</th>
                    <th>Calling</th>
                    <th>Retrying</th>
                    <th>Completed</th>
                    <th>Escalated</th>
                    <th>Failed</th>
                    <th>Manual follow-up</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hospitals.map((h) => {
                    const s = h.summary.pending_tasks ?? {};
                    return (
                      <tr key={h.id}>
                        <td><strong>{h.name}</strong></td>
                        <td>{s["PENDING"] ?? 0}</td>
                        <td>{s["CALLING"] ?? 0}</td>
                        <td>{s["RETRYING"] ?? s["RETRY"] ?? 0}</td>
                        <td>{s["COMPLETED"] ?? 0}</td>
                        <td>{s["ESCALATED"] ?? 0}</td>
                        <td>{s["FAILED"] ?? 0}</td>
                        <td>{h.summary.manual_followups ?? 0}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 14 }}>
            <h3 style={{ marginTop: 0 }}>Recent system activity</h3>
            <div className="table-wrap" style={{ marginTop: 10 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Hospital</th>
                    <th>Top queue item</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hospitals.map((h) => {
                    const s = h.summary;
                    const top = (s.top_queue ?? [])[0];
                    return (
                      <tr key={h.id}>
                        <td><strong>{h.name}</strong></td>
                        <td>
                          {top ? (
                            <span className="sub">{top.status} · priority {Math.round(top.priority)}</span>
                          ) : (
                            <span className="sub">empty</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!data && !error && <p>Loading platform dashboard…</p>}
    </Page>
  );
}
