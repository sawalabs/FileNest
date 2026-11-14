from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_rules_service
from backend.app.schemas.rules import (
    OrganizationRuleApproveRequest,
    OrganizationRuleCreate,
    OrganizationRuleResponse,
    OrganizationRuleUpdate,
    RuleEvaluateFileRequest,
    RuleEvaluationResult,
    RuleExecutionResponse,
)
from backend.app.services.rules_automation import (
    RulesAutomationException,
    RulesAutomationService,
)

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization or rename rule",
    description="Registers a new rule. Starts at version 1 and unapproved status.",
)
def create_rule(
    payload: OrganizationRuleCreate,
    service: RulesAutomationService = Depends(get_rules_service),
) -> OrganizationRuleResponse:
    try:
        rule = service.create_rule(payload)
        return service.to_rule_response(rule)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    response_model=List[OrganizationRuleResponse],
    summary="List organization rules",
    description="Returns rules, optionally filtered by managed_folder_id.",
)
def list_rules(
    folder_id: Optional[str] = Query(default=None),
    service: RulesAutomationService = Depends(get_rules_service),
) -> List[OrganizationRuleResponse]:
    rules = service.list_rules(folder_id)
    return [service.to_rule_response(r) for r in rules]


@router.get(
    "/executions",
    response_model=List[RuleExecutionResponse],
    summary="List rule execution history",
    description="Returns execution logs for approved rules, including automatic executions and review diversions.",
)
def list_rule_executions(
    rule_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: RulesAutomationService = Depends(get_rules_service),
) -> List[RuleExecutionResponse]:
    executions = service.list_executions(rule_id, limit)
    return [service.to_execution_response(e) for e in executions]


@router.get(
    "/{rule_id}",
    response_model=OrganizationRuleResponse,
    summary="Get rule details",
)
def get_rule(
    rule_id: str,
    service: RulesAutomationService = Depends(get_rules_service),
) -> OrganizationRuleResponse:
    try:
        rule = service.get_rule(rule_id)
        return service.to_rule_response(rule)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{rule_id}",
    response_model=OrganizationRuleResponse,
    summary="Update rule scope or actions",
    description="Material changes to scope, conditions, or actions increment version and revoke approval.",
)
def update_rule(
    rule_id: str,
    payload: OrganizationRuleUpdate,
    service: RulesAutomationService = Depends(get_rules_service),
) -> OrganizationRuleResponse:
    try:
        rule = service.update_rule(rule_id, payload)
        return service.to_rule_response(rule)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{rule_id}/approve",
    response_model=OrganizationRuleResponse,
    summary="Approve rule for automatic execution",
    description="Approves a rule for its current version and exact scope definition.",
)
def approve_rule(
    rule_id: str,
    payload: OrganizationRuleApproveRequest = OrganizationRuleApproveRequest(),
    service: RulesAutomationService = Depends(get_rules_service),
) -> OrganizationRuleResponse:
    try:
        rule = service.approve_rule(rule_id, payload.approved_by)
        return service.to_rule_response(rule)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{rule_id}/toggle",
    response_model=OrganizationRuleResponse,
    summary="Enable or pause rule",
)
def toggle_rule(
    rule_id: str,
    is_enabled: bool = Query(...),
    service: RulesAutomationService = Depends(get_rules_service),
) -> OrganizationRuleResponse:
    try:
        rule = service.toggle_rule(rule_id, is_enabled)
        return service.to_rule_response(rule)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete rule",
)
def delete_rule(
    rule_id: str,
    service: RulesAutomationService = Depends(get_rules_service),
) -> None:
    try:
        service.delete_rule(rule_id)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/evaluate-file",
    response_model=List[RuleEvaluationResult],
    summary="Evaluate file against active rules",
    description="Tests an existing file against active rules, executing approved operations or diverting conflicts to Review Changes.",
)
def evaluate_file(
    payload: RuleEvaluateFileRequest,
    service: RulesAutomationService = Depends(get_rules_service),
) -> List[RuleEvaluationResult]:
    try:
        return service.evaluate_file(payload.managed_folder_id, payload.relative_path)
    except RulesAutomationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

