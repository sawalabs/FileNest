from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_assistant_service
from backend.app.schemas.assistant import (
    AssistantExplainRequest,
    AssistantExplainResponse,
    AssistantSuggestPlanRequest,
    AssistantSuggestPlanResponse,
    AssistantTargetType,
    QuickPromptItem,
)
from backend.app.services.assistant import AssistantException, ContextualAssistantService
from backend.app.services.managed_folder import ManagedFolderException
from backend.app.services.transaction import TransactionException

router = APIRouter()


@router.post(
    "/explain",
    response_model=AssistantExplainResponse,
    summary="Explain selected file, folder, plan, or analysis within Managed Folder",
)
async def explain_entity(
    request: AssistantExplainRequest,
    service: ContextualAssistantService = Depends(get_assistant_service),
) -> AssistantExplainResponse:
    """Provides bounded contextual insights, safety assessments, and action proposals."""
    try:
        return await service.explain_entity(request)
    except AssistantException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assistant explanation failed: {str(e)}",
        )


@router.post(
    "/suggest-plan",
    response_model=AssistantSuggestPlanResponse,
    summary="Create a draft Change Plan in Review Changes from an assistant proposal",
)
def suggest_plan(
    request: AssistantSuggestPlanRequest,
    service: ContextualAssistantService = Depends(get_assistant_service),
) -> AssistantSuggestPlanResponse:
    """Routes an assistant recommendation directly to Review Changes (pending_review).
    
    Guarantees: Zero direct filesystem mutations. All changes require manual user approval.
    """
    try:
        return service.create_proposed_plan(request)
    except (AssistantException, TransactionException, ManagedFolderException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create proposed change plan: {str(e)}",
        )


@router.get(
    "/quick-prompts",
    response_model=List[QuickPromptItem],
    summary="Get contextual prompt suggestions based on selected entity type",
)
def get_quick_prompts(
    target_type: AssistantTargetType = Query(..., description="Target type: file, folder, plan, analysis, or general"),
    service: ContextualAssistantService = Depends(get_assistant_service),
) -> List[QuickPromptItem]:
    """Returns contextual quick question suggestions."""
    return service.get_quick_prompts(target_type)

