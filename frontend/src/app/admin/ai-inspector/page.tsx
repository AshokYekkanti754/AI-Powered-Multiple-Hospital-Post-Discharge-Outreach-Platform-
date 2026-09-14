"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";

function statusPill(s: string) {
  const map: Record<string, string> = {
    urgent: "pill red", escalated: "pill red",
    concerning: "pill amber", uncertain: "pill amber",
    routine: "pill green",
  };
  return map[s] ?? "pill";
}
function fmtDate(d: string | undefined) {
  if (!d) return "—";
  try { return new Date(d).toLocaleString(); } catch { return d; }
}
function statusLabel(s: string) {
  return ({
    urgent: "URGENT — immediate medical attention",
    escalated: "ESCALATED — routed to human review",
    concerning: "CONCERNING — warrants follow-up",
    uncertain: "UNCERTAIN — needs clarification",
    routine: "ROUTINE — standard follow-up",
  }[s] ?? s.toUpperCase());
}

export default function AIInspectorPage() {
  const [m, setM] = useState<{ requests: number; prompt_tokens: number; completion_tokens: number; estimated_cost: number; disagreements: number; disagreement_rate: number } | null>(null);
  const [logs, setLogs] = useState<{ id: string; agent: string; model: string; tokens: number[]; disagreement: boolean; output?: Record<string, unknown>; at?: string }[]>([]);
  const [prov, setProv] = useState<{
    provider: string; mode: string; model: string; hint?: string | null;
    chain?: { provider: string; model: string; configured: boolean; kind: string; reachable?: boolean | null; circuit?: string }[];
  } | null>(null);
  const [text, setText] = useState("Since I left the hospital, I have new chest pain and cannot breathe well when I walk up stairs.");
  const [triage, setTriage] = useState<{ final_status: string; decisions: { status: string; rationale: string; protocol_citations: string[] }[]; disagreement: boolean; human_escalation: boolean; arbiter_used: boolean } | null>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function refresh() {
    try {
      setM(await apiFetch("/api/v1/ai/metrics"));
      setLogs(await apiFetch("/api/v1/ai/logs?limit=20"));
      setProv(await apiFetch("/api/v1/ai/provider-status"));
      setErr(null);
    } catch (e) { setErr(e instanceof Error ? e.message : "Unable to load AI data"); }
  }
  useEffect(() => { refresh(); }, []);
  async function runTriage() {
    setRunning(true);
    setErr(null);
    try {
      const result = await apiFetch<{ final_status: string; decisions: { status: string; rationale: string; protocol_citations: string[] }[]; disagreement: boolean; human_escalation: boolean; arbiter_used: boolean }>(
        "/api/v1/ai/triage/evaluate",
        { method: "POST", body: JSON.stringify({ transcript: text }) }
      );
      setTriage(result);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Triage failed");
    } finally {
      setRunning(false);
    }
  }
  const stat = (t: string, v: string | number) => (
    <article key={t} className="card"><div className="label">{t}</div><div className="value">{v}</div></article>);
  return (
    <Page kicker="MODEL OPERATIONS" title="AI inspector"
      sub={`Provider ${prov?.provider ?? "…"} (${prov?.mode ?? ""}) · ${prov?.model ?? ""} · free open-model chain: Groq → OpenRouter → Google.`}>
      {err && <p className="alert err">{err}</p>}
      {prov?.hint && <p className="alert ok">{prov.hint}</p>}
      {prov?.chain && prov.chain.length > 0 && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <strong>Provider fallback chain</strong>
          <div className="table-wrap" style={{ marginTop: 8 }}><table className="table">
            <thead><tr><th>Provider</th><th>Model</th><th>Kind</th><th>Key</th><th>Status</th></tr></thead>
            <tbody>{prov.chain.map((c) => (
              <tr key={c.provider}>
                <td><strong>{c.provider}</strong>{c.provider === prov.provider && <span className="pill green" style={{ marginLeft: 6 }}>active</span>}</td>
                <td style={{ fontSize: 12 }}>{c.model}</td>
                <td>{c.kind}</td>
                <td>{c.configured ? <span className="pill green">configured</span> : <span className="pill amber">placeholder — add free key</span>}</td>
                <td>{c.circuit ? <span className="pill red">{c.circuit}</span> : c.reachable === false ? <span className="pill red">unreachable</span> : c.reachable === true ? <span className="pill green">reachable</span> : <span className="pill">—</span>}</td>
              </tr>))}</tbody>
          </table></div>
        </div>
      )}
      <section className="grid cards">
        {stat("REQUESTS", m?.requests ?? 0)}
        {stat("TOKENS IN/OUT", `${m?.prompt_tokens ?? 0} / ${m?.completion_tokens ?? 0}`)}
        {stat("COST", `$${(m?.estimated_cost ?? 0).toFixed(4)}`)}
        {stat("DISAGREE", `${m?.disagreements ?? 0} (${(((m?.disagreement_rate ?? 0) * 100)).toFixed(1)}%)`)}
      </section>
      <div className="panel" style={{ marginTop: 14 }}>
        <strong>Triage playground</strong>
        <p className="sub" style={{ marginTop: 4, marginBottom: 10 }}>
          Paste a patient transcript and run the 3-agent consensus council (2 LLM assessors + protocol-based triage). The result shows each agent's decision and the final disposition.
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "flex-start" }}>
          <textarea
            className="input"
            rows={4}
            style={{ minWidth: 380, maxWidth: 600, resize: "vertical", fontFamily: "inherit", flex: 1 }}
            placeholder="Patient transcript — e.g. &quot;Since I left the hospital, I have new chest pain and cannot breathe well when I walk up stairs.&quot;"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button className="btn" onClick={runTriage} disabled={running || !text.trim()}>
              {running ? "Running…" : "▶ Run triage"}
            </button>
            <button className="btn ghost" onClick={() => { setText("I have new chest pain and cannot breathe well."); setTriage(null); }} style={{ fontSize: 12, padding: "6px 12px" }}>
              Reset to chest pain
            </button>
            <button className="btn ghost" onClick={() => { setText("I feel fine, no new symptoms since discharge."); setTriage(null); }} style={{ fontSize: 12, padding: "6px 12px" }}>
              Reset to routine
            </button>
          </div>
        </div>
        {triage && (
          <div className="panel" style={{ marginTop: 14, borderLeft: "4px solid var(--brand)" }}>
            <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
              <span className="label" style={{ fontSize: 11 }}>FINAL DISPOSITION</span>
              <span className={statusPill(triage.final_status)} style={{ fontSize: 14, padding: "6px 14px" }}>
                {statusLabel(triage.final_status)}
              </span>
              {triage.disagreement && <span className="pill amber" style={{ fontSize: 13 }}>DISAGREEMENT between agents</span>}
              {triage.human_escalation && <span className="pill red" style={{ fontSize: 13 }}>HUMAN ESCALATION REQUIRED</span>}
              {!triage.human_escalation && <span className="pill green" style={{ fontSize: 13 }}>No escalation needed</span>}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 4 }}>
              <div className="card" style={{ padding: 12, flex: "1 1 200px" }}>
                <div className="label">DECISIONS ({triage.decisions.length} agents)</div>
                {triage.decisions.map((d, i) => (
                  <div key={i} style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 2 }}>Agent {i + 1}: {d.status.toUpperCase()}</div>
                    <div style={{ fontSize: 13 }}>{d.rationale}</div>
                    {d.protocol_citations.length > 0 && (
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>Protocol citations: {d.protocol_citations.length} docs</div>
                    )}
                  </div>
                ))}
              </div>
              {triage.decisions.some(d => d.protocol_citations.length > 0) && (
                <div className="card" style={{ padding: 12, flex: "0 0 auto", maxWidth: 240 }}>
                  <div className="label">PROTOCOL CITATIONS</div>
                  <div style={{ fontSize: 12, marginTop: 6 }}>
                    {new Set(triage.decisions.flatMap(d => d.protocol_citations)).size} unique protocol documents retrieved from the hospital knowledge base.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <strong>Recent AI decisions</strong>
        <div style={{ marginTop: 8 }}>
          {logs.length === 0 && <p className="sub">No AI decisions logged yet.</p>}
          <div className="table-wrap"><table className="table">
            <thead><tr><th>When</th><th>Agent</th><th>Model</th><th>Tokens (in/out)</th><th>Decision</th></tr></thead>
            <tbody>{logs.map((l) => (
              <tr key={l.id}>
                <td style={{ fontSize: 12, whiteSpace: "nowrap" }}>{fmtDate(l.at)}</td>
                <td><strong>{l.agent}</strong></td>
                <td style={{ fontSize: 12 }}>{l.model}</td>
                <td style={{ fontSize: 12 }}>{l.tokens?.[0] ?? "?"} / {l.tokens?.[1] ?? "?"}</td>
                <td>
                  {l.disagreement
                    ? <span className="pill amber">DISAGREED → escalated</span>
                    : <span className="pill green">agreed</span>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      </div>
    </Page>);
}

