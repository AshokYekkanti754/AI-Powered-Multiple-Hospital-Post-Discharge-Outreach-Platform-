"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../lib/api";
type Call = { id: string; patient_id: string; outcome: string; duration?: number; transcript?: string; at?: string };
function pillFor(o: string) {
  if (o === "COMPLETED") return "pill green";
  if (o === "FAILED") return "pill red";
  if (["NO_ANSWER", "BUSY", "VOICEMAIL", "DROPPED"].includes(o)) return "pill amber";
  return "pill";
}
export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [override, setOverride] = useState("");
  const [overrideTs, setOverrideTs] = useState<string | null>(null);
  async function refresh() {
    try { setCalls(await apiFetch<Call[]>("/api/v1/calls/history?limit=50")); setErr(null); }
    catch (e) { setErr(e instanceof Error ? e.message : "Unable to load calls"); }
  }
  useEffect(() => { refresh(); const t = window.setInterval(refresh, 4000); return () => window.clearInterval(t); }, []);
  async function runOne(overrideText?: string) {
    setBusy(true);
    try {
      await apiFetch("/api/v1/calls/process-next", {
        method: "POST",
        body: JSON.stringify(overrideText ? { transcript_override: overrideText } : {}),
      });
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }
  function handleOverrideRun() {
    const text = override.trim();
    if (!text) return;
    setOverrideTs(text);
    runOne(text);
    setOverride("");
  }
  return (
    <Page kicker="VOICE OPERATIONS" title="Calls" sub="Every call runs voice intake → triage → consensus → documentation → EHR.">
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <button className="btn" onClick={() => runOne()} disabled={busy}>{busy ? "Running…" : "▶ Run next AI call"}</button>
          <a className="btn ghost" href="/dashboard" style={{ textDecoration: "none" }}>Run batch of 10</a>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginLeft: "auto", paddingTop: 2 }}>
          <textarea
            className="input"
            rows={2}
            style={{ minWidth: 260, maxWidth: 420, resize: "vertical", fontFamily: "inherit" }}
            placeholder="Custom patient transcript — e.g. &quot;I have chest pain and shortness of breath.&quot;"
            value={override}
            onChange={(e) => setOverride(e.target.value)}
          />
          <button className="btn" onClick={handleOverrideRun} disabled={busy || !override.trim()} style={{ padding: "11px 14px" }}>
            {busy ? "Running…" : "▶ Run with override"}
          </button>
        </div>
      </div>
      {err && <p className="alert err" role="alert">{err}</p>}
      {overrideTs && (
        <div className="panel" style={{ marginBottom: 12, fontSize: 13 }}>
          <span style={{ color: "var(--brand)", fontWeight: 800 }}>Last override used:</span>
          <code className="code" style={{ display: "block", marginTop: 6, fontSize: 12 }}>{overrideTs}</code>
        </div>
      )}
      <div className="table-wrap"><table className="table">
        <thead><tr><th>Outcome</th><th>Patient</th><th>Transcript</th></tr></thead>
        <tbody>{calls.map((c) => (
          <tr key={c.id}>
            <td><span className={pillFor(c.outcome)}>{c.outcome}</span>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{c.id.slice(0, 8)}{c.duration ? ` · ${c.duration}s` : ""}</div></td>
            <td style={{ fontSize: 12 }}>{c.patient_id.slice(0, 8)}</td>
            <td style={{ fontSize: 12.5, whiteSpace: "pre-wrap", maxWidth: 640 }}>{c.transcript || "—"}</td>
          </tr>))}</tbody>
      </table></div>
      {calls.length === 0 && <p className="sub">No calls yet — press “Run next AI call”.</p>}
    </Page>);
}
