"""
Integration test for the full analysis flow via the HTTP API.

Covers the complete job lifecycle:
  POST /api/services/load/sample  →  seeds the graph
  POST /api/analysis/run          →  queues a background job
  GET  /api/analysis/{job_id}     →  polls until completed

Uses FastAPI's TestClient which runs BackgroundTasks synchronously,
so no real polling loop is needed — the job completes before the
POST response returns.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)

FAKE_LLM_RESPONSE = """### Architectural Observations
The system exhibits a hub-and-spoke pattern with auth-service as a critical bottleneck.

### Recommendations
["Add circuit breakers around auth-service", "Introduce caching for auth tokens"]

### Risk Summary
High risk due to auth-service being a single point of failure for all backend services.
"""


def test_full_analysis_job_lifecycle():
    # Step 1: load sample data
    res = client.post("/api/services/load/sample")
    assert res.status_code == 200
    assert res.json()["loaded"] is True
    assert res.json()["services"] == 5

    # Step 2: trigger analysis — mock LLM so test doesn't hit real API
    with patch("app.agents.planner.llm.analyze_dependencies",
               new_callable=AsyncMock, return_value=FAKE_LLM_RESPONSE), \
         patch("app.agents.planner.settings") as mock_settings:

        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model   = "gemini-flash-latest"

        res = client.post("/api/analysis/run")
        assert res.status_code == 200
        job_id = res.json()["job_id"]
        assert job_id  # non-empty string

    # Step 3: poll — TestClient runs BackgroundTasks synchronously so it's
    # already done by the time we get here
    res = client.get(f"/api/analysis/{job_id}")
    assert res.status_code == 200

    job = res.json()
    assert job["status"] == "completed"
    assert job["result"] is not None

    result = job["result"]
    # Rule-based findings — auth-service has in_degree=4, must be a SPOF
    spof_names = [f["service"] for f in result["single_points_of_failure"]]
    assert "auth-service" in spof_names

    # LLM synthesis was injected
    assert "hub-and-spoke" in result["architectural_observations"]
    assert len(result["recommendations"]) == 2


def test_polling_unknown_job_returns_404():
    res = client.get("/api/analysis/does-not-exist")
    assert res.status_code == 404


def test_graph_endpoint_returns_correct_shape_after_load():
    client.post("/api/services/load/sample")
    res = client.get("/api/graph")
    assert res.status_code == 200
    graph = res.json()
    assert graph["service_count"] == 5
    assert graph["edge_count"] == 8
    node_ids = [n["id"] for n in graph["nodes"]]
    assert "auth-service" in node_ids
