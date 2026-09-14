"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";
type Report = { id: string; total_cases: number; false_negative_rate: number; report_markdown?: string };
export default function SafetyPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    try { setReport(await apiFetch<Report>("/api/v1/safety/reports/latest")); setErr(null); }
    catch { setReport(null); }
  }
  useEffect(() => { refresh(); }, []);
  async function runEval() {
    setBusy(true); setErr(null);
    try { await apiFetch("/api/v1/safety/run-eval", { method: "POST", body: JSON.stringify({}) }); await refresh(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Evaluation failed"); }
    finally { setBusy(false); }
  }
  return (
    <Page kicker="SAFETY MONITORING" title="Safety evaluation"
      sub="Fixed 30-case benchmark · false-negative rate, disagreements, limitations.">
      <button className="btn" onClick={runEval} disabled={busy}>{busy ? "Evaluating…" : "▶ Run 30-case safety benchmark"}</button>
      {err && <p className="alert err" role="alert">{err}</p>}
      <div className="panel" style={{ marginTop: 14 }}>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 13 }}>
          {report ? (report.report_markdown ?? JSON.stringify(report, null, 2)) : "No evaluation run yet — press the button."}</pre>
      </div>
    </Page>);
}

