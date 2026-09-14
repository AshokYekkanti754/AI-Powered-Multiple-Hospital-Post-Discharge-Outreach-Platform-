"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../../lib/api";
export default function LiveCampaignPage() {
  const [events, setEvents] = useState<unknown>(null);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try { const q = await apiFetch("/api/v1/queue/status"); if (alive) setEvents(q); } catch { /* keep last */ }
    };
    poll();
    const api = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/^http/, "ws");
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(`${api}/api/v1/ws/queue-stream`);
      ws.onmessage = (m) => { try { setEvents(JSON.parse(m.data)); } catch { /* ignore */ } };
    } catch { /* polling fallback */ }
    const t = window.setInterval(poll, 3000);
    return () => { alive = false; window.clearInterval(t); try { ws?.close(); } catch { /* noop */ } };
  }, []);
  return (
    <Page kicker="LIVE QUEUE" title="Campaign activity" sub="WebSocket stream with 3s polling fallback.">
      <pre className="code">{JSON.stringify(events, null, 2) ?? "Connecting…"}</pre>
    </Page>);
}

