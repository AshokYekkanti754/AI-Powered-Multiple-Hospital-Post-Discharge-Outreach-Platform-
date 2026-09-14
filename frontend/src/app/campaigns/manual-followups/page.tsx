"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";
type FollowUp = { id: string; patient_id: string; reason: string; status: string };
export default function ManualFollowUpsPage() {
  const [items, setItems] = useState<FollowUp[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiFetch<FollowUp[]>("/api/v1/calls/manual-followups").then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : "Unable to load follow-ups"));
  }, []);
  return (
    <Page kicker="CLINICAL OPERATIONS" title="Manual follow-ups"
      sub="Retries exhausted here automatically — nurse callback list.">
      {error && <p className="alert err" role="alert">{error}</p>}
      <div className="table-wrap"><table className="table">
        <thead><tr><th>Patient</th><th>Reason</th><th>Status</th></tr></thead>
        <tbody>{items.map((i) => (
          <tr key={i.id}><td>{i.patient_id.slice(0, 8)}</td><td>{i.reason}</td>
            <td><span className={i.status === "RESOLVED" ? "pill green" : "pill amber"}>{i.status}</span></td></tr>))}
        </tbody>
      </table></div>
      {items.length === 0 && <p className="sub">None yet. Failed / max-retry calls land here.</p>}
    </Page>);
}

