# Backend

FastAPI service that discovers service dependencies, builds a graph, and runs AI-assisted analysis.

## Project Structure

```
backend/
├── app/
│   ├── main.py              # App entrypoint — FastAPI instance, middleware, routers, health
│   ├── config.py            # All settings via pydantic-settings (env vars, no hardcoded values)
│   ├── routers/
│   │   ├── services.py      # POST /api/services/load — ingest config, seed graph
│   │   ├── graph.py         # GET /api/graph — nodes + edges JSON; GET /api/graph/mermaid
│   │   ├── insights.py      # GET /api/insights/{service} — upstream/downstream relationships
│   │   └── analysis.py      # POST /api/analysis/run + GET /api/analysis/{job_id} — async AI job
│   ├── agents/
│   │   ├── planner.py       # Orchestrates analysis: executor → planner gate → LLM synthesizer
│   │   └── tools.py         # Four deterministic rule tools (SPOF, coupling, risk, observability)
│   ├── models/
│   │   ├── service.py       # Input models: ServiceNode, DependencyEdge, ServiceMetadata
│   │   └── graph.py         # Output models: GraphNode, GraphEdge, AnalysisResult, AnalysisJob
│   ├── services/
│   │   ├── discovery.py     # Parses Docker Compose, OpenAPI YAML, and raw JSON into ServiceMetadata
│   │   ├── graph_service.py # NetworkX graph — algorithms live here, not in routers or agents
│   │   └── llm.py           # Gemini client wrapper — asyncio.to_thread wraps the blocking SDK
│   └── middleware/
│       └── logging.py       # Binds full UUID request_id to structlog context per request
├── tests/
│   ├── conftest.py          # autouse fixture: resets graph + job store between every test
│   ├── test_graph_service.py
│   ├── test_planner.py
│   └── test_analysis_router.py
├── sample_data/
│   ├── docker-compose.yml   # 5-service mock ecosystem (topology + ports)
│   └── openapi/             # Per-service OpenAPI specs with x-service-metadata extension
├── .env.example             # All supported env vars with descriptions
├── requirements.txt         # Runtime dependencies only
└── requirements-dev.txt     # Adds pytest + pytest-asyncio on top of requirements.txt
```

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env    # set GEMINI_API_KEY if you want LLM synthesis

uvicorn app.main:app --reload
```

API available at `http://localhost:8000`
Swagger UI at `http://localhost:8000/docs`

## Running Tests

```bash
pytest tests/ -v
```

```
tests/test_graph_service.py    — 6 pure logic tests (no mocks, no network)
tests/test_planner.py          — 3 async tests (AsyncMock patches Gemini)
tests/test_analysis_router.py  — 3 integration tests (TestClient, full HTTP stack)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | `""` | Gemini API key. LLM synthesis is skipped if empty — rule findings still returned |
| `GEMINI_MODEL` | `gemini-flash-latest` | Gemini model name |
| `GEMINI_MAX_TOKENS` | `4096` | Max tokens for LLM response |
| `GEMINI_MAX_RETRIES` | `3` | Retry count on transient Gemini errors |
| `LOG_LEVEL` | `INFO` | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SPOF_IN_DEGREE_THRESHOLD` | `2` | Services with at least this many dependents are flagged as SPOFs |
| `GRAPH_PERSISTENCE_PATH` | *(disabled)* | If set, graph is persisted to this JSON file path across restarts |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed origins for CORS |

## Key Design Decisions

**Two separate risk mechanisms:**
- `risk_level` on `GraphNode` — drives node colour in the UI, based purely on `in_degree`
- `risk_score` in `score_dependency_risk()` — drives agent findings, uses `fan-in × fan-out + observability penalty`

**Why `tools.run_all()` is synchronous:**
All four tools call NetworkX in-memory graph math — CPU-bound operations completing in < 1ms. Making them `async def` without any `await` would be misleading. `asyncio.to_thread` is reserved for the Gemini SDK call, which is a real blocking network call.

**Why `asyncio.to_thread` instead of `generate_content_async`:**
`generate_content_async()` hangs indefinitely on Python 3.9 + `google-generativeai==0.8.x`. `asyncio.to_thread` offloads the blocking sync call to a thread pool, which works correctly across all Python versions.
