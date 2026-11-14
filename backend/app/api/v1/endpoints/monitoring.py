from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_monitoring_service
from backend.app.schemas.monitoring import (
    ActivityChartResponse,
    DistributionResponse,
    MonitoringConfigResponse,
    MonitoringConfigUpdate,
    MonitoringEventListResponse,
    MonitoringSummaryStats,
    WatcherItemResponse,
)
from backend.app.services.monitoring import (
    MonitoringException,
    MonitoringManagerService,
)

router = APIRouter()


@router.get("/status")
def get_service_status(
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Returns the live status of the filesystem monitoring subsystem."""
    active_count = sum(1 for w in service._watchers.values() if w.get("status") == "watching")
    return {
        "status": "running" if active_count > 0 else "idle",
        "active_watchers": active_count,
        "total_monitored": len(service._watchers),
    }


@router.get("/watchers", response_model=List[WatcherItemResponse])
def list_watchers(
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> List[WatcherItemResponse]:
    """Lists all monitored folder watchers with current observer states and 24h event counts."""
    return service.get_watchers_list(db=db)


@router.post("/watchers/{folder_id}/start", response_model=Dict[str, Any])
def start_watcher(
    folder_id: str,
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Starts or enables the filesystem observer for a specific registered Managed Folder."""
    try:
        service.start_watcher(folder_id, persist=True, db=db)
        return {"status": "watching", "folder_id": folder_id, "message": "Watcher started successfully"}
    except MonitoringException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/watchers/{folder_id}/stop", response_model=Dict[str, Any])
def stop_watcher(
    folder_id: str,
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Stops the filesystem observer for a specific Managed Folder."""
    try:
        service.stop_watcher(folder_id, persist=True, db=db)
        return {"status": "stopped", "folder_id": folder_id, "message": "Watcher stopped"}
    except MonitoringException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/watchers/{folder_id}/pause", response_model=Dict[str, Any])
def pause_watcher(
    folder_id: str,
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Temporarily pauses event collection for a monitored folder."""
    try:
        service.pause_watcher(folder_id, db=db)
        return {"status": "paused", "folder_id": folder_id}
    except MonitoringException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/watchers/{folder_id}/resume", response_model=Dict[str, Any])
def resume_watcher(
    folder_id: str,
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> Dict[str, Any]:
    """Resumes event collection for a paused folder watcher."""
    try:
        service.resume_watcher(folder_id, db=db)
        return {"status": "watching", "folder_id": folder_id}
    except MonitoringException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/watchers/{folder_id}/config", response_model=MonitoringConfigResponse)
def update_watcher_config(
    folder_id: str,
    payload: MonitoringConfigUpdate,
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> MonitoringConfigResponse:
    """Updates watcher parameters (debounce_ms, recursive, ignore_patterns)."""
    try:
        return service.update_config(folder_id, payload, db=db)
    except MonitoringException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/events", response_model=MonitoringEventListResponse)
def get_monitoring_events(
    folder_id: Optional[str] = Query(None, description="Filter by Managed Folder ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type: created, modified, deleted, moved"),
    time_range: Optional[str] = Query(None, description="Time range: last_hour, last_24h, last_7d, last_30d"),
    search: Optional[str] = Query(None, description="Search relative path"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> MonitoringEventListResponse:
    """Retrieves chronological filesystem events with filtering and search."""
    events, total = service.get_events(
        folder_id=folder_id,
        event_type=event_type,
        time_range=time_range,
        search=search,
        limit=limit,
        offset=offset,
        db=db,
    )
    return MonitoringEventListResponse(total=total, items=events)


@router.get("/stats", response_model=MonitoringSummaryStats)
def get_monitoring_stats(
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> MonitoringSummaryStats:
    """Returns summary statistics for the monitoring cards."""
    return service.get_summary_stats(db=db)


@router.get("/activity-chart", response_model=ActivityChartResponse)
def get_activity_chart(
    time_range: str = Query("last_24h", pattern="^(last_hour|last_24h|last_7d|last_30d)$"),
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> ActivityChartResponse:
    """Returns time-bucketed event counts for the stacked bar chart."""
    return service.get_activity_chart(time_range=time_range, db=db)


@router.get("/distribution", response_model=DistributionResponse)
def get_event_distribution(
    db: Session = Depends(get_db),
    service: MonitoringManagerService = Depends(get_monitoring_service),
) -> DistributionResponse:
    """Returns event type breakdown and percentages for the donut chart."""
    return service.get_distribution(db=db)
