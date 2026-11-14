from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RouterModelItem(BaseModel):
    id: str
    name: str
    context_length: int = 128000
    provider: str = "9Router"
    supports_vision: bool = False
    is_default: bool = False


class RouterModelListResponse(BaseModel):
    models: List[RouterModelItem] = []
    source: str = "remote"  # "remote" or "fallback"
    total_count: int = 0


class RouterChatMessage(BaseModel):
    role: str = Field(description="'system', 'user', or 'assistant'")
    content: str


class RouterChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[RouterChatMessage] = Field(min_length=1)
    temperature: Optional[float] = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4096, ge=1)
    json_mode: bool = False
    timeout_seconds: Optional[int] = None


class RouterTokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class RouterChatResponse(BaseModel):
    id: str
    model: str
    content: str
    finish_reason: str = "stop"
    usage: RouterTokenUsage
    latency_ms: float = 0.0
    parsed_json: Optional[Dict[str, Any]] = None
    provider_used: str = "9Router"
    fallback_triggered: bool = False

    model_config = ConfigDict(from_attributes=True)


class RouterHealthResponse(BaseModel):
    status: str  # "connected", "disconnected", "unauthorized", "error", "not_configured"
    endpoint: str
    latency_ms: Optional[float] = None
    message: str
    authenticated: bool = False
    models_count: int = 0
    fallback_status: Optional[str] = None  # "connected", "not_configured", "error"
    fallback_provider: str = "OpenRouter"

