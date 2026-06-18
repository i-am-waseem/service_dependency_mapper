"""
Tests for graph algorithms in graph_service.py.

These are pure logic tests — no network, no LLM, no mocking needed.
We build minimal graphs directly and assert the algorithms are correct.
"""
import pytest
from app.models.service import ServiceMetadata, ServiceNode, DependencyEdge, ServiceType
from app.services import graph_service


def _load(services: list[ServiceNode], deps: list[DependencyEdge]) -> None:
    graph_service.load_graph(ServiceMetadata(services=services, dependencies=deps))


def _svc(name: str, has_metrics: bool = True, has_logging: bool = True) -> ServiceNode:
    return ServiceNode(
        name=name,
        type=ServiceType.BACKEND,
        language="python",
        has_metrics=has_metrics,
        has_logging=has_logging,
        health_check="/health",
    )


# ── SPOF detection ─────────────────────────────────────────────────────────────

def test_spof_detected_when_in_degree_meets_threshold():
    # A  B  C  all call gateway → in_degree = 3 → SPOF
    _load(
        services=[_svc("gateway"), _svc("A"), _svc("B"), _svc("C")],
        deps=[
            DependencyEdge(source="A", target="gateway"),
            DependencyEdge(source="B", target="gateway"),
            DependencyEdge(source="C", target="gateway"),
        ],
    )
    results = graph_service.find_single_points_of_failure(threshold=2)
    names = [r["service"] for r in results]
    assert "gateway" in names


def test_no_spof_when_under_threshold():
    # Only one service calls gateway → in_degree = 1 → not a SPOF
    _load(
        services=[_svc("gateway"), _svc("caller")],
        deps=[DependencyEdge(source="caller", target="gateway")],
    )
    results = graph_service.find_single_points_of_failure(threshold=2)
    assert results == []


# ── Tight coupling ─────────────────────────────────────────────────────────────

def test_tight_coupling_detected_for_bidirectional_dependency():
    _load(
        services=[_svc("A"), _svc("B")],
        deps=[
            DependencyEdge(source="A", target="B"),
            DependencyEdge(source="B", target="A"),
        ],
    )
    results = graph_service.find_tight_coupling()
    assert len(results) == 1
    pair = {results[0]["service_a"], results[0]["service_b"]}
    assert pair == {"A", "B"}


def test_no_tight_coupling_for_unidirectional_dependency():
    _load(
        services=[_svc("A"), _svc("B")],
        deps=[DependencyEdge(source="A", target="B")],
    )
    assert graph_service.find_tight_coupling() == []


# ── Risk scoring ───────────────────────────────────────────────────────────────

def test_risk_score_elevated_by_missing_observability():
    # hub: in=2, out=1 → base score = 2. Missing metrics adds +2 → score = 4 → flagged
    _load(
        services=[
            _svc("hub", has_metrics=False, has_logging=True),
            _svc("A"), _svc("B"), _svc("downstream"),
        ],
        deps=[
            DependencyEdge(source="A",    target="hub"),
            DependencyEdge(source="B",    target="hub"),
            DependencyEdge(source="hub",  target="downstream"),
        ],
    )
    results = graph_service.score_dependency_risk()
    flagged = [r["service"] for r in results]
    assert "hub" in flagged


def test_isolated_service_not_flagged():
    # A service with no edges has score 0 — should not be flagged
    _load(services=[_svc("standalone")], deps=[])
    assert graph_service.score_dependency_risk() == []
