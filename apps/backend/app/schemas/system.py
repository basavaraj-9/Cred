from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    version: str
    environment: str
    dependencies: dict[
        str, Literal["connected", "ready", "available", "disabled", "unavailable", "not_configured"]
    ]


class ApplicationInfo(BaseModel):
    name: str
    version: str
    environment: str


ComponentStatus = Literal[
    "ready",
    "connected",
    "unavailable",
    "not_configured",
    "not_implemented",
    "foundation_ready",
    "pipeline_validated",
    "experimental",
    "disabled",
    "not_recorded",
]


class StatusResponse(BaseModel):
    application: ApplicationInfo
    components: dict[str, ComponentStatus]
    development_stage: dict[str, str | int]
    core_models: dict[str, Literal["ready"]]
