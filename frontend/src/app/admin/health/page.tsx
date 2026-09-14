"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";
const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export default function HealthPage() {
  const [api, setApi] = useState<unknown>(null);
  const [queue, setQueue] = useState<unknown>(null);
  const [prov, setProv] = useState<unknown>(null);
  useEffect(() => {
    apiFetch("/api/v1/health").then(setApi).catch((e) => setApi({ error: String(e) }));
    apiFetch("/api/v1/queue/status").then(setQueue).catch((e) => setQueue({ error: String(e) }));
    apiFetch("/api/v1/ai/provider-status").then(setProv).catch((e) => setProv({ error: String(e) }));
  }, []);
  const ok = (v: unknown) => !!v && typeof v === "object" && !("error" in (v as Record<string, unknown>));
  const badge = (v: unknown) => <span className={ok(v) ? "pill green" : "pill red"}>{ok(v) ? "HEALTHY" : "UNREACHABLE"}</span>;
  const pre = (v: unknown) => <pre className="code">{JSON.stringify(v, null, 2)}</pre>;
  return (
    <Page kicker="SYSTEM STATUS" title="Health monitor" sub="Backend, queue and AI provider at a glance.">
      <div className="grid two">
        <div className="panel"><h3 style={{ marginTop: 0 }}>Backend API {badge(api)}</h3>{pre(api)}</div>
        <div className="panel"><h3 style={{ marginTop: 0 }}>Queue {badge(queue)}</h3>{pre(queue)}</div>
      </div>
      <div className="panel" style={{ marginTop: 14 }}>
        <h3 style={{ marginTop: 0 }}>AI provider {badge(prov)}</h3>{pre(prov)}
        <p className="sub">Dummy keys = offline mock, fully working. See docs/EXTERNAL_KEYS.md to go live.</p>
      </div>
      <p><a href={`${API}/docs`}>Backend /docs</a> · <a href={`${API}/health`}>/health</a></p>
    </Page>);
}

