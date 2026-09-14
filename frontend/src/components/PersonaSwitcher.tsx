"use client";
import { useState, useRef, useEffect } from "react";
import { useRole, ROLE_CONFIGS, Role } from "../context/RoleContext";

export default function PersonaSwitcher() {
  const { currentRole, setRole, config } = useRole();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const options = Object.values(ROLE_CONFIGS);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        className="btn ghost"
        onClick={() => setOpen((v) => !v)}
        style={{ display: "flex", alignItems: "center", gap: 6 }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        Viewing as {config.label} ▾
      </button>
      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            background: "white",
            border: "1px solid #dce7e4",
            borderRadius: 12,
            boxShadow: "0 8px 24px rgba(15,42,40,0.12)",
            minWidth: 220,
            zIndex: 30,
            overflow: "hidden",
          }}
        >
          {options.map((o) => (
            <button
              key={o.role}
              role="option"
              aria-selected={o.role === currentRole}
              onClick={() => {
                setRole(o.role as Role);
                setOpen(false);
              }}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                width: "100%",
                padding: "10px 14px",
                border: "none",
                background: o.role === currentRole ? "#f0faf8" : "white",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                color: "#0f2a28",
                textAlign: "left",
              }}
            >
              <span>{o.label}</span>
              {o.role === currentRole && <span className="pill green" style={{ fontSize: 10 }}>active</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
