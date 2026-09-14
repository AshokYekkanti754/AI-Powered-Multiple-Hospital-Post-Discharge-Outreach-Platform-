import Link from "next/link";
import { Nav } from "../lib/api";

const STEPS: [string, string, string][] = [
  ["Sign in", "/login", "One-click demo accounts (password Demo@123)"],
  ["Live dashboard", "/dashboard", "Capacity bar, KPIs, Run 10 AI calls"],
  ["Campaigns", "/campaigns", "Create → Start → queue fills → Pause"],
  ["Calls", "/calls", "AI transcripts, outcomes, triage"],
  ["Escalations", "/escalations", "Acknowledge / resolve urgent cases"],
  ["Patients", "/patients", "Directory, timeline, eligibility"],
  ["AI inspector", "/admin/ai-inspector", "Provider status, metrics, playground"],
  ["Safety", "/admin/safety", "30-case benchmark + report"],
  ["Health", "/admin/health", "Backend, queue, AI health"],
];

export default function HomePage() {
  return (
    <div className="app-shell">
      <Nav />
      <p className="kicker">MULTI-HOSPITAL OUTREACH OPERATIONS</p>
      <h1 className="h1">Post-discharge care, on autopilot — safely.</h1>
      <p className="sub">Queue-driven AI voice outreach with human-in-the-loop escalation. Works fully offline with mock AI + simulated voice.</p>
      <div className="hero">
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Start the 60-second demo</h3>
          <ol style={{ paddingLeft: 18 }}>
            {STEPS.slice(0, 4).map(([t, h, s]) => (
              <li key={h} style={{ marginBottom: 8 }}><Link href={h}><strong>{t}</strong></Link> — {s}</li>
            ))}
          </ol>
          <a className="btn" href="/dashboard" style={{ textDecoration: "none", display: "inline-block" }}>Open live dashboard →</a>
        </div>
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Everything else</h3>
          <ul style={{ paddingLeft: 18 }}>
            {STEPS.slice(4).map(([t, h, s]) => (
              <li key={h} style={{ marginBottom: 8 }}><Link href={h}><strong>{t}</strong></Link> — {s}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

