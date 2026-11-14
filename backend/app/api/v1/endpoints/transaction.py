from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.api.deps import get_transaction_service
from backend.app.db.models.change_plan import ChangePlan
from backend.app.schemas.history import (
    BatchApprovalRequest,
    BatchExecuteApprovedRequest,
    BatchRejectRequest,
)
from backend.app.schemas.transaction import (
    ChangePlanApproveRequest,
    ChangePlanCreate,
    ChangePlanItemResponse,
    ChangePlanResponse,
    ExecutionJobResponse,
    OperationLogResponse,
    PlanValidationSummary,
    QuickCopyRequest,
    QuickDeleteRequest,
    QuickFolderCreateRequest,
    QuickMoveRequest,
    QuickRenameRequest,
    UndoExecutionResponse,
)
from backend.app.services.managed_folder import ManagedFolderException
from backend.app.services.transaction import (
    TransactionException,
    TransactionManagerService,
)

router = APIRouter()


def _serialize_plan(plan: ChangePlan) -> ChangePlanResponse:
    latest_job = plan.execution_jobs[-1] if plan.execution_jobs else None
    latest_job_resp: Optional[ExecutionJobResponse] = None
    if latest_job:
        completed = sum(1 for log in latest_job.operation_logs if log.status == "completed")
        failed = sum(1 for log in latest_job.operation_logs if log.status == "failed")
        latest_job_resp = ExecutionJobResponse(
            id=latest_job.id,
            change_plan_id=latest_job.change_plan_id,
            status=latest_job.status,
            started_at=latest_job.started_at,
            finished_at=latest_job.finished_at,
            error_message=latest_job.error_message,
            created_at=latest_job.created_at,
            operations_count=len(latest_job.operation_logs),
            completed_count=completed,
            failed_count=failed,
            operation_logs=[
                OperationLogResponse.model_validate(log) for log in latest_job.operation_logs
            ],
        )

    return ChangePlanResponse(
        id=plan.id,
        managed_folder_id=plan.managed_folder_id,
        analysis_run_id=plan.analysis_run_id,
        title=plan.title,
        plan_type=plan.plan_type,
        status=plan.status,
        created_by=plan.created_by,
        approved_at=plan.approved_at,
        approved_by=plan.approved_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        items=[ChangePlanItemResponse.model_validate(item) for item in plan.items],
        latest_execution_job=latest_job_resp,
    )


@router.post("/plans", response_model=ChangePlanResponse, status_code=status.HTTP_201_CREATED)
def create_change_plan(
    payload: ChangePlanCreate,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanResponse:
    """Creates a new structured Change Plan."""
    try:
        plan = service.create_plan(payload, created_by="user")
        return _serialize_plan(plan)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/plans", response_model=List[ChangePlanResponse])
def list_change_plans(
    folder_id: Optional[str] = Query(None, description="Filter by Managed Folder ID"),
    status: Optional[str] = Query(None, description="Filter by Plan status"),
    service: TransactionManagerService = Depends(get_transaction_service),
) -> List[ChangePlanResponse]:
    """Lists change plans, newest first."""
    plans = service.list_plans(folder_id=folder_id, status=status)
    return [_serialize_plan(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=ChangePlanResponse)
def get_change_plan(
    plan_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanResponse:
    """Retrieves full details of a specific Change Plan."""
    try:
        plan = service.get_plan(plan_id)
        return _serialize_plan(plan)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


class UpdatePlanItemRequest(BaseModel):
    new_destination_relative_path: str


@router.put("/plans/{plan_id}/items/{item_id}", response_model=ChangePlanItemResponse)
def update_plan_item(
    plan_id: str,
    item_id: str,
    payload: UpdatePlanItemRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanItemResponse:
    """Updates the destination path of a plan item in draft or pending review status."""
    try:
        item = service.update_plan_item(
            plan_id=plan_id,
            item_id=item_id,
            new_destination_relative_path=payload.new_destination_relative_path,
        )
        return ChangePlanItemResponse.model_validate(item)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/plans/{plan_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_item(
    plan_id: str,
    item_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> None:
    """Removes an item from a draft Change Plan."""
    try:
        service.delete_plan_item(plan_id=plan_id, item_id=item_id)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/{plan_id}/submit", response_model=ChangePlanResponse)
def submit_change_plan(
    plan_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanResponse:
    """Submits a draft Change Plan for user review and approval."""
    try:
        plan = service.submit_plan(plan_id)
        return _serialize_plan(plan)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/{plan_id}/validate", response_model=PlanValidationSummary)
def validate_change_plan(
    plan_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> PlanValidationSummary:
    """Validates plan items against live filesystem state, detecting conflicts or stale targets."""
    try:
        return service.validate_plan(plan_id)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/{plan_id}/approve", response_model=ChangePlanResponse)
def approve_change_plan(
    plan_id: str,
    payload: Optional[ChangePlanApproveRequest] = None,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanResponse:
    """Explicitly approves a Change Plan for execution."""
    approver = payload.approved_by if payload and payload.approved_by else "user"
    try:
        plan = service.approve_plan(plan_id, approved_by=approver)
        return _serialize_plan(plan)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/{plan_id}/reject", response_model=ChangePlanResponse)
def reject_change_plan(
    plan_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ChangePlanResponse:
    """Rejects a Change Plan."""
    try:
        plan = service.reject_plan(plan_id)
        return _serialize_plan(plan)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/{plan_id}/execute", response_model=ExecutionJobResponse)
def execute_change_plan(
    plan_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Executes an approved plan deterministically with best-effort rollback on failure."""
    try:
        job = service.execute_plan(plan_id)
        return service._build_execution_response(job)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/jobs/{job_id}", response_model=ExecutionJobResponse)
def get_execution_job(
    job_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Retrieves execution job progress and audit logs."""
    try:
        job = service.get_execution_job(job_id)
        return service._build_execution_response(job)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/jobs/{job_id}/undo", response_model=UndoExecutionResponse)
def undo_execution_job(
    job_id: str,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> UndoExecutionResponse:
    """Safely reverses a completed execution job in reverse order without overwriting modified files."""
    try:
        return service.undo_execution_job(job_id)
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/execute-approved", response_model=List[ExecutionJobResponse])
def execute_approved_plans(
    payload: Optional[BatchExecuteApprovedRequest] = None,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> List[ExecutionJobResponse]:
    """Executes all approved plans or a specified batch of approved plans."""
    try:
        plan_ids = payload.plan_ids if payload else None
        jobs = service.execute_approved_plans(plan_ids=plan_ids)
        return [service._build_execution_response(j) for j in jobs]
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/batch-approve", response_model=List[ChangePlanResponse])
def batch_approve_plans(
    payload: BatchApprovalRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> List[ChangePlanResponse]:
    """Approves multiple change plans in batch after verifying safety."""
    try:
        approver = payload.approved_by or "user"
        plans = service.batch_approve_plans(payload.plan_ids, approved_by=approver)
        return [_serialize_plan(p) for p in plans]
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/plans/batch-reject", response_model=List[ChangePlanResponse])
def batch_reject_plans(
    payload: BatchRejectRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> List[ChangePlanResponse]:
    """Rejects multiple change plans in batch."""
    try:
        plans = service.batch_reject_plans(payload.plan_ids, reason=payload.reason)
        return [_serialize_plan(p) for p in plans]
    except TransactionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# Quick actions
# -----------------------------------------------------------------------------


@router.post("/quick/create-folder", response_model=ExecutionJobResponse)
def quick_create_folder(
    payload: QuickFolderCreateRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Quickly creates a directory via an approved transaction."""
    try:
        return service.quick_create_directory(payload)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/quick/rename", response_model=ExecutionJobResponse)
def quick_rename(
    payload: QuickRenameRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Quickly renames a file or folder via an approved transaction."""
    try:
        return service.quick_rename(payload)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/quick/move", response_model=ExecutionJobResponse)
def quick_move(
    payload: QuickMoveRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Quickly moves files/folders via an approved transaction."""
    try:
        return service.quick_move(payload)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/quick/copy", response_model=ExecutionJobResponse)
def quick_copy(
    payload: QuickCopyRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Quickly copies files/folders via an approved transaction."""
    try:
        return service.quick_copy(payload)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/quick/delete", response_model=ExecutionJobResponse)
def quick_delete(
    payload: QuickDeleteRequest,
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionJobResponse:
    """Quickly deletes items to the Recycle Bin via an approved transaction."""
    try:
        return service.quick_delete(payload)
    except (TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
