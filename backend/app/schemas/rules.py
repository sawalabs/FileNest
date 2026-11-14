from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuleScope(BaseModel):
    subpath: str = Field(
        default="",
        description="Relative subpath within managed folder to confine rule scope (empty string for root)",
    )
    extensions: List[str] = Field(
        default_factory=list,
        description="Allowed file extensions (e.g. ['pdf', 'docx']). Empty means all.",
    )
    min_size_bytes: Optional[int] = Field(
        default=None,
        description="Minimum file size in bytes to apply rule",
    )
    max_size_bytes: Optional[int] = Field(
        default=None,
        description="Maximum file size in bytes to apply rule",
    )


class RuleCondition(BaseModel):
    field: str = Field(description="Target attribute: 'name', 'extension', 'category', 'size_bytes'")
    operator: Literal[
        "equals",
        "contains",
        "starts_with",
        "ends_with",
        "matches_regex",
        "in",
        "greater_than",
        "less_than",
    ] = Field(description="Comparison operator")
    value: Any = Field(description="Comparison value")

    @model_validator(mode="after")
    def validate_condition_regex(self) -> "RuleCondition":
        if self.operator == "matches_regex":
            from backend.app.core.security import validate_regex_pattern

            try:
                validate_regex_pattern(str(self.value))
            except ValueError as e:
                raise ValueError(str(e))
        return self


class RuleAction(BaseModel):
    action_type: Literal["move", "rename", "create_directory"] = Field(
        description="Operation to perform on matching files"
    )
    target_directory: Optional[str] = Field(
        default=None,
        description="Target directory relative to managed folder root",
    )
    naming_pattern: Optional[str] = Field(
        default=None,
        description="Pattern for rename, e.g. '{date}_{name}' or 'Invoice_{index}'",
    )
    create_subfolders: bool = Field(
        default=False,
        description="Whether to organize into dynamic subfolders (e.g. by year/month)",
    )


class OrganizationRuleCreate(BaseModel):
    managed_folder_id: str
    name: str = Field(min_length=3, max_length=255)
    rule_type: Literal["organize", "rename"] = "organize"
    scope: RuleScope = Field(default_factory=RuleScope)
    conditions: List[RuleCondition] = Field(default_factory=list)
    actions: List[RuleAction] = Field(min_length=1)
    is_enabled: bool = False


class OrganizationRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=255)
    scope: Optional[RuleScope] = None
    conditions: Optional[List[RuleCondition]] = None
    actions: Optional[List[RuleAction]] = None
    is_enabled: Optional[bool] = None


class OrganizationRuleApproveRequest(BaseModel):
    approved_by: str = Field(default="user", max_length=255)


class OrganizationRuleResponse(BaseModel):
    id: str
    managed_folder_id: str
    name: str
    rule_type: str
    scope: RuleScope
    conditions: List[RuleCondition] = []
    actions: List[RuleAction] = []
    is_enabled: bool
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    is_approved: bool
    version: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class RuleExecutionResponse(BaseModel):
    id: str
    organization_rule_id: str
    monitoring_event_id: Optional[str] = None
    execution_job_id: Optional[str] = None
    rule_version: int
    status: str  # "executed", "pending_review", "skipped", "failed"
    reason: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    file_path: str
    matched: bool
    eligible_for_auto_execution: bool
    execution_status: Literal["executed", "routed_to_review", "skipped", "failed"]
    plan_id: Optional[str] = None
    message: str


class RuleEvaluateFileRequest(BaseModel):
    managed_folder_id: str
    relative_path: str

