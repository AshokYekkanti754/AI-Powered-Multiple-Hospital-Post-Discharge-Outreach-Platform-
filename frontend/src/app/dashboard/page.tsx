"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page, useMe } from "../../lib/api";

type Summary = {
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
  ai_metrics?: { requests: number; disagreement_rate?: number; estimated_cost?: number };
  recent_calls?: { id: string; outcome: string }[];
  top_queue?: { id: string; status: string; priority: number }[];
};

type QueueBucket = {
  pending: number;
  scheduled: number;
  calling: number;
  retrying: number;
  completed: number;
  escalated: number;
  failed: number;
  manual_followup: number;
};

function pillFor(s: string) {
  if (s === "COMPLETED") return "pill green";
  if (s === "ESCALATED" || s === "FAILED") return "pill red";
  if (s.includes("RETRY") || s === "CALLING" || s.includes("CALLBACK")) return "pill amber";
  return "pill";
}

export default function DashboardPage() {
  const me = useMe();
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setData(await apiFetch<Summary>("/api/v1/dashboard/campaign-manager"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load dashboard");
    }
  }

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 4000);
    return () => window.clearInterval(t);
  }, []);

  async function runBatch() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await apiFetch<{ processed: number }>(
        "/api/v1/calls/demo-batch?count=10",
        { method: "POST" }
      );
      setMsg(`Processed ${r.processed} AI calls — queue, calls, escalations and AI logs updated.`);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Batch failed");
    } finally {
      setBusy(false);
    }
  }

  const buckets: QueueBucket = data
    ? {
        pending: data.pending_tasks["PENDING"] ?? 0,
        scheduled: data.pending_tasks["SCHEDULED"] ?? 0,
        calling: data.pending_tasks["CALLING"] ?? 0,
        retrying: data.pending_tasks["RETRYING"] ?? data.pending_tasks["RETRY"] ?? 0,
        completed: data.pending_tasks["COMPLETED"] ?? 0,
        escalated: data.pending_tasks["ESCALATED"] ?? 0,
        failed: data.pending_tasks["FAILED"] ?? 0,
        manual_followup: data.manual_followups ?? 0,
      }
    : {
        pending: 0,
        scheduled: 0,
        calling: 0,
        retrying: 0,
        completed: 0,
        escalated: 0,
        failed: 0,
        manual_followup: 0,
      };

  const total = Object.values(buckets).reduce((a, b) => a + b, 0);
  const reached = buckets.completed + buckets.escalated;
  const contacted = buckets.calling + buckets.completed + buckets.escalated;
  const cap = data?.max_capacity ?? 0;
  const util = cap ? Math.min(100, Math.round(((data?.active_calls ?? 0) / cap) * 100)) : 0;

  const stat = (label: string, value: string | number, hint?: string) => (
    <article key={label} className="card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </article>
  );

  const queueRow = (
    label: string,
    value: number,
    color = "var(--muted)"
  ) => (
    <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
      <span>{label}</span>
      <span style={{ color }}>{value}</span>
    </div>
  );
  return (
    <Page
      kicker={`CAMPAIGN MANAGER DASHBOARD · ${data?.hospital_name ?? "…"}`}
      title="Campaign Dashboard"
      sub={me ? `Signed in as ${me.email} · ${me.role}` : "Auto-refreshes every 4s."}
    >
      <div className="hero">
        <div className="panel">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <div>
              <strong>Queue capacity</strong>
              <div style={{ fontSize: 13, color: "#5b7170" }}>
                {data?.active_calls ?? 0} / {cap} active · {util}%
              </div>
            </div>
            <button className="btn" onClick={runBatch} disabled={busy}>
              {busy ? "Running…" : "▶ Run 10 AI calls now"}
            </button>
          </div>
          <div className="progress" style={{ marginTop: 10 }}>
            <div style={{ width: `${util}%` }} />
          </div>
          <div style={{ fontSize: 12.5, color: "#5b7170", marginTop: 8 }}>
            {Object.entries(data?.pending_tasks ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ") ||
              "No queue data yet"}
          </div>
          {msg && <p className="alert ok">{msg}</p>}
          {error && <p className="alert err" role="alert">{error}</p>}
          {!data && !error && <p>Loading… if this persists, sign in at /login.</p>}
        </div>

        <div className="panel">
          <strong>60-second demo</strong>
          <ol style={{ fontSize: 13.5, paddingLeft: 18 }}>
            <li>Press <strong>Run 10 AI calls now</strong>.</li>
            <li>Open <a href="/calls">Calls</a> and <a href="/escalations">Escalations</a>.</li>
            <li>Open <a href="/admin/safety">Safety</a> → run benchmark.</li>
          </ol>
        </div>
      </div>

      {data && (
        <>
          <div className="panel" style={{ marginTop: 14 }}>
            <h3 style={{ marginTop: 0 }}>Live Queue View</h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: 8,
                marginTop: 10,
              }}
            >
              {queueRow("Pending", buckets.pending)}
              {queueRow("Scheduled", buckets.scheduled)}
              {queueRow("Calling", buckets.calling, "var(--amber)")}
              {queueRow("Retrying", buckets.retrying, "var(--amber)")}
              {queueRow("Completed", buckets.completed, "var(--green)")}
              {queueRow("Escalated", buckets.escalated, "var(--red)")}
              {queueRow("Failed", buckets.failed, "var(--red)")}
              {queueRow("Manual follow-up", buckets.manual_followup, "var(--amber)")}
            </div>
            <div style={{ marginTop: 10, fontSize: 12.5, color: "#5b7170" }}>
              Queue depth {total} · Oldest pending task{" "}
              {(data.top_queue ?? [])[0] ? "see top of queue below" : "—"}
            </div>
          </div>

          <section className="grid cards" style={{ marginTop: 14 }}>
            {stat("TOTAL PATIENTS", data.patients)}
            {stat("PATIENTS REACHED", reached)}
            {stat("COMPLETION RATE", `${Math.round(data.completion_rate * 100)}%`)}
            {stat("CONTACT RATE", `${((contacted / (total || 1)) * 100).toFixed(1)}%`, "contact ÷ total queue")}
            {stat("RETRY RATE", `${((buckets.retrying / (total || 1)) * 100).toFixed(1)}%`, "queue share")}
            {stat("ESCALATION RATE", `${((buckets.escalated / (total || 1)) * 100).toFixed(1)}%`, "queue share")}
            {stat("ACTIVE CALLS", data.active_calls, `${cap} capacity`)}
            {stat("AVAILABLE CAPACITY", Math.max(0, cap - (data.active_calls ?? 0)))}
            {stat("QUEUE DEPTH", total)}
            {stat("PATIENTS APPROACHING CUTOFF", 0, "hook to cutoff visibility")}
          </section>

          <section className="grid two" style={{ marginTop: 14 }}>
            <article className="panel">
              <h3 style={{ marginTop: 0 }}>Recent calls</h3>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {(data.recent_calls ?? []).map((c) => (
                  <span key={c.id} className={pillFor(c.outcome)}>
                    {c.outcome}
                  </span>
                ))}
              </div>
              {(data.recent_calls ?? []).length === 0 && <p className="sub">No calls yet.</p>}
              <p>
                <a href="/calls">Open call history →</a>
              </p>
            </article>
            <article className="panel">
              <h3 style={{ marginTop: 0 }}>Top of queue</h3>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.top_queue ?? []).map((t) => (
                      <tr key={t.id}>
                        <td>
                          <span className={pillFor(t.status)}>{t.status}</span>
                        </td>
                        <td>{Math.round(t.priority)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(data.top_queue ?? []).length === 0 && <p className="sub">Queue is empty.</p>}
            </article>
          </section>
        </>
      )}
    </Page>
  );
}

