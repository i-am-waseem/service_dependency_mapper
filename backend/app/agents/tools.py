"""
Deterministic, rule-based analysis tools.
These run before the LLM — the LLM interprets and extends their output,
not the other way around. This keeps LLM calls grounded and cheap.
"""
from app.models.graph import Finding, RiskLevel
from app.services import graph_service
from app.config import settings


def run_spof_check() -> list[Finding]:
    raw = graph_service.find_single_points_of_failure(
        threshold=settings.spof_in_degree_threshold
    )
    return [
        Finding(
            service=r["service"],
            severity=RiskLevel.CRITICAL if r["in_degree"] >= 3 else RiskLevel.HIGH,
            category="spof",
            detail=r["detail"],
        )
        for r in raw
    ]


def run_tight_coupling_check() -> list[Finding]:
    raw = graph_service.find_tight_coupling()
    return [
        Finding(
            service=f"{r['service_a']} <-> {r['service_b']}",
            severity=RiskLevel.HIGH,
            category="tight_coupling",
            detail=r["detail"],
        )
        for r in raw
    ]


def run_risk_scoring() -> list[Finding]:
    raw = graph_service.score_dependency_risk()
    return [
        Finding(
            service=r["service"],
            severity=RiskLevel.HIGH if r["risk_score"] >= 6 else RiskLevel.MEDIUM,
            category="risky_dep",
            detail=r["detail"],
        )
        for r in raw
    ]


def run_observability_check() -> list[Finding]:
    raw = graph_service.find_missing_observability()
    return [
        Finding(
            service=r["service"],
            severity=RiskLevel.MEDIUM,
            category="missing_observability",
            detail=r["detail"],
        )
        for r in raw
    ]


def run_all() -> dict[str, list[Finding]]:
    return {
        "single_points_of_failure": run_spof_check(),
        "tight_coupling": run_tight_coupling_check(),
        "risky_dependencies": run_risk_scoring(),
        "missing_observability": run_observability_check(),
    }
