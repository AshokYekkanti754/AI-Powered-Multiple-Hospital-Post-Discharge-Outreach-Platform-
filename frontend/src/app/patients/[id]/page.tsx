"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";
type TimelineEvent = { type: string; timestamp: string; detail: Record<string, unknown> };
type Elig = { eligible: boolean; reason: string; risk_tier: string; hours_since_discharge?: number; hours_remaining_in_window?: number } | null;
export default function PatientDetailPage({ params }: { params: { id: string } }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [elig, setElig] = useState<Elig>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiFetch<TimelineEvent[]>(`/api/v1/patients/${params.id}/timeline`).then(setEvents)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load timeline"));
    apiFetch<Elig>(`/api/v1/patients/eligibility-check?patient_id=${params.id}`, { method: "POST", body: JSON.stringify({}) })
      .then(setElig).catch(() => setElig(null));
  }, [params.id]);
  return (
    <Page kicker="PATIENT RECORD" title="Patient timeline" sub={params.id}>
      {error && <p className="alert err">{error}</p>}
      {elig && (
        <p>{elig.eligible ? <span className="pill green">ELIGIBLE</span> : <span className="pill amber">NOT ELIGIBLE</span>}{" "}
          <span className="pill">{elig.risk_tier}</span> <span style={{ fontSize: 13, color: "#5b7170" }}>{elig.reason}</span></p>)}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {events.map((e, i) => (
          <li key={i} className="panel" style={{ borderLeft: "4px solid #0f766e", marginBottom: 12 }}>
            <div><strong>{e.type}</strong> — {new Date(e.timestamp).toLocaleString()}</div>
            <pre className="code" style={{ marginTop: 8 }}>{JSON.stringify(e.detail, null, 2)}</pre>
          </li>))}
      </ul>
      {events.length === 0 && !error && <p className="sub">No timeline events.</p>}
    </Page>);
}

