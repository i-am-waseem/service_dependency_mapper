from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GraphNode(BaseModel):
    id: str
    label: str
    type: str           # frontend | backend
    language: str
    risk_level: RiskLevel = RiskLevel.LOW
    in_degree: int = 0
    out_degree: int = 0
    has_metrics: bool = False
    has_logging: bool = False
    health_check: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    protocol: str = "REST"
    endpoints_called: list[str] = []


class DependencyGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    service_count: int = 0
    edge_count: int = 0


class Finding(BaseModel):
    service: str
    severity: RiskLevel
    category: str       # spof | tight_coupling | risky_dep | missing_observability | scaling
    detail: str


class AnalysisResult(BaseModel):
    single_points_of_failure: list[Finding]
    tight_coupling: list[Finding]
    risky_dependencies: list[Finding]
    missing_observability: list[Finding]
    architectural_observations: str
    recommendations: list[str]
    risk_summary: str


class AnalysisJob(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None
