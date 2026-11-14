from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    health,
    folders,
    filesystem,
    transaction,
    storage,
    organization,
    smart_rename,
    history,
    monitoring,
    settings,
    dashboard,
    router_gateway,
    mcp,
    specialists,
    rules,
    assistant,
    ocr,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Session"])
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard Overview"])
api_v1_router.include_router(assistant.router, prefix="/assistant", tags=["Contextual AI Assistant"])
api_v1_router.include_router(ocr.router, prefix="/ocr", tags=["PaddleOCR Text Extraction"])
api_v1_router.include_router(router_gateway.router, prefix="/router", tags=["9Router Gateway"])
api_v1_router.include_router(mcp.router, prefix="/mcp", tags=["Restricted MCP Tools"])
api_v1_router.include_router(specialists.router, prefix="/specialists", tags=["AI Analysis Specialists"])
api_v1_router.include_router(rules.router, prefix="/rules", tags=["Approved Rules Automation"])
api_v1_router.include_router(folders.router, prefix="/folders", tags=["Managed Folders"])
api_v1_router.include_router(filesystem.router, prefix="/fs", tags=["Filesystem Services"])
api_v1_router.include_router(transaction.router, prefix="/transactions", tags=["Transaction Manager"])
api_v1_router.include_router(storage.router, prefix="/storage", tags=["Storage Analyzer"])
api_v1_router.include_router(organization.router, prefix="/organization", tags=["Organization Plans"])
api_v1_router.include_router(smart_rename.router, prefix="/smart-rename", tags=["Smart Rename Plans"])
api_v1_router.include_router(history.router, prefix="/history", tags=["History & Audit Logs"])
api_v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["Filesystem Monitoring"])
api_v1_router.include_router(settings.router, prefix="/settings", tags=["Application Settings"])

