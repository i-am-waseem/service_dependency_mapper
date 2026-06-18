"""
Builds and queries a NetworkX directed graph from ServiceMetadata.
All graph algorithms (centrality, cycle detection, risk scoring) live here.
The LLM layer never runs graph math — it only interprets what this module produces.
"""
import networkx as nx
import structlog
from typing import Optional

from app.models.service import ServiceMetadata, ServiceNode
from app.models.graph import DependencyGraph, GraphNode, GraphEdge, RiskLevel

logger = structlog.get_logger(__name__)

# Module-level in-memory state (swappable to persistence later)
_graph: nx.DiGraph = nx.DiGraph()
_service_metadata: dict[str, ServiceNode] = {}


def load_graph(metadata: ServiceMetadata) -> None:
    global _graph, _service_metadata
    _graph = nx.DiGraph()
    _service_metadata = {s.name: s for s in metadata.services}

    for svc in metadata.services:
        _graph.add_node(svc.name)

    for dep in metadata.dependencies:
        _graph.add_edge(dep.source, dep.target,
                        protocol=dep.protocol,
                        endpoints_called=dep.endpoints_called)

    logger.info("graph_loaded",
                nodes=_graph.number_of_nodes(),
                edges=_graph.number_of_edges())


def get_graph() -> DependencyGraph:
    nodes = []
    for name in _graph.nodes():
        meta = _service_metadata.get(name)
        in_d = _graph.in_degree(name)
        out_d = _graph.out_degree(name)
        nodes.append(GraphNode(
            id=name,
            label=name,
            type=meta.type.value if meta else "backend",
            language=meta.language if meta else "unknown",
            risk_level=_compute_risk_level(name),
            in_degree=in_d,
            out_degree=out_d,
            has_metrics=meta.has_metrics if meta else False,
            has_logging=meta.has_logging if meta else False,
            health_check=meta.health_check if meta else None,
        ))

    edges = []
    for src, tgt, data in _graph.edges(data=True):
        edges.append(GraphEdge(
            source=src,
            target=tgt,
            protocol=data.get("protocol", "REST"),
            endpoints_called=data.get("endpoints_called", []),
        ))

    return DependencyGraph(
        nodes=nodes,
        edges=edges,
        service_count=len(nodes),
        edge_count=len(edges),
    )


def get_service_relationships(service_name: str) -> dict:
    if service_name not in _graph:
        return {}
    upstreams = list(_graph.predecessors(service_name))   # who calls this service
    downstreams = list(_graph.successors(service_name))   # who this service calls
    return {
        "service": service_name,
        "upstreams": upstreams,
        "downstreams": downstreams,
        "in_degree": _graph.in_degree(service_name),
        "out_degree": _graph.out_degree(service_name),
        "risk_level": _compute_risk_level(service_name).value,
    }


def get_all_service_names() -> list[str]:
    return list(_graph.nodes())


def is_loaded() -> bool:
    return _graph.number_of_nodes() > 0


def reset() -> None:
    """Reset all graph state. Used in tests to ensure isolation between test cases."""
    global _graph, _service_metadata
    _graph = nx.DiGraph()
    _service_metadata = {}


# ---------------------------------------------------------------------------
# Graph algorithms used by the agent tools layer
# ---------------------------------------------------------------------------

def find_single_points_of_failure(threshold: int = 2) -> list[dict]:
    """Services where in_degree > threshold and no redundancy annotation."""
    results = []
    for node in _graph.nodes():
        in_d = _graph.in_degree(node)
        if in_d >= threshold:
            dependents = list(_graph.predecessors(node))
            results.append({
                "service": node,
                "in_degree": in_d,
                "dependents": dependents,
                "detail": (
                    f"{node} is depended on by {in_d} services "
                    f"({', '.join(dependents)}). A failure here cascades to all of them."
                ),
            })
    return results


def find_tight_coupling() -> list[dict]:
    """Pairs of services that call each other bidirectionally."""
    results = []
    checked = set()
    for src, tgt in _graph.edges():
        pair = tuple(sorted([src, tgt]))
        if pair in checked:
            continue
        if _graph.has_edge(tgt, src):
            checked.add(pair)
            results.append({
                "service_a": src,
                "service_b": tgt,
                "detail": (
                    f"{src} and {tgt} call each other — circular dependency. "
                    "This creates tight coupling and complicates deployment ordering."
                ),
            })
    return results


def find_cycles() -> list[list[str]]:
    return list(nx.simple_cycles(_graph))


def score_dependency_risk() -> list[dict]:
    """Heuristic risk score: (in_degree * out_degree) + missing observability penalty."""
    results = []
    for node in _graph.nodes():
        meta = _service_metadata.get(node)
        in_d = _graph.in_degree(node)
        out_d = _graph.out_degree(node)
        score = in_d * max(out_d, 1)
        if meta and not meta.has_metrics:
            score += 2
        if meta and not meta.has_logging:
            score += 1
        if score >= 4:
            results.append({
                "service": node,
                "risk_score": score,
                "in_degree": in_d,
                "out_degree": out_d,
                "detail": f"{node} has risk score {score} (high fan-in × fan-out).",
            })
    return results


def find_missing_observability() -> list[dict]:
    results = []
    for node in _graph.nodes():
        meta = _service_metadata.get(node)
        if meta is None:
            continue
        issues = []
        if not meta.has_metrics:
            issues.append("no metrics endpoint")
        if not meta.has_logging:
            issues.append("no structured logging")
        if not meta.health_check:
            issues.append("no health check")
        if issues:
            results.append({
                "service": node,
                "issues": issues,
                "detail": f"{node} is missing: {', '.join(issues)}.",
            })
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_risk_level(name: str) -> RiskLevel:
    in_d = _graph.in_degree(name)
    meta = _service_metadata.get(name)
    missing_obs = meta and (not meta.has_metrics or not meta.health_check)
    if in_d >= 3 or (in_d >= 2 and missing_obs):
        return RiskLevel.CRITICAL
    if in_d >= 2:
        return RiskLevel.HIGH
    if in_d == 1 and missing_obs:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


