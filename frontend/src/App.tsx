import { useState, useEffect, useRef, useCallback } from "react";
import { api, DependencyGraph, AnalysisJob } from "./api/client";
import DependencyGraphView from "./components/DependencyGraph";
import ServiceList from "./components/ServiceList";
import InsightsPanel from "./components/InsightsPanel";

// Starting widths in percent — must sum to 100
const DEFAULT_WIDTHS: [number, number, number] = [15, 45, 40];
const MIN_W = [10, 20, 20]; // minimum % per panel

export default function App() {
  const [graph, setGraph]                     = useState<DependencyGraph | null>(null);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [serviceDetail, setServiceDetail]     = useState<any>(null);
  const [job, setJob]                         = useState<AnalysisJob | null>(null);
  const [loadingData, setLoadingData]         = useState(false);
  const [loadingAI, setLoadingAI]             = useState(false);
  const [error, setError]                     = useState<string | null>(null);
  const [widths, setWidths]                   = useState<[number, number, number]>(DEFAULT_WIDTHS);
  const [isDragging, setIsDragging]           = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Data ─────────────────────────────────────────────────────────────────────
  const loadSample = async () => {
    setLoadingData(true);
    setError(null);
    setJob(null);
    setSelectedService(null);
    setServiceDetail(null);
    try {
      await api.loadSample();
      setGraph(await api.getGraph());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingData(false);
    }
  };

  const runAnalysis = async () => {
    if (!graph) return;
    setLoadingAI(true);
    setError(null);
    setJob(null);
    try {
      const { job_id } = await api.runAnalysis();
      setJob({ job_id, status: "pending", created_at: new Date().toISOString(),
               completed_at: null, result: null, error: null });
      pollRef.current = setInterval(async () => {
        try {
          const j = await api.getJob(job_id);
          setJob(j);
          if (j.status === "completed" || j.status === "failed") {
            clearInterval(pollRef.current!);
            setLoadingAI(false);
          }
        } catch {
          clearInterval(pollRef.current!);
          setLoadingAI(false);
        }
      }, 1500);
    } catch (e: any) {
      setError(e.message);
      setLoadingAI(false);
    }
  };

  useEffect(() => {
    if (!selectedService) { setServiceDetail(null); return; }
    api.getInsights(selectedService).then(setServiceDetail).catch(() => {});
  }, [selectedService]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ── Drag-to-resize ────────────────────────────────────────────────────────────
  // handle 0 = between Left & Middle; handle 1 = between Middle & Right
  const startResize = useCallback((handleIndex: 0 | 1) => (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    const startX   = e.clientX;
    const totalW   = containerRef.current?.getBoundingClientRect().width ?? window.innerWidth;
    const snapshot = [...widths] as [number, number, number];

    const onMove = (me: MouseEvent) => {
      const delta = ((me.clientX - startX) / totalW) * 100;

      if (handleIndex === 0) {
        // Resize left ↔ middle; right stays
        const sum = snapshot[0] + snapshot[1];
        const newLeft   = Math.max(MIN_W[0], Math.min(snapshot[0] + delta, sum - MIN_W[1]));
        const newMiddle = sum - newLeft;
        setWidths([newLeft, newMiddle, snapshot[2]]);
      } else {
        // Resize middle ↔ right; left stays
        const sum = snapshot[1] + snapshot[2];
        const newMiddle = Math.max(MIN_W[1], Math.min(snapshot[1] + delta, sum - MIN_W[2]));
        const newRight  = sum - newMiddle;
        setWidths([snapshot[0], newMiddle, newRight]);
      }
    };

    const onUp = () => {
      setIsDragging(false);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup",   onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup",   onUp);
  }, [widths]);

  const isAnalyzing = job?.status === "running" || job?.status === "pending";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh",
                  background: "#060b14", color: "#e2e8f0", overflow: "hidden",
                  userSelect: isDragging ? "none" : undefined }}>

      {/* Drag overlay — prevents ReactFlow / iframes swallowing mouse during resize */}
      {isDragging && (
        <div style={{ position: "fixed", inset: 0, zIndex: 9999, cursor: "col-resize" }} />
      )}

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header style={{
        padding: "0 20px", height: 52,
        borderBottom: "1px solid #1e293b", background: "#0a0f1a",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
          }}>⬡</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: "-0.01em" }}>
              Service Dependency Mapper
            </div>
            {graph && (
              <div style={{ fontSize: 10, color: "#475569" }}>
                {graph.service_count} services · {graph.edge_count} dependencies
                {job?.result && ` · ${[
                  ...job.result.single_points_of_failure,
                  ...job.result.risky_dependencies,
                ].filter(f => f.severity === "critical" || f.severity === "high").length} high/critical`}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {error && (
            <span style={{ fontSize: 11, color: "#ef4444", maxWidth: 260,
                           overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {error}
            </span>
          )}
          {graph && (
            <button onClick={runAnalysis} disabled={loadingAI} style={btn("#14532d", "#22c55e", loadingAI)}>
              {isAnalyzing ? <><Spin color="#22c55e" /> Analyzing…</> : "Run AI Analysis"}
            </button>
          )}
          <button onClick={loadSample} disabled={loadingData} style={btn("#1e293b", "#475569", loadingData)}>
            {loadingData ? <><Spin color="#94a3b8" /> Loading…</> : graph ? "Reload" : "Load Sample Data"}
          </button>
        </div>
      </header>

      {/* ── 3-column body ──────────────────────────────────────────────────── */}
      {graph ? (
        <div ref={containerRef} style={{ display: "flex", flex: 1, overflow: "hidden" }}>

          {/* Left — Services */}
          <aside style={{
            flex: `0 0 ${widths[0]}%`,
            position: "relative",
            background: "#0a0f1a",
            display: "flex", flexDirection: "column",
            overflow: "hidden",
          }}>
            <PanelHeader label="Services" />
            <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
              <ServiceList
                nodes={graph.nodes}
                selectedService={selectedService}
                onSelect={setSelectedService}
              />
            </div>
            <DragHandle onMouseDown={startResize(0)} />
          </aside>

          {/* Middle — Graph */}
          <main style={{
            flex: `0 0 ${widths[1]}%`,
            position: "relative",
            display: "flex", flexDirection: "column",
            overflow: "hidden",
          }}>
            <PanelHeader label="Dependency Graph" hint="Drag nodes · Click to trace" />
            <div style={{ flex: 1, overflow: "hidden" }}>
              <DependencyGraphView graph={graph} onNodeClick={setSelectedService} />
            </div>
            <DragHandle onMouseDown={startResize(1)} />
          </main>

          {/* Right — Insights */}
          <aside style={{
            flex: `0 0 ${widths[2]}%`,
            background: "#0a0f1a",
            display: "flex", flexDirection: "column",
            overflow: "hidden",
          }}>
            <PanelHeader
              label="AI Insights"
              badge={
                isAnalyzing           ? { text: "running",    color: "#f59e0b" }
                : job?.status === "completed" ? { text: "● complete", color: "#22c55e" }
                : undefined
              }
            />
            <div style={{ flex: 1, overflowY: "auto", padding: "14px 18px" }}>
              <InsightsPanel
                result={job?.result ?? null}
                status={job?.status ?? null}
                selectedService={selectedService}
                serviceDetail={serviceDetail}
              />
            </div>
          </aside>

        </div>
      ) : (
        <div style={{ flex: 1, display: "flex", alignItems: "center",
                      justifyContent: "center", flexDirection: "column", gap: 14 }}>
          {loadingData ? (
            <>
              <div style={{ width: 32, height: 32, borderRadius: "50%",
                            border: "3px solid #1e293b", borderTop: "3px solid #3b82f6",
                            animation: "spin 0.9s linear infinite" }} />
              <p style={{ color: "#475569", fontSize: 13 }}>Loading services…</p>
            </>
          ) : (
            <>
              <div style={{ fontSize: 36, opacity: 0.3 }}>⬡</div>
              <p style={{ color: "#475569", fontSize: 13 }}>No data loaded yet</p>
              <button onClick={loadSample} style={btn("#1e3a5f", "#3b82f6", false)}>
                Load Sample Data
              </button>
            </>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
      `}</style>
    </div>
  );
}

// ── Drag handle between panels ────────────────────────────────────────────────

function DragHandle({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseDown={onMouseDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position:  "absolute",
        top: 0, right: -4, bottom: 0,
        width:     8,
        cursor:    "col-resize",
        zIndex:    20,
        display:   "flex",
        alignItems: "stretch",
        justifyContent: "center",
      }}
    >
      {/* Visual line */}
      <div style={{
        width:      2,
        background: hovered ? "#3b82f6" : "#1e293b",
        transition: "background 0.15s",
      }} />
      {/* Drag dots hint on hover */}
      {hovered && (
        <div style={{
          position:   "absolute",
          top: "50%", left: "50%",
          transform:  "translate(-50%, -50%)",
          display:    "flex",
          flexDirection: "column",
          gap:        3,
          pointerEvents: "none",
        }}>
          {[0,1,2].map(i => (
            <div key={i} style={{ width: 2, height: 2, borderRadius: "50%",
                                   background: "#3b82f6" }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Panel header ──────────────────────────────────────────────────────────────

function PanelHeader({ label, hint, badge }: {
  label: string;
  hint?: string;
  badge?: { text: string; color: string };
}) {
  return (
    <div style={{
      padding: "9px 14px 8px", borderBottom: "1px solid #1e293b",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexShrink: 0,
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#475569",
                     textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {label}
      </span>
      {hint && <span style={{ fontSize: 10, color: "#334155" }}>{hint}</span>}
      {badge && (
        <span style={{ display: "flex", alignItems: "center", gap: 5,
                       fontSize: 10, color: badge.color }}>
          {badge.text.startsWith("●")
            ? badge.text
            : <><Spin color={badge.color} />{badge.text}</>}
        </span>
      )}
    </div>
  );
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function Spin({ color }: { color: string }) {
  return (
    <span style={{
      display: "inline-block", width: 10, height: 10, borderRadius: "50%",
      border: `2px solid ${color}33`, borderTop: `2px solid ${color}`,
      animation: "spin 0.9s linear infinite", flexShrink: 0,
    }} />
  );
}

function btn(bg: string, border: string, disabled: boolean): React.CSSProperties {
  return {
    background: disabled ? "#1e293b" : bg,
    border:     `1px solid ${disabled ? "#334155" : border}`,
    color:      disabled ? "#475569" : "#e2e8f0",
    borderRadius: 7, padding: "6px 12px",
    fontSize: 12, fontWeight: 500,
    cursor:   disabled ? "not-allowed" : "pointer",
    display:  "flex", alignItems: "center", gap: 6,
    opacity:  disabled ? 0.7 : 1,
  };
}
