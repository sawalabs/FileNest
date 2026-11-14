from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.settings import (
    AISettings,
    AISettingsUpdate,
    AllSettingsResponse,
    ApplyUpdateRequest,
    ApplyUpdateResponse,
    AppUpdateStatusResponse,
    AvailableModelsResponse,
    GeneralSettings,
    MaintenanceActionResult,
    MonitoringGlobalSettings,
    OrganizationSettings,
    SecuritySettings,
    StorageSettings,
    TestConnectionRequest,
    TestConnectionResponse,
)
from backend.app.services.settings_service import SettingsException, SettingsService

router = APIRouter()


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(db)


@router.get("", response_model=AllSettingsResponse, summary="Get all application settings grouped by category")
def get_all_settings(service: SettingsService = Depends(get_settings_service)) -> AllSettingsResponse:
    return service.get_all_settings()


@router.get("/update/status", response_model=AppUpdateStatusResponse, summary="Check local installer & update status")
def get_update_status(service: SettingsService = Depends(get_settings_service)) -> AppUpdateStatusResponse:
    return service.check_update_status()


@router.post("/update/apply", response_model=ApplyUpdateResponse, summary="Launch NSIS or MSI installer for update/reinstall")
def apply_installer_update(
    payload: ApplyUpdateRequest = ApplyUpdateRequest(),
    service: SettingsService = Depends(get_settings_service),
) -> ApplyUpdateResponse:
    try:
        return service.apply_installer_update(installer_path=payload.installer_path)
    except SettingsException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{category}", summary="Get settings for a specific category")
def get_category_settings(category: str, service: SettingsService = Depends(get_settings_service)) -> Any:
    category_lower = category.lower()
    if category_lower == "general":
        return service.get_general_settings()
    elif category_lower == "ai":
        return service.get_ai_settings()
    elif category_lower == "organization":
        return service.get_organization_settings()
    elif category_lower == "monitoring":
        return service.get_monitoring_settings()
    elif category_lower == "security":
        return service.get_security_settings()
    elif category_lower == "storage":
        return service.get_storage_settings()
    elif category_lower == "about":
        return service.get_about_settings()
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown settings category '{category}'",
        )


@router.patch("/{category}", summary="Update settings for a specific category")
@router.put("/{category}", summary="Update settings for a specific category")
def update_category_settings(
    category: str,
    payload: Dict[str, Any],
    service: SettingsService = Depends(get_settings_service),
) -> Any:
    category_lower = category.lower()
    try:
        if category_lower == "general":
            return service.update_general_settings(payload)
        elif category_lower == "ai":
            update_model = AISettingsUpdate(**payload)
            return service.update_ai_settings(update_model)
        elif category_lower == "organization":
            return service.update_organization_settings(payload)
        elif category_lower == "monitoring":
            return service.update_monitoring_settings(payload)
        elif category_lower == "security":
            return service.update_security_settings(payload)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Direct update of category '{category}' is not supported.",
            )
    except SettingsException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/reset", summary="Reset a settings category to default values")
def reset_category_settings(
    category: str = Query(..., description="Category to reset: general, ai, organization, monitoring, security"),
    service: SettingsService = Depends(get_settings_service),
) -> Dict[str, Any]:
    try:
        return service.reset_category(category.lower())
    except SettingsException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==========================================
# AI Connection Testing & Models
# ==========================================
@router.post("/ai/hermes/test", response_model=TestConnectionResponse, summary="Test Hermes connection")
async def test_hermes_connection(
    payload: TestConnectionRequest = TestConnectionRequest(),
    service: SettingsService = Depends(get_settings_service),
) -> TestConnectionResponse:
    return await service.test_hermes_connection(
        endpoint=payload.endpoint,
        timeout=payload.timeout_seconds or 5,
    )


@router.post("/ai/9router/test", response_model=TestConnectionResponse, summary="Test 9Router connection")
async def test_9router_connection(
    payload: TestConnectionRequest = TestConnectionRequest(),
    service: SettingsService = Depends(get_settings_service),
) -> TestConnectionResponse:
    return await service.test_9router_connection(
        endpoint=payload.endpoint,
        api_key=payload.api_key,
        timeout=payload.timeout_seconds or 10,
    )


@router.post("/ai/openrouter/test", response_model=TestConnectionResponse, summary="Test OpenRouter connection")
async def test_openrouter_connection(
    payload: TestConnectionRequest = TestConnectionRequest(),
    service: SettingsService = Depends(get_settings_service),
) -> TestConnectionResponse:
    return await service.test_openrouter_connection(
        endpoint=payload.endpoint,
        api_key=payload.api_key,
        timeout=payload.timeout_seconds or 15,
    )


@router.get("/ai/models", response_model=AvailableModelsResponse, summary="Get configured models available via 9Router")
async def get_available_models(service: SettingsService = Depends(get_settings_service)) -> AvailableModelsResponse:
    return await service.get_available_models()


# ==========================================
# Storage & Database Maintenance
# ==========================================
@router.get("/storage", response_model=StorageSettings, summary="Get application storage usage and database metrics")
def get_storage_metrics(service: SettingsService = Depends(get_settings_service)) -> StorageSettings:
    return service.get_storage_settings()


@router.post("/database/integrity-check", response_model=MaintenanceActionResult, summary="Run SQLite integrity check")
def run_database_integrity_check(service: SettingsService = Depends(get_settings_service)) -> MaintenanceActionResult:
    return service.check_database_integrity()


@router.post("/database/compact", response_model=MaintenanceActionResult, summary="Compact and vacuum SQLite database")
def compact_database(service: SettingsService = Depends(get_settings_service)) -> MaintenanceActionResult:
    return service.compact_database()


@router.post("/cache/clear", response_model=MaintenanceActionResult, summary="Clear application cache")
def clear_application_cache(
    cache_types: Optional[List[str]] = None,
    service: SettingsService = Depends(get_settings_service),
) -> MaintenanceActionResult:
    return service.clear_cache(cache_types)

