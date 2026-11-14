from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.dashboard import (
    DashboardAnalyzeRequest,
    DashboardJobItem,
    DashboardOverviewResponse,
)
from backend.app.services.dashboard import DashboardService

router = APIRouter()


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    """Returns aggregated summary metrics, storage distribution, activities, and background jobs from local database."""
    try:
        return service.get_overview()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memuat ringkasan dashboard: {str(e)}",
        )


@router.post("/analyze", response_model=DashboardJobItem)
def trigger_dashboard_analysis(
    payload: DashboardAnalyzeRequest,
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardJobItem:
    """Executes a metadata or deep storage analysis job across one or all managed folders."""
    try:
        return service.trigger_analysis(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal memulai analisis: {str(e)}",
        )
