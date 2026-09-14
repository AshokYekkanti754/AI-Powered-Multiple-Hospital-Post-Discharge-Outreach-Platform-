"use client";

export function QueueCapacityMeter({ active, capacity }: { active: number; capacity: number }) {
  const ratio = capacity ? Math.min(1, active / capacity) : 0;
  return <div aria-label="Queue capacity"><div style={{ display: "flex", justifyContent: "space-between" }}><strong>Active Calls</strong><span>{active} / {capacity}</span></div><div style={{ height: 10, background: "#dbe4e2", marginTop: 8 }}><div style={{ width: `${ratio * 100}%`, height: "100%", background: ratio > 0.85 ? "#dc2626" : "#0f766e" }} /></div></div>;
}
