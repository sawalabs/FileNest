from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    status: str = Field(default="ok", description="Component status: ok, warning, error, or not_configured")
    message: str = Field(default="", description="Descriptive status message or diagnostic hint")
    latency_ms: Optional[float] = Field(default=None, description="Probe latency in milliseconds if applicable")
    details: Dict[str, Any] = Field(default_factory=dict, description="Component-specific telemetry details")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Application service status")
    project: str = Field(description="Application project name")
    version: str = Field(description="Application version string")
    environment: str = Field(description="Runtime environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server UTC timestamp in ISO-8601",
    )
    subsystems: Dict[str, ComponentHealth] = Field(
        default_factory=dict,
        description="Health and diagnostic status per subsystem (database, filesystem, security, ai_gateway, monitoring)",
    )
