from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_mcp_service
from backend.app.schemas.mcp import (
    MCPCallRequest,
    MCPCallResponse,
    MCPJsonRpcRequest,
    MCPJsonRpcResponse,
    MCPToolListResponse,
)
from backend.app.services.mcp_service import MCPService

router = APIRouter()


@router.get(
    "/tools",
    response_model=MCPToolListResponse,
    summary="List permitted restricted MCP tools",
    description="Returns the schemas of all restricted MCP tools exposed to AI specialists and clients.",
)
def list_mcp_tools(
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolListResponse:
    return mcp_service.list_tools()


@router.post(
    "/call",
    response_model=MCPCallResponse,
    summary="Invoke a restricted MCP tool",
    description="Executes a permitted MCP tool with strict path boundary confinement and input validation.",
)
def call_mcp_tool(
    payload: MCPCallRequest,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPCallResponse:
    return mcp_service.call_tool(payload.tool, payload.arguments)


@router.post(
    "/rpc",
    response_model=MCPJsonRpcResponse,
    summary="Standard MCP JSON-RPC 2.0 interface",
    description="Provides standard JSON-RPC 2.0 compliance for external MCP clients and runtimes.",
)
def mcp_jsonrpc_endpoint(
    payload: MCPJsonRpcRequest,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPJsonRpcResponse:
    return mcp_service.handle_jsonrpc(payload)

