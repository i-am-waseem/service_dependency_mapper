import structlog
from fastapi import APIRouter, HTTPException

from app.models.graph import DependencyGraph
from app.services import graph_service

router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=DependencyGraph, summary="Get dependency graph (nodes + edges)")
async def get_graph():
    if not graph_service.is_loaded():
        raise HTTPException(status_code=404, detail="No graph loaded. POST /api/services/load first.")
    return graph_service.get_graph()
