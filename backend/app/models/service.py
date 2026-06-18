from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ServiceType(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"


class ServiceNode(BaseModel):
    name: str
    type: ServiceType
    language: str  # python, javascript, etc.
    port: Optional[int] = None
    endpoints: list[str] = []
    health_check: Optional[str] = None
    has_metrics: bool = False
    has_logging: bool = False
    description: Optional[str] = None


class DependencyEdge(BaseModel):
    source: str  # calling service
    target: str  # service being called
    protocol: str = "REST"
    endpoints_called: list[str] = []


class ServiceMetadata(BaseModel):
    services: list[ServiceNode]
    dependencies: list[DependencyEdge]
    source: str = "manual"  # docker-compose | openapi | manual
