from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_router_gateway_service
from backend.app.schemas.router_gateway import (
    RouterChatRequest,
    RouterChatResponse,
    RouterHealthResponse,
    RouterModelListResponse,
)
from backend.app.services.router_gateway import RouterGatewayException, RouterGatewayService

router = APIRouter()


@router.get("/health", response_model=RouterHealthResponse, summary="Check 9Router gateway connectivity")
async def get_router_health(
    endpoint: Optional[str] = Query(None, description="Optional custom 9Router endpoint to probe"),
    timeout: Optional[int] = Query(15, description="Probe timeout in seconds"),
    service: RouterGatewayService = Depends(get_router_gateway_service),
) -> RouterHealthResponse:
    """Verifies connection health, models count, and latency of the configured 9Router gateway."""
    return await service.check_health(endpoint_override=endpoint, timeout=timeout or 15)


@router.get("/models", response_model=RouterModelListResponse, summary="Discover models from 9Router")
async def get_available_models(
    endpoint: Optional[str] = Query(None, description="Optional custom 9Router endpoint"),
    service: RouterGatewayService = Depends(get_router_gateway_service),
) -> RouterModelListResponse:
    """Returns models discovered dynamically from 9Router or fallback supported models."""
    return await service.discover_models(endpoint_override=endpoint)


@router.post("/chat", response_model=RouterChatResponse, summary="Execute chat completion via 9Router")
async def create_chat_completion(
    payload: RouterChatRequest,
    service: RouterGatewayService = Depends(get_router_gateway_service),
) -> RouterChatResponse:
    """Sends an OpenAI-compatible completion request through 9Router with latency tracking and JSON mode support."""
    try:
        return await service.chat_completion(payload)
    except RouterGatewayException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"9Router request failed: {str(e)}",
        )
