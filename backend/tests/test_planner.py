"""
Tests for the agent planner (planner.py).

Key behaviours:
- Rule-only path works when no API key is configured
- LLM path is invoked when key is present and graph is non-trivial
- System never crashes when LLM fails — it falls back gracefully
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.models.service import ServiceMetadata, ServiceNode, DependencyEdge, ServiceType
from app.models.graph import AnalysisResult
from app.services import graph_service
from app.agents import planner


def _seed_graph() -> None:
    """Load a minimal 3-service graph so the planner has something to analyse."""
    graph_service.load_graph(ServiceMetadata(
        services=[
            ServiceNode(name="auth",     type=ServiceType.BACKEND,  language="python",
                        has_metrics=False, has_logging=True,  health_check="/health"),
            ServiceNode(name="api",      type=ServiceType.BACKEND,  language="python",
                        has_metrics=True,  has_logging=True,  health_check="/health"),
            ServiceNode(name="frontend", type=ServiceType.FRONTEND, language="javascript",
                        has_metrics=False, has_logging=False, health_check=None),
        ],
        dependencies=[
            DependencyEdge(source="frontend", target="api"),
            DependencyEdge(source="api",      target="auth"),
            DependencyEdge(source="frontend", target="auth"),
        ],
    ))


# ── Rule-only path ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_only_path_returns_valid_result_without_api_key():
    _seed_graph()
    with patch("app.agents.planner.settings") as mock_settings:
        mock_settings.gemini_api_key = ""   # no key → LLM skipped
        result = await planner.run_analysis()

    assert isinstance(result, AnalysisResult)
    # auth has in_degree=2 → should be flagged as SPOF
    spof_names = [f.service for f in result.single_points_of_failure]
    assert "auth" in spof_names
    # Fallback text is generated even without LLM
    assert len(result.architectural_observations) > 0
    assert len(result.recommendations) > 0


# ── LLM path ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_called_when_api_key_is_present():
    _seed_graph()

    fake_response = """### Architectural Observations
Auth service is a critical SPOF with 2 upstream callers.

### Recommendations
["Add circuit breaker to auth service", "Implement caching layer"]

### Risk Summary
System has moderate risk due to auth dependency concentration.
"""
    with patch("app.agents.planner.settings") as mock_settings, \
         patch("app.agents.planner.llm.analyze_dependencies",
               new_callable=AsyncMock, return_value=fake_response):

        mock_settings.gemini_api_key = "fake-key"
        result = await planner.run_analysis()

    assert "Auth service" in result.architectural_observations
    assert len(result.recommendations) == 2
    assert "moderate risk" in result.risk_summary


# ── Graceful LLM failure ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_falls_back_gracefully_when_llm_raises():
    _seed_graph()

    with patch("app.agents.planner.settings") as mock_settings, \
         patch("app.agents.planner.llm.analyze_dependencies",
               new_callable=AsyncMock, side_effect=Exception("API timeout")):

        mock_settings.gemini_api_key = "fake-key"
        result = await planner.run_analysis()

    # Must still return a valid result — not raise
    assert isinstance(result, AnalysisResult)
    assert len(result.architectural_observations) > 0
    assert len(result.recommendations) > 0
