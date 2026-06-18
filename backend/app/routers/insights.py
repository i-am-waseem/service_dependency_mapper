import structlog
from fastapi import APIRouter, HTTPException

from app.services import graph_service

router = APIRouter(prefix="/api/insights", tags=["insights"])
logger = structlog.get_logger(__name__)


@router.get("/{service_name}", summary="Get upstream/downstream relationships for a service")
async def get_service_insights(service_name: str):
    if not graph_service.is_loaded():
        raise HTTPException(status_code=404, detail="No graph loaded.")
    if service_name not in graph_service.get_all_service_names():
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found.")
    return graph_service.get_service_relationships(service_name)
