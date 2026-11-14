from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_system_service
from backend.app.schemas.health import HealthResponse
from backend.app.services.system import SystemService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check(
    service: SystemService = Depends(get_system_service),
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Returns the operational status, version, and environment of the backend."""
    return service.get_health_status(db=db)
