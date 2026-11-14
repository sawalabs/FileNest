from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==========================================
# 1. General Settings
# ==========================================
class GeneralSettings(BaseModel):
    app_name: str = "FileNest Desktop"
    default_workspace: str = ""
    download_location: str = ""
    temp_location: str = ""
    # Startup & Behavior
    start_on_startup: bool = False
    run_in_background: bool = True
    minimize_to_tray: bool = True
    restore_last_page: bool = True
    ask_before_exit: bool = True
    start_monitoring_on_launch: bool = True
    # UI
    theme: str = "system"  # light, dark, system
    sidebar_behavior: str = "expanded"  # expanded, collapsed, remember
    default_file_view: str = "list"  # list, grid
    default_table_density: str = "comfortable"  # comfortable, compact
    show_file_extensions: bool = True
    show_hidden_files: bool = False
    # Language & Format
    language: str = "en"
    date_format: str = "YYYY-MM-DD"
    time_format: str = "24h"  # 12h, 24h
    # Notifications
    desktop_notifications: bool = True
    job_notifications: bool = True
    monitoring_notifications: bool = True
    notification_sound: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"


# ==========================================
# 2. AI & Model Settings
# ==========================================
class AISettings(BaseModel):
    # Primary AI Gateway
    ai_provider: str = "9Router"
    # Model Gateway (9Router)
    router_endpoint: str = "http://127.0.0.1:20128/v1"
    router_timeout_seconds: int = 45
    router_status: str = "not_configured"  # connected, disconnected, not_configured
    has_router_api_key: bool = False
    masked_router_api_key: str = ""
    # OpenRouter Fallback Gateway
    openrouter_endpoint: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat"
    auto_fallback_enabled: bool = True
    has_openrouter_api_key: bool = False
    masked_openrouter_api_key: str = ""
    # Optional legacy fields for backward compatibility
    hermes_endpoint: Optional[str] = None
    hermes_timeout_seconds: Optional[int] = None
    hermes_max_concurrent_tasks: Optional[int] = None
    hermes_status: Optional[str] = None
    has_hermes_auth: Optional[bool] = None
    # Models
    default_model: str = "gpt-4o-mini"
    analysis_model: str = "gpt-4o"
    vision_model: str = "gpt-4o"
    enabled_models: List[str] = Field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.2
    # Analysis Preferences
    default_analysis_mode: str = "metadata_only"  # metadata_only, deep_analysis
    max_concurrent_analysis_jobs: int = 2
    analyze_file_content: bool = False
    analyze_images: bool = False
    analyze_documents: bool = False
    max_file_size_mb: int = 25
    # Privacy
    allow_remote_ai_processing: bool = False
    metadata_only: bool = True
    content_extraction_consent: bool = False
    sensitive_folder_exclusions: List[str] = Field(default_factory=list)
    sensitive_file_extensions: List[str] = Field(
        default_factory=lambda: [".key", ".pem", ".pfx", ".kdbx", ".env", ".id_rsa"]
    )


class AISettingsUpdate(BaseModel):
    hermes_endpoint: Optional[str] = None
    hermes_timeout_seconds: Optional[int] = None
    hermes_max_concurrent_tasks: Optional[int] = None
    hermes_auth_token: Optional[str] = None
    clear_hermes_auth: Optional[bool] = None

    router_endpoint: Optional[str] = None
    router_timeout_seconds: Optional[int] = None
    router_api_key: Optional[str] = None
    clear_router_api_key: Optional[bool] = None

    # OpenRouter Fallback
    openrouter_endpoint: Optional[str] = None
    openrouter_model: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    clear_openrouter_api_key: Optional[bool] = None
    auto_fallback_enabled: Optional[bool] = None

    default_model: Optional[str] = None
    analysis_model: Optional[str] = None
    vision_model: Optional[str] = None
    enabled_models: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    default_analysis_mode: Optional[str] = None
    max_concurrent_analysis_jobs: Optional[int] = None
    analyze_file_content: Optional[bool] = None
    analyze_images: Optional[bool] = None
    analyze_documents: Optional[bool] = None
    max_file_size_mb: Optional[int] = None

    allow_remote_ai_processing: Optional[bool] = None
    metadata_only: Optional[bool] = None
    content_extraction_consent: Optional[bool] = None
    sensitive_folder_exclusions: Optional[List[str]] = None
    sensitive_file_extensions: Optional[List[str]] = None


# ==========================================
# 3. Organization Settings
# ==========================================
class OrganizationSettings(BaseModel):
    default_strategy: str = "file_type"  # file_type, project_structure, custom
    default_folder_naming: str = "kebab-case"  # kebab-case, snake_case, PascalCase, numbered
    use_number_prefix: bool = True
    prefix_separator: str = "_"  # _, -, space
    default_archive_folder_name: str = "Archive"
    require_approval_for_new_rules: bool = True
    enable_approved_rule_automation: bool = True
    detect_destination_conflicts: bool = True
    conflict_resolution_strategy: str = "add_sequence"  # add_sequence, suggest_alternative, review_changes
    require_review_for_ambiguous: bool = True


# ==========================================
# 4. Monitoring Settings
# ==========================================
class MonitoringGlobalSettings(BaseModel):
    enable_monitoring: bool = True
    start_monitoring_on_launch: bool = True
    run_in_background: bool = True
    recursive_monitoring_default: bool = True
    watcher_recovery_on_startup: bool = True
    watcher_health_check_interval_seconds: int = 60
    debounce_interval_ms: int = 1000
    deduplication_enabled: bool = True
    max_queue_size: int = 5000
    batch_size: int = 100
    notify_file_created: bool = True
    notify_file_modified: bool = False
    notify_file_deleted: bool = True
    notify_folder_changed: bool = False
    notify_watcher_error: bool = True
    notify_rule_triggered: bool = True
    global_ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            ".git", "node_modules", "__pycache__", ".venv", ".DS_Store",
            "Thumbs.db", "desktop.ini", "*.tmp", "~$*"
        ]
    )


# ==========================================
# 5. Security & Access Settings
# ==========================================
class MandatorySafetyPolicy(BaseModel):
    policy_id: str
    name: str
    description: str
    status: str = "ENFORCED"
    can_disable: bool = False


class SecuritySettings(BaseModel):
    # Mandatory non-disableable safety rules (Rule 70 & 30)
    mandatory_policies: List[MandatorySafetyPolicy] = Field(
        default_factory=lambda: [
            MandatorySafetyPolicy(
                policy_id="managed_folders_isolation",
                name="Strict Managed Folders Confinement",
                description="Frontend and backend operations strictly confined to manually registered Managed Folders.",
            ),
            MandatorySafetyPolicy(
                policy_id="backend_path_validation",
                name="Canonical Path Validation",
                description="Every path is canonicalized and validated on the backend immediately before any action.",
            ),
            MandatorySafetyPolicy(
                policy_id="windows_system_protection",
                name="Windows System Directories Protection",
                description="System32, Windows, ProgramFiles, and drive roots can never be registered or modified.",
            ),
            MandatorySafetyPolicy(
                policy_id="symlink_reparse_block",
                name="Symlink & Reparse Point Blocking",
                description="Symbolic links and NTFS junctions are rejected to prevent directory traversal and escape.",
            ),
            MandatorySafetyPolicy(
                policy_id="transaction_manager_required",
                name="Transaction Manager Mandatory",
                description="All filesystem modifications must execute through validated plans with audit logging.",
            ),
            MandatorySafetyPolicy(
                policy_id="prevent_silent_overwrite",
                name="Prevent Silent Overwrites",
                description="Files cannot be silently overwritten; collisions require sequence resolution or review.",
            ),
            MandatorySafetyPolicy(
                policy_id="no_permanent_delete",
                name="No Automatic Permanent Deletion",
                description="Permanent file deletion is prohibited in all automated execution workflows.",
            ),
        ]
    )
    # Configurable security parameters
    require_confirmation_before_execution: bool = True
    require_confirmation_before_folder_remove: bool = True
    lock_settings: bool = False
    auto_lock_inactivity_minutes: int = 30
    require_reapproval_on_scope_change: bool = True
    # Privacy options
    anonymous_usage_reporting: bool = False
    crash_reporting: bool = False


# ==========================================
# 6. Storage & Database Settings
# ==========================================
class DatabaseInfo(BaseModel):
    engine: str = "SQLite 3 (WAL Mode)"
    location: str = "backend/app/db/database.db"
    size_bytes: int = 0
    wal_size_bytes: int = 0
    tables_count: int = 14
    health: str = "healthy"
    last_integrity_check: Optional[str] = None
    last_integrity_result: Optional[str] = None


class CacheInfo(BaseModel):
    total_cache_bytes: int = 0
    file_scan_cache_bytes: int = 0
    analysis_cache_bytes: int = 0
    thumbnail_cache_bytes: int = 0


class StorageSettings(BaseModel):
    database: DatabaseInfo = Field(default_factory=DatabaseInfo)
    cache: CacheInfo = Field(default_factory=CacheInfo)
    workspace_path: str = ""
    export_path: str = ""
    temp_path: str = ""


# ==========================================
# 7. About Settings
# ==========================================
class AboutSettings(BaseModel):
    app_name: str = "FileNest Desktop & Storage Manager"
    version: str = "0.1.0"
    build_number: str = "20261114-production"
    release_channel: str = "Production Release"
    tauri_version: str = "2.0.0"
    react_version: str = "18.3.1"
    python_version: str = "3.11.9"
    sqlite_version: str = "3.45.1"
    os_name: str = "Windows"
    os_version: str = "11 / 10 x64"
    architecture: str = "x86_64"


# ==========================================
# Top-level Response & Payloads
# ==========================================
class AllSettingsResponse(BaseModel):
    general: GeneralSettings
    ai: AISettings
    organization: OrganizationSettings
    monitoring: MonitoringGlobalSettings
    security: SecuritySettings
    storage: StorageSettings
    about: AboutSettings


class TestConnectionRequest(BaseModel):
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[int] = 10


class TestConnectionResponse(BaseModel):
    success: bool
    status: str
    message: str
    latency_ms: Optional[float] = None
    detected_version: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    name: str
    context_length: int = 128000
    provider: str = "9Router"
    supports_vision: bool = False
    is_default: bool = False


class AvailableModelsResponse(BaseModel):
    models: List[ModelInfo] = Field(default_factory=list)
    source: str = "remote"
    total_count: int = 0


class MaintenanceActionResult(BaseModel):
    success: bool
    action: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class InstallerArtifactInfo(BaseModel):
    filename: str
    path: str
    installer_type: str  # nsis | msi
    size_bytes: int
    modified_at: str


class AppUpdateStatusResponse(BaseModel):
    current_version: str
    latest_version: str
    build_number: str
    update_available: bool
    data_directory: str
    installers: List[InstallerArtifactInfo] = Field(default_factory=list)
    message: str


class ApplyUpdateRequest(BaseModel):
    installer_path: Optional[str] = None


class ApplyUpdateResponse(BaseModel):
    success: bool
    installer_path: str
    message: str

