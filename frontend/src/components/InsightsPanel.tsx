import type { AnalysisResult, Finding } from "../api/client";

interface ServiceDetail {
  service: string;
  upstreams: string[];
  downstreams: string[];
  risk_level: string;
}

interface Props {
  result: AnalysisResult | null;
  status: "pending" | "running" | "completed" | "failed" | null;
  selectedService: string | null;
  serviceDetail: ServiceDetail | null;
}

const SEVERITY_COLOR: Record<string, string> = {
  low:      "#22c55e",
  medium:   "#f59e0b",
  high:     "#ef4444",
  critical: "#dc2626",
};

const RISK_COLOR: Record<string, string> = {
  low: "#22c55e", medium: "#f59e0b", high: "#ef4444", critical: "#dc2626",
};

const CATEGORY_LABEL: Record<string, string> = {
  spof:                  "Single Point of Failure",
  tight_coupling:        "Tight Coupling",
  risky_dep:             "Risky Dependency",
  missing_observability: "Missing Observability",
};

function Spinner() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", height: 240, gap: 16 }}>
      <div style={{
        width: 36, height: 36,
        border: "3px solid #1e293b", borderTop: "3px solid #3b82f6",
        borderRadius: "50%", animation: "spin 0.9s linear infinite",
      }} />
      <p style={{ color: "#64748b", fontSize: 13 }}>AI analysis running…</p>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// A single finding card.
// hideService=true when the service name is already shown in the context header above it.
function FindingCard({ f, highlighted, hideService }: {
  f: Finding;
  highlighted?: boolean;
  hideService?: boolean;
}) {
  const color = SEVERITY_COLOR[f.severity] ?? "#64748b";
  return (
    <div style={{
      background: highlighted ? "#0f172a" : "#0a0e1a",
      border:     `1px solid ${highlighted ? color + "77" : color + "33"}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 8,
      padding: "10px 14px",
      marginBottom: 8,
      boxShadow: highlighted ? `0 0 12px ${color}22` : "none",
      transition: "box-shadow 0.2s",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "flex-start", gap: 8, marginBottom: 4 }}>
        <div>
          {!hideService && (
            <span style={{ fontWeight: 700, fontSize: 12, color: "#e2e8f0" }}>{f.service}</span>
          )}
          <span style={{ color: "#64748b", fontSize: 11, marginLeft: hideService ? 0 : 8 }}>
            {CATEGORY_LABEL[f.category] ?? f.category}
          </span>
        </div>
        <span style={{
          background: color + "22", border: `1px solid ${color}66`, color,
          borderRadius: 4, padding: "2px 7px",
          fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, flexShrink: 0,
        }}>
          {f.severity}
        </span>
      </div>
      <p style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6, margin: 0 }}>{f.detail}</p>
    </div>
  );
}

// Shown at top of right panel when a service is selected
function ServiceContextCard({ detail }: { detail: ServiceDetail }) {
  const riskColor = RISK_COLOR[detail.risk_level] ?? "#64748b";
  return (
    <div style={{
      background: "#0f172a",
      border: `1px solid ${riskColor}44`,
      borderLeft: `3px solid ${riskColor}`,
      borderRadius: 10,
      padding: "12px 16px",
      marginBottom: 16,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                    marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: "#f1f5f9" }}>
          {detail.service}
        </span>
        <span style={{
          background: riskColor + "22", border: `1px solid ${riskColor}55`, color: riskColor,
          borderRadius: 4, padding: "2px 8px",
          fontSize: 10, fontWeight: 800, textTransform: "uppercase" as const,
        }}>
          {detail.risk_level}
        </span>
      </div>

      {/* Connection chips */}
      <div style={{ display: "flex", gap: 16 }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: "#475569",
                        textTransform: "uppercase" as const, letterSpacing: "0.07em",
                        marginBottom: 5 }}>
            Upstream — calls this
          </div>
          <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
            {detail.upstreams?.length ? detail.upstreams.map(s => (
              <span key={s} style={{
                background: "#8b5cf611", border: "1px solid #8b5cf644",
                color: "#a78bfa", borderRadius: 5, padding: "2px 8px", fontSize: 11,
              }}>{s}</span>
            )) : <span style={{ fontSize: 11, color: "#334155" }}>none</span>}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: "#475569",
                        textTransform: "uppercase" as const, letterSpacing: "0.07em",
                        marginBottom: 5 }}>
            Downstream — called by this
          </div>
          <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 4 }}>
            {detail.downstreams?.length ? detail.downstreams.map(s => (
              <span key={s} style={{
                background: "#06b6d411", border: "1px solid #06b6d444",
                color: "#22d3ee", borderRadius: 5, padding: "2px 8px", fontSize: 11,
              }}>{s}</span>
            )) : <span style={{ fontSize: 11, color: "#334155" }}>none</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
      <h3 style={{ fontSize: 11, fontWeight: 700, color: "#64748b",
                   textTransform: "uppercase" as const, letterSpacing: "0.08em", margin: 0 }}>
        {title}
      </h3>
      {count !== undefined && (
        <span style={{ background: "#1e293b", color: "#94a3b8", borderRadius: 999,
                       padding: "1px 7px", fontSize: 10, fontWeight: 600 }}>
          {count}
        </span>
      )}
    </div>
  );
}

function Divider({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "14px 0 12px" }}>
      <div style={{ flex: 1, height: 1, background: "#1e293b" }} />
      <span style={{ fontSize: 10, color: "#334155", fontWeight: 600,
                     textTransform: "uppercase" as const, letterSpacing: "0.07em",
                     whiteSpace: "nowrap" as const }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: "#1e293b" }} />
    </div>
  );
}

function StatBubble({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ textAlign: "center" as const, display: "flex",
                  flexDirection: "column", alignItems: "center" }}>
      <span style={{ fontSize: 22, fontWeight: 800, color, lineHeight: 1 }}>{value}</span>
      <span style={{ fontSize: 9, color: "#64748b", fontWeight: 600,
                     textTransform: "uppercase" as const, letterSpacing: "0.06em", marginTop: 2 }}>
        {label}
      </span>
    </div>
  );
}

export default function InsightsPanel({ result, status, selectedService, serviceDetail }: Props) {
  if (status === "running" || status === "pending") {
    return (
      <div>
        {serviceDetail && <ServiceContextCard detail={serviceDetail} />}
        <Spinner />
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div>
        {serviceDetail && <ServiceContextCard detail={serviceDetail} />}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 160 }}>
          <p style={{ color: "#ef4444", fontSize: 13 }}>Analysis failed. Try again.</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div>
        {serviceDetail && <ServiceContextCard detail={serviceDetail} />}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 160 }}>
          <p style={{ color: "#475569", fontSize: 13, textAlign: "center" as const }}>
            Click "Run AI Analysis" to generate insights.
          </p>
        </div>
      </div>
    );
  }

  const allFindings: Finding[] = [
    ...result.single_points_of_failure,
    ...result.tight_coupling,
    ...result.risky_dependencies,
    ...result.missing_observability,
  ];

  const focusedFindings = selectedService
    ? allFindings.filter(f => f.service === selectedService)
    : [];
  const otherFindings = selectedService
    ? allFindings.filter(f => f.service !== selectedService)
    : allFindings;

  const criticalCount = allFindings.filter(f => f.severity === "critical").length;
  const highCount     = allFindings.filter(f => f.severity === "high").length;

  return (
    <div style={{ fontSize: 13, display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Service context card — shown when a node is clicked */}
      {serviceDetail && <ServiceContextCard detail={serviceDetail} />}

      {/* Risk summary */}
      {result.risk_summary && (
        <div style={{
          background: "#0f172a", border: "1px solid #334155",
          borderRadius: 10, padding: 16,
          display: "flex", gap: 16, alignItems: "flex-start",
        }}>
          <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
            {criticalCount > 0 && <StatBubble value={criticalCount} label="critical" color="#dc2626" />}
            {highCount > 0 && <StatBubble value={highCount} label="high" color="#ef4444" />}
            <StatBubble value={allFindings.length} label="total" color="#64748b" />
          </div>
          <p style={{ color: "#94a3b8", lineHeight: 1.7, margin: 0, fontSize: 12 }}>
            {result.risk_summary}
          </p>
        </div>
      )}

      {/* Findings section */}
      {allFindings.length > 0 && (
        <div>
          <SectionHeader title="Findings" count={allFindings.length} />

          {/* Focused findings for selected service */}
          {focusedFindings.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "#8b5cf6", fontWeight: 600,
                            marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%",
                               background: "#8b5cf6", display: "inline-block" }} />
                {focusedFindings.length} finding{focusedFindings.length > 1 ? "s" : ""} for {selectedService}
              </div>
              {focusedFindings.map((f, i) => (
                <FindingCard key={`focused-${i}`} f={f} highlighted hideService />
              ))}
            </>
          )}

          {/* No findings for the selected service */}
          {selectedService && focusedFindings.length === 0 && (
            <div style={{
              background: "#0a0e1a", border: "1px solid #22c55e33",
              borderLeft: "3px solid #22c55e", borderRadius: 8, padding: "10px 14px",
              marginBottom: 10, fontSize: 12, color: "#4ade80",
            }}>
              No issues detected for {selectedService}
            </div>
          )}

          {/* Divider before other findings */}
          {selectedService && otherFindings.length > 0 && (
            <Divider label={`${otherFindings.length} other finding${otherFindings.length > 1 ? "s" : ""}`} />
          )}

          {/* Other findings (or all findings when nothing is selected) */}
          {otherFindings.map((f, i) => (
            <FindingCard key={`other-${i}`} f={f} />
          ))}
        </div>
      )}

      {/* Architectural observations */}
      {result.architectural_observations && (
        <div>
          <SectionHeader title="Architectural Observations" />
          <div style={{
            background: "#0f172a", border: "1px solid #1e293b",
            borderRadius: 8, padding: 14,
            color: "#94a3b8", lineHeight: 1.8, fontSize: 12,
            whiteSpace: "pre-wrap" as const,
          }}>
            {result.architectural_observations}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {result.recommendations.length > 0 && (
        <div>
          <SectionHeader title="Recommendations" count={result.recommendations.length} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {result.recommendations.map((r, i) => (
              <div key={i} style={{
                background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: 8, padding: "10px 14px",
                display: "flex", gap: 12, alignItems: "flex-start",
              }}>
                <span style={{
                  background: "#1e3a5f", color: "#60a5fa", borderRadius: 6,
                  width: 22, height: 22, display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 10, fontWeight: 800, flexShrink: 0,
                }}>
                  {i + 1}
                </span>
                <span style={{ color: "#cbd5e1", lineHeight: 1.6, fontSize: 12 }}>{r}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
