import { useState } from "react";
import type { GraphNode } from "../api/client";

interface Props {
  nodes: GraphNode[];
  selectedService: string | null;
  onSelect: (name: string) => void;
}

const RISK_COLOR: Record<string, string> = {
  low: "#22c55e",
  medium: "#f59e0b",
  high: "#ef4444",
  critical: "#dc2626",
};

const LANG_ICON: Record<string, string> = {
  python: "🐍",
  javascript: "⚛",
  unknown: "·",
};

export default function ServiceList({ nodes, selectedService, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const filtered = nodes.filter((n) =>
    n.label.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ position: "relative" }}>
        <input
          placeholder="Search services…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            width: "100%",
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            color: "#e2e8f0",
            padding: "7px 10px 7px 32px",
            fontSize: 12,
            outline: "none",
            boxSizing: "border-box" as const,
          }}
        />
        <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)",
                       color: "#475569", fontSize: 12 }}>⌕</span>
      </div>

      <div style={{ fontSize: 10, color: "#475569", fontWeight: 600, padding: "4px 2px",
                    textTransform: "uppercase" as const, letterSpacing: "0.08em" }}>
        {filtered.length} service{filtered.length !== 1 ? "s" : ""}
      </div>

      {filtered.map((n) => {
        const selected = selectedService === n.id;
        const riskColor = RISK_COLOR[n.risk_level] ?? "#64748b";
        return (
          <div
            key={n.id}
            onClick={() => onSelect(n.id)}
            style={{
              background: selected ? "#0f2040" : "#0a0f1a",
              border: `1px solid ${selected ? "#3b82f6" : "#1e293b"}`,
              borderLeft: `3px solid ${selected ? "#3b82f6" : riskColor}`,
              borderRadius: 8,
              padding: "9px 10px",
              cursor: "pointer",
              transition: "border-color 0.15s",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 600, fontSize: 12, color: "#e2e8f0" }}>
                {LANG_ICON[n.language] ?? "·"} {n.label}
              </span>
              <span style={{
                background: riskColor + "22",
                border: `1px solid ${riskColor}55`,
                color: riskColor,
                borderRadius: 4,
                padding: "1px 5px",
                fontSize: 9,
                fontWeight: 800,
                textTransform: "uppercase" as const,
              }}>
                {n.risk_level}
              </span>
            </div>
            <div style={{ marginTop: 4, display: "flex", gap: 8, fontSize: 10, color: "#475569" }}>
              <span>{n.type}</span>
              <span>↓{n.in_degree} ↑{n.out_degree}</span>
              {!n.has_metrics && <span style={{ color: "#ef444488" }}>no metrics</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
