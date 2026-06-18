const BASE = "";  // proxied by Vite dev server

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  language: string;
  risk_level: "low" | "medium" | "high" | "critical";
  in_degree: number;
  out_degree: number;
  has_metrics: boolean;
  has_logging: boolean;
  health_check: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  protocol: string;
  endpoints_called: string[];
}

export interface DependencyGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  service_count: number;
  edge_count: number;
}

export interface Finding {
  service: string;
  severity: string;
  category: string;
  detail: string;
}

export interface AnalysisResult {
  single_points_of_failure: Finding[];
  tight_coupling: Finding[];
  risky_dependencies: Finding[];
  missing_observability: Finding[];
  architectural_observations: string;
  recommendations: string[];
  risk_summary: string;
}

export interface AnalysisJob {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  result: AnalysisResult | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export const api = {
  loadSample: () =>
    request<{ loaded: boolean; services: number }>("/api/services/load/sample", { method: "POST" }),

  getGraph: () => request<DependencyGraph>("/api/graph"),

  getInsights: (service: string) =>
    request<{ service: string; upstreams: string[]; downstreams: string[]; risk_level: string }>(
      `/api/insights/${service}`
    ),

  runAnalysis: () =>
    request<{ job_id: string; status: string }>("/api/analysis/run", { method: "POST" }),

  getJob: (jobId: string) => request<AnalysisJob>(`/api/analysis/${jobId}`),
};
