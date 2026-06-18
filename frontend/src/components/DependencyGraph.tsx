import { useState, useEffect, useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  NodeProps,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import type { DependencyGraph as GraphData, GraphNode } from "../api/client";

interface Props {
  graph: GraphData;
  onNodeClick: (name: string) => void;
}

// ─── Risk indicator ────────────────────────────────────────────────────────────
const RISK_COLOR: Record<string, string> = {
  low:      "#22c55e",
  medium:   "#f59e0b",
  high:     "#ef4444",
  critical: "#dc2626",
};

// Type accent — left border stripe colour only
const TYPE_ACCENT: Record<string, string> = {
  frontend: "#3b82f6",
  backend:  "#475569",
};

const LANG_ICON: Record<string, string> = {
  python:     "🐍",
  javascript: "⚛",
  unknown:    "·",
};

// ─── Custom node card ──────────────────────────────────────────────────────────
function ServiceNodeCard({ data }: NodeProps) {
  const { selected, dimmed, upstream, downstream } = data as {
    label: string; type: string; language: string; risk_level: string;
    in_degree: number; out_degree: number; has_metrics: boolean;
    has_logging: boolean; health_check: string | null;
    selected: boolean; dimmed: boolean; upstream: boolean; downstream: boolean;
  };

  const riskColor  = RISK_COLOR[data.risk_level] ?? "#64748b";
  const typeAccent = TYPE_ACCENT[data.type] ?? "#475569";

  // Border & glow driven by selection state, not risk
  let borderColor = "#1e293b";
  let boxShadow   = "none";
  let opacity     = dimmed ? 0.2 : 1;

  if (selected) {
    borderColor = "#f8fafc";
    boxShadow   = "0 0 0 2px #f8fafc, 0 0 20px rgba(248,250,252,0.25)";
  } else if (upstream) {
    borderColor = "#8b5cf6";
    boxShadow   = "0 0 10px rgba(139,92,246,0.35)";
  } else if (downstream) {
    borderColor = "#06b6d4";
    boxShadow   = "0 0 10px rgba(6,182,212,0.35)";
  }

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "#334155", width: 8, height: 8, border: "none" }}
      />
      <div style={{
        background:   "#111827",
        border:       `1px solid ${borderColor}`,
        borderLeft:   `4px solid ${typeAccent}`,
        borderRadius: 9,
        padding:      "10px 13px",
        minWidth:     155,
        opacity,
        boxShadow,
        transition:   "opacity 0.2s, box-shadow 0.2s, border-color 0.2s",
        cursor:       "pointer",
        userSelect:   "none" as const,
      }}>
        {/* Header row */}
        <div style={{ display: "flex", justifyContent: "space-between",
                      alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#f1f5f9",
                         letterSpacing: "-0.01em", whiteSpace: "nowrap" as const }}>
            {LANG_ICON[data.language] ?? "·"} {data.label}
          </span>
          {/* Risk dot — subtle, not dominant */}
          <span title={`Risk: ${data.risk_level}`} style={{
            width: 8, height: 8, borderRadius: "50%",
            background: riskColor, flexShrink: 0,
            boxShadow: `0 0 4px ${riskColor}88`,
          }} />
        </div>

        {/* Meta row */}
        <div style={{ fontSize: 10, color: "#64748b", display: "flex",
                      gap: 8, alignItems: "center" }}>
          <span style={{ textTransform: "uppercase" as const,
                         letterSpacing: "0.06em", fontWeight: 600 }}>
            {data.type}
          </span>
          <span>·</span>
          <span>{data.language}</span>
        </div>

        {/* Connectivity row */}
        <div style={{ marginTop: 6, display: "flex", gap: 10, fontSize: 10, color: "#475569" }}>
          <span title="services that call this one">
            <span style={{ color: "#8b5cf6" }}>↓</span> {data.in_degree} upstream
          </span>
          <span title="services this one calls">
            <span style={{ color: "#06b6d4" }}>→</span> {data.out_degree} downstream
          </span>
        </div>

      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "#334155", width: 8, height: 8, border: "none" }}
      />
    </>
  );
}

const NODE_TYPES = { serviceNode: ServiceNodeCard };

// ─── Layout: topological layers ───────────────────────────────────────────────
function computeLayout(nodes: GraphNode[], edges: { source: string; target: string }[]) {
  // BFS from roots (nodes with no incoming edges) to assign depth layers
  const inDegree: Record<string, number> = {};
  const children: Record<string, string[]> = {};
  nodes.forEach(n => { inDegree[n.id] = 0; children[n.id] = []; });
  edges.forEach(e => {
    inDegree[e.target] = (inDegree[e.target] ?? 0) + 1;
    children[e.source] = [...(children[e.source] ?? []), e.target];
  });

  const layer: Record<string, number> = {};
  const queue = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id);
  queue.forEach(id => { layer[id] = 0; });

  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    for (const child of (children[cur] ?? [])) {
      layer[child] = Math.max(layer[child] ?? 0, (layer[cur] ?? 0) + 1);
      queue.push(child);
    }
  }
  // Any node not reached (cycle) gets its own layer
  nodes.forEach(n => { if (layer[n.id] === undefined) layer[n.id] = 0; });

  // Group nodes by layer and space them out
  const byLayer: Record<number, string[]> = {};
  nodes.forEach(n => {
    const l = layer[n.id];
    byLayer[l] = [...(byLayer[l] ?? []), n.id];
  });

  const H_GAP = 200;
  const V_GAP = 160;
  const positions: Record<string, { x: number; y: number }> = {};
  Object.entries(byLayer).forEach(([l, ids]) => {
    const totalWidth = (ids.length - 1) * H_GAP;
    ids.forEach((id, i) => {
      positions[id] = { x: i * H_GAP - totalWidth / 2 + 400, y: Number(l) * V_GAP + 60 };
    });
  });

  return positions;
}

// ─── Main component ────────────────────────────────────────────────────────────
export default function DependencyGraph({ graph, onNodeClick }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Compute upstream/downstream sets for the selected node
  const upstream   = new Set(graph.edges.filter(e => e.target === selectedId).map(e => e.source));
  const downstream = new Set(graph.edges.filter(e => e.source === selectedId).map(e => e.target));
  const hasSelection = selectedId !== null;

  // Build RF nodes/edges, applying selection-driven styles
  const buildNodes = useCallback((): Node[] => {
    const positions = computeLayout(graph.nodes, graph.edges);
    return graph.nodes.map(n => ({
      id:       n.id,
      type:     "serviceNode",
      position: positions[n.id] ?? { x: 0, y: 0 },
      data: {
        label:        n.label,
        type:         n.type,
        language:     n.language,
        risk_level:   n.risk_level,
        in_degree:    n.in_degree,
        out_degree:   n.out_degree,
        has_metrics:  n.has_metrics,
        has_logging:  n.has_logging,
        health_check: n.health_check,
        selected:     n.id === selectedId,
        dimmed:       hasSelection && n.id !== selectedId && !upstream.has(n.id) && !downstream.has(n.id),
        upstream:     upstream.has(n.id),
        downstream:   downstream.has(n.id),
      },
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, selectedId]);

  const buildEdges = useCallback((): Edge[] => {
    return graph.edges.map((e, i) => {
      const id       = `${e.source}-${e.target}-${i}`;
      const isUp     = e.target === selectedId;   // leads INTO selected
      const isDown   = e.source === selectedId;   // goes OUT OF selected
      const relevant = isUp || isDown;
      const dimmed   = hasSelection && !relevant;

      let stroke   = "#2d3a4a";
      let animated = false;
      let markerColor = "#2d3a4a";

      if (isUp)   { stroke = "#8b5cf6"; markerColor = "#8b5cf6"; animated = true; }
      if (isDown) { stroke = "#06b6d4"; markerColor = "#06b6d4"; animated = true; }
      if (dimmed) { stroke = "#1a2330"; markerColor = "#1a2330"; }

      return {
        id,
        source:    e.source,
        target:    e.target,
        animated,
        markerEnd: { type: MarkerType.ArrowClosed, color: markerColor, width: 14, height: 14 },
        style:     { stroke, strokeWidth: relevant ? 2 : 1.5, opacity: dimmed ? 0.3 : 1,
                     transition: "stroke 0.2s, opacity 0.2s" },
      };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, selectedId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(buildNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState(buildEdges());

  // Rebuild nodes/edges when graph data changes (re-layout)
  useEffect(() => {
    setNodes(buildNodes());
    setEdges(buildEdges());
    setSelectedId(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  // Re-apply styles only (no position change) when selection changes
  useEffect(() => {
    setNodes(prev => prev.map(n => {
      const isSelected  = n.id === selectedId;
      const isUpstream  = upstream.has(n.id);
      const isDownstream = downstream.has(n.id);
      const isDimmed    = hasSelection && !isSelected && !isUpstream && !isDownstream;
      return {
        ...n,
        data: { ...n.data, selected: isSelected, dimmed: isDimmed,
                upstream: isUpstream, downstream: isDownstream },
      };
    }));
    setEdges(buildEdges());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const id = node.id;
    setSelectedId(prev => prev === id ? null : id);  // toggle
    onNodeClick(id);
  }, [onNodeClick]);

  const handlePaneClick = useCallback(() => {
    setSelectedId(null);
  }, []);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%",
                  background: "#080e18" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.35 }}
        minZoom={0.3}
        nodesDraggable
        panOnDrag
      >
        <Background color="#111827" gap={28} size={1} />
        <Controls
          showInteractive={false}
          style={{ background: "#111827", border: "1px solid #1e293b",
                   borderRadius: 8, overflow: "hidden" }}
        />
      </ReactFlow>

      {/* Legend */}
      <div style={{
        position:   "absolute", top: 12, right: 12,
        background: "#0d1420cc", backdropFilter: "blur(8px)",
        border:     "1px solid #1e293b", borderRadius: 8,
        padding:    "8px 12px", display: "flex", flexDirection: "column", gap: 5,
        fontSize:   10, color: "#64748b", pointerEvents: "none",
      }}>
        <div style={{ fontWeight: 700, color: "#475569", marginBottom: 2,
                      textTransform: "uppercase", letterSpacing: "0.07em" }}>
          Click a node
        </div>
        <LegendRow color="#8b5cf6" label="Upstream (calls it)" />
        <LegendRow color="#06b6d4" label="Downstream (it calls)" />
        <LegendRow color="#f8fafc" label="Selected" />
        <div style={{ borderTop: "1px solid #1e293b", marginTop: 4, paddingTop: 6 }}>
          <div style={{ fontWeight: 700, color: "#475569", marginBottom: 4,
                        textTransform: "uppercase", letterSpacing: "0.07em" }}>
            Risk
          </div>
          {Object.entries(RISK_COLOR).map(([k, v]) => (
            <LegendRow key={k} color={v} label={k} isDot />
          ))}
        </div>
      </div>

      <style>{`
        .react-flow__node { cursor: grab; }
        .react-flow__node:active { cursor: grabbing; }
        .react-flow__controls-button { background: #111827 !important; border-bottom-color: #1e293b !important; color: #94a3b8 !important; }
        .react-flow__controls-button:hover { background: #1e293b !important; }
        .react-flow__controls-button svg { fill: #94a3b8 !important; }
      `}</style>
    </div>
  );
}

function LegendRow({ color, label, isDot = false }: { color: string; label: string; isDot?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {isDot ? (
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, flexShrink: 0 }} />
      ) : (
        <span style={{ width: 16, height: 2, background: color, borderRadius: 2, flexShrink: 0 }} />
      )}
      <span style={{ color: "#64748b", textTransform: "capitalize" }}>{label}</span>
    </div>
  );
}
