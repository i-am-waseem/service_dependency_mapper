"""
Parses service metadata from multiple sources:
  - Docker Compose YAML (depends_on + env var URL references)
  - OpenAPI YAML with x-service-metadata extension
  - Raw JSON payload
"""
import re
import yaml
import json
import structlog
from pathlib import Path
from typing import Any, Union

from app.models.service import ServiceMetadata, ServiceNode, DependencyEdge, ServiceType

logger = structlog.get_logger(__name__)

_URL_PATTERN = re.compile(r"https?://([a-z0-9_-]+):\d+", re.IGNORECASE)


def load_from_docker_compose(path: Union[str, Path]) -> ServiceMetadata:
    path = Path(path)
    with open(path) as f:
        compose = yaml.safe_load(f)

    raw_services: dict[str, Any] = compose.get("services", {})
    nodes: list[ServiceNode] = []
    edges: list[DependencyEdge] = []

    for name, cfg in raw_services.items():
        lang = _infer_language(name, cfg)
        svc_type = ServiceType.FRONTEND if name == "frontend" else ServiceType.BACKEND
        health = None
        hc = cfg.get("healthcheck", {})
        if isinstance(hc, dict) and hc.get("test"):
            health = "/health"

        ports = cfg.get("ports", [])
        port = None
        if ports:
            raw = str(ports[0]).split(":")[-1]
            port = int(raw) if raw.isdigit() else None

        nodes.append(ServiceNode(
            name=name,
            type=svc_type,
            language=lang,
            port=port,
            health_check=health,
        ))

    # Build edges from depends_on declarations
    for name, cfg in raw_services.items():
        for dep in cfg.get("depends_on", []):
            edges.append(DependencyEdge(source=name, target=dep))

        # Also mine env vars for service URL references
        for env_val in (cfg.get("environment") or []):
            if isinstance(env_val, str) and "=" in env_val:
                val = env_val.split("=", 1)[1]
            else:
                val = str(env_val)
            for target_name in _URL_PATTERN.findall(val):
                if target_name in raw_services and target_name != name:
                    edge = DependencyEdge(source=name, target=target_name)
                    if edge not in edges:
                        edges.append(edge)

    logger.info("docker_compose_parsed", services=len(nodes), edges=len(edges))
    return ServiceMetadata(services=nodes, dependencies=edges, source="docker-compose")


def load_from_openapi_dir(directory: Union[str, Path]) -> ServiceMetadata:
    directory = Path(directory)
    all_nodes: dict[str, ServiceNode] = {}
    all_edges: list[DependencyEdge] = []

    for spec_path in directory.glob("*.yaml"):
        with open(spec_path) as f:
            spec = yaml.safe_load(f)

        service_name = spec_path.stem  # filename without extension
        meta = spec.get("x-service-metadata", {})
        lang = meta.get("language", "unknown")
        svc_type = ServiceType.FRONTEND if service_name == "frontend" else ServiceType.BACKEND

        # Collect endpoint paths
        paths = list(spec.get("paths", {}).keys())

        all_nodes[service_name] = ServiceNode(
            name=service_name,
            type=svc_type,
            language=lang,
            endpoints=paths,
            health_check="/health" if "/health" in paths else None,
            has_metrics=meta.get("has_metrics", False),
            has_logging=meta.get("has_logging", False),
        )

        for dep in meta.get("dependencies", []):
            all_edges.append(DependencyEdge(
                source=service_name,
                target=dep["target"],
                protocol=dep.get("protocol", "REST"),
                endpoints_called=dep.get("endpoints_called", []),
            ))

    logger.info("openapi_dir_parsed", services=len(all_nodes), edges=len(all_edges))
    return ServiceMetadata(
        services=list(all_nodes.values()),
        dependencies=all_edges,
        source="openapi",
    )


def load_from_json(payload: dict) -> ServiceMetadata:
    metadata = ServiceMetadata(**payload)
    logger.info("json_payload_parsed",
                services=len(metadata.services),
                edges=len(metadata.dependencies))
    return metadata


def load_sample_data() -> ServiceMetadata:
    """Merge Docker Compose topology with OpenAPI observability metadata."""
    base_dir = Path(__file__).parent.parent.parent / "sample_data"
    compose_meta = load_from_docker_compose(base_dir / "docker-compose.yml")
    openapi_meta = load_from_openapi_dir(base_dir / "openapi")

    # OpenAPI specs are richer — use them as primary, fill gaps from compose
    openapi_by_name = {s.name: s for s in openapi_meta.services}
    for node in compose_meta.services:
        if node.name not in openapi_by_name:
            openapi_by_name[node.name] = node
        else:
            # Backfill port and health_check from compose
            existing = openapi_by_name[node.name]
            openapi_by_name[node.name] = existing.model_copy(update={
                "port": node.port or existing.port,
                "health_check": existing.health_check or node.health_check,
            })

    # Merge edges (prefer openapi for endpoint detail, add compose-only edges)
    openapi_edge_pairs = {(e.source, e.target) for e in openapi_meta.dependencies}
    merged_edges = list(openapi_meta.dependencies)
    for edge in compose_meta.dependencies:
        if (edge.source, edge.target) not in openapi_edge_pairs:
            merged_edges.append(edge)

    # Add frontend edges (not in OpenAPI specs since frontend has no spec here)
    frontend_node = openapi_by_name.get("frontend")
    if frontend_node is None:
        frontend_compose = next(
            (s for s in compose_meta.services if s.name == "frontend"), None
        )
        if frontend_compose:
            openapi_by_name["frontend"] = frontend_compose

    return ServiceMetadata(
        services=list(openapi_by_name.values()),
        dependencies=merged_edges,
        source="docker-compose+openapi",
    )


def _infer_language(name: str, cfg: dict) -> str:
    if name == "frontend":
        return "javascript"
    image = cfg.get("image", "")
    if "node" in image or "react" in image:
        return "javascript"
    return "python"
