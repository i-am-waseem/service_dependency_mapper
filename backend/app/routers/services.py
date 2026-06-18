import json
import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.models.service import ServiceMetadata, ServiceNode
from app.services import discovery, graph_service

router = APIRouter(prefix="/api/services", tags=["services"])
logger = structlog.get_logger(__name__)


@router.post("/load", summary="Load service metadata from JSON payload")
async def load_services(metadata: ServiceMetadata):
    try:
        graph_service.load_graph(metadata)
        return {"loaded": True, "services": len(metadata.services), "dependencies": len(metadata.dependencies)}
    except Exception as exc:
        logger.error("load_services_failed", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/load/sample", summary="Load built-in sample data (5-service ecosystem)")
async def load_sample():
    try:
        metadata = discovery.load_sample_data()
        graph_service.load_graph(metadata)
        return {
            "loaded": True,
            "source": metadata.source,
            "services": len(metadata.services),
            "dependencies": len(metadata.dependencies),
        }
    except Exception as exc:
        logger.error("load_sample_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/load/docker-compose", summary="Upload a docker-compose.yml file")
async def load_docker_compose(file: UploadFile = File(...)):
    import tempfile, os
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        metadata = discovery.load_from_docker_compose(tmp_path)
        graph_service.load_graph(metadata)
        os.unlink(tmp_path)
        return {"loaded": True, "services": len(metadata.services), "dependencies": len(metadata.dependencies)}
    except Exception as exc:
        logger.error("load_docker_compose_failed", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", summary="List all discovered services")
async def list_services() -> list[ServiceNode]:
    if not graph_service.is_loaded():
        return []
    graph = graph_service.get_graph()
    # Return enriched service data from the graph nodes
    return [
        ServiceNode(
            name=n.id,
            type=n.type,  # type: ignore[arg-type]
            language=n.language,
            health_check=n.health_check,
            has_metrics=n.has_metrics,
            has_logging=n.has_logging,
        )
        for n in graph.nodes
    ]


@router.get("/{service_name}", summary="Get a single service by name")
async def get_service(service_name: str):
    if service_name not in graph_service.get_all_service_names():
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    return graph_service.get_service_relationships(service_name)
