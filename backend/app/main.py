import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import services, graph, insights, analysis

# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    ),
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.app_name, version=settings.app_version)
    yield
    logger.info("shutdown")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Service Dependency Mapping System",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(services.router)
app.include_router(graph.router)
app.include_router(insights.router)
app.include_router(analysis.router)


# ---------------------------------------------------------------------------
# Health + global error handling
# ---------------------------------------------------------------------------
@app.get("/health", tags=["observability"])
async def health():
    from app.services import graph_service
    g = graph_service.get_graph() if graph_service.is_loaded() else None
    return {
        "status": "ok",
        "version": settings.app_version,
        "graph_loaded": graph_service.is_loaded(),
        "service_count": g.service_count if g else 0,
    }


@app.get("/api/metrics", tags=["observability"])
async def metrics():
    """
    Lightweight operational metrics for this service.
    Exposes graph stats and analysis job counters.
    Ironic to check other services for missing metrics — we should have our own.
    """
    from app.services import graph_service
    from app.routers.analysis import _jobs

    g = graph_service.get_graph() if graph_service.is_loaded() else None

    risk_distribution: dict[str, int] = {}
    if g:
        for node in g.nodes:
            level = node.risk_level
            risk_distribution[level] = risk_distribution.get(level, 0) + 1

    job_counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for job in _jobs.values():
        job_counts[job.status] += 1

    return {
        "graph": {
            "loaded": graph_service.is_loaded(),
            "service_count": g.service_count if g else 0,
            "edge_count": g.edge_count if g else 0,
            "risk_distribution": risk_distribution,
        },
        "analysis_jobs": job_counts,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://tools.ietf.org/html/rfc7807",
            "title": "Internal Server Error",
            "detail": str(exc),
        },
    )
