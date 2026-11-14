export interface BackendHealth {
  status: "ok" | "error" | "connecting";
  project?: string;
  version?: string;
  environment?: string;
  timestamp?: string;
  error?: string;
}

export interface FolderCapabilities {
  organization: boolean;
  smart_rename: boolean;
  monitoring: boolean;
  analysis: boolean;
  content_extraction: boolean;
}

export interface FolderExclusionItem {
  id: string;
  folder_id: string;
  exclusion_type: "directory" | "extension" | "pattern" | "file";
  value: string;
  reason?: string | null;
  is_enabled: boolean;
  created_at: string;
}

export interface FolderHealthCheck {
  folder_id: string;
  folder_name: string;
  root_path: string;
  is_accessible: boolean;
  exists: boolean;
  can_read: boolean;
  can_write: boolean;
  is_symlink: boolean;
  is_reparse_point: boolean;
  watcher_status: string;
  last_scanned_at?: string | null;
  last_error?: string | null;
  overall_status: "healthy" | "warning" | "error" | "inaccessible";
}

export interface FolderUsageStats {
  folder_id: string;
  total_size_bytes: number;
  total_files_count: number;
  storage_limit_bytes?: number | null;
  usage_percentage?: number | null;
  last_scanned_at?: string | null;
}

export interface FolderSummaryCards {
  total_folders: number;
  active_folders: number;
  total_size_bytes: number;
  total_files: number;
  active_rules_count: number;
  monitored_folders_count: number;
  health_status: "healthy" | "warning" | "error";
}

export interface ManagedFolder {
  id: string;
  name: string;
  root_path: string;
  is_enabled: boolean;
  monitoring_enabled: boolean;
  scan_on_startup: boolean;
  exclude_patterns: string[];
  capabilities?: FolderCapabilities;
  total_size_bytes?: number;
  total_files?: number;
  health_status?: string;
  last_scanned_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type NavItem =
  | "dashboard"
  | "files"
  | "storage"
  | "organization"
  | "smart-rename"
  | "review-changes"
  | "monitoring"
  | "history"
  | "managed-folders"
  | "settings";

export type FileCategory =
  | "document"
  | "image"
  | "video"
  | "audio"
  | "archive"
  | "code"
  | "other";

export interface FileItemMetadata {
  name: string;
  relative_path: string;
  parent_relative_path: string;
  item_type: "file" | "directory";
  size_bytes: number;
  category: FileCategory;
  extension?: string | null;
  mime_type?: string | null;
  modified_at?: string | null;
  created_at?: string | null;
  is_hidden: boolean;
  is_symlink: boolean;
  is_inaccessible: boolean;
  error_message?: string | null;
}

export interface DirectoryListingResponse {
  managed_folder_id: string;
  managed_folder_name: string;
  current_relative_path: string;
  parent_relative_path?: string | null;
  entries: FileItemMetadata[];
  total_files: number;
  total_directories: number;
  total_size_bytes: number;
}

export interface FolderSummaryResponse {
  managed_folder_id: string;
  relative_path: string;
  total_size_bytes: number;
  file_count: number;
  directory_count: number;
  category_counts: Record<string, number>;
  category_bytes: Record<string, number>;
  inaccessible_count: number;
}

export interface OperationLogResponse {
  id: string;
  execution_job_id: string;
  change_plan_item_id: string;
  operation: string;
  source_path_snapshot?: string | null;
  destination_path_snapshot?: string | null;
  status: string;
  backup_reference?: string | null;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
}

export interface ExecutionJobResponse {
  id: string;
  change_plan_id: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  created_at: string;
  operations_count: number;
  completed_count: number;
  failed_count: number;
  operation_logs: OperationLogResponse[];
}

export interface LargeFileItem {
  name: string;
  relative_path: string;
  size_bytes: number;
  category: string;
  extension?: string | null;
  modified_at?: string | null;
  managed_folder_id?: string | null;
}

export interface DuplicateFileItem {
  name: string;
  relative_path: string;
  size_bytes: number;
  modified_at?: string | null;
  managed_folder_id?: string | null;
}

export interface DuplicateGroup {
  hash: string;
  size_bytes: number;
  files_count: number;
  potential_savings_bytes: number;
  files: DuplicateFileItem[];
}

export interface EmptyFolderItem {
  name: string;
  relative_path: string;
  modified_at?: string | null;
  managed_folder_id?: string | null;
}

export interface CategoryDistribution {
  category: string;
  files_count: number;
  total_size_bytes: number;
  percentage: number;
}

export interface FileTypeStats {
  category: string;
  extension: string;
  files_count: number;
  total_size_bytes: number;
  percentage: number;
}

export interface LargestFolderItem {
  name: string;
  relative_path: string;
  total_size_bytes: number;
  files_count: number;
  percentage: number;
  managed_folder_id?: string | null;
}

export interface StorageRecommendation {
  id: string;
  title: string;
  description: string;
  target_tab: string;
  impact_bytes: number;
  count: number;
}

export interface StorageUsageTrendPoint {
  date: string;
  total_size_bytes: number;
}

export interface StorageAnalysisResult {
  managed_folder_id?: string | null;
  managed_folder_name: string;
  analyzed_at: string;
  total_storage_bytes: number;
  total_files_count: number;
  total_folders_count: number;
  large_files_count: number;
  large_files_bytes: number;
  large_files_percentage: number;
  duplicate_groups_count: number;
  duplicate_files_count: number;
  potential_savings_bytes: number;
  empty_folders_count: number;
  category_distribution: CategoryDistribution[];
  file_types: FileTypeStats[];
  largest_folders: LargestFolderItem[];
  recommendations: StorageRecommendation[];
  large_files: LargeFileItem[];
  duplicate_groups: DuplicateGroup[];
  empty_folders: EmptyFolderItem[];
  trend_points: StorageUsageTrendPoint[];
}

export interface StorageAnalysisRequest {
  managed_folder_id?: string | null;
  large_file_threshold_bytes?: number;
  calculate_hashes?: boolean;
}

// -----------------------------------------------------------------------------
// Organization & Smart Rename Types
// -----------------------------------------------------------------------------

export interface StructureTreeNode {
  name: string;
  relative_path: string;
  item_type: string;
  files_count: number;
  size_bytes: number;
  is_new: boolean;
  children?: StructureTreeNode[];
}

export interface ProposedChangeItem {
  item_id?: string | null;
  sequence_no: number;
  operation: "create_directory" | "move" | "rename";
  source_relative_path?: string | null;
  destination_relative_path: string;
  file_name: string;
  size_bytes: number;
  category?: string | null;
  status: "pending" | "conflict" | "skipped";
  conflict_reason?: string | null;
}

export interface OrganizationPlanRequest {
  managed_folder_id: string;
  target_subfolder?: string;
  strategy: "by_category" | "by_date" | "by_extension" | "by_project" | "custom";
  custom_rules?: Record<string, any>;
  include_subfolders?: boolean;
  move_unorganized_only?: boolean;
  title?: string;
}

export interface OrganizationPlanResult {
  change_plan_id: string;
  managed_folder_id: string;
  managed_folder_name: string;
  strategy: string;
  title: string;
  status: string;
  created_at: string;
  files_analyzed_count: number;
  files_to_move_count: number;
  folders_to_create_count: number;
  conflicts_count: number;
  total_size_bytes: number;
  protected_folders_skipped_count?: number;
  protected_folders_skipped?: string[];
  current_structure: StructureTreeNode[];
  proposed_structure: StructureTreeNode[];
  items: ProposedChangeItem[];
}

export interface ProtectedSubfolderItem {
  id: string;
  managed_folder_id: string;
  relative_path: string;
  name: string;
  source: "manual" | "smart_detect" | "ai" | string;
  category: "tool_bundle" | "code_project" | "sdk_runtime" | "custom" | string;
  reason: string;
  confidence: number;
  is_protected: boolean;
  created_at: string;
}

export interface ProtectedFoldersListResponse {
  managed_folder_id: string;
  protected_folders: ProtectedSubfolderItem[];
  available_subfolders: string[];
}

export interface ProtectedFoldersDetectResponse {
  managed_folder_id: string;
  newly_flagged_count: number;
  total_protected_count: number;
  detection_mode: string;
  protected_folders: ProtectedSubfolderItem[];
  available_subfolders: string[];
}

export interface SmartRenamePlanRequest {
  managed_folder_id: string;
  target_subfolder?: string;
  target_relative_paths?: string[];
  strategy: "make_consistent" | "pattern" | "add_meaningful" | "describe_content";
  pattern?: string;
  case_transform?: "lower" | "upper" | "title" | "preserve";
  space_replacement?: "_" | "-" | "none";
  keep_extension?: boolean;
  add_sequence_on_collision?: boolean;
  skip_compliant_files?: boolean;
  prefix?: string;
  suffix?: string;
  title?: string;
  use_ai_content?: boolean;
  run_ocr_background?: boolean;
}

export interface ItemOCRAnalyzeRequest {
  plan_id: string;
  item_id: string;
}

export interface ItemOCRAnalyzeResponse {
  item_id: string;
  plan_id: string;
  source_relative_path: string;
  original_name: string;
  proposed_name: string;
  destination_relative_path: string;
  extracted_text?: string | null;
  status: "ready" | "conflict" | "unchanged";
  conflict_reason?: string | null;
  success: boolean;
  error_message?: string | null;
}

export interface BatchOCRJobStatus {
  plan_id: string;
  is_running: boolean;
  total_items: number;
  processed_items: number;
  success_count: number;
  error_count: number;
  current_item_name?: string | null;
  message?: string | null;
}

export interface SmartRenamePreviewItem {
  item_id?: string | null;
  sequence_no: number;
  source_relative_path: string;
  original_name: string;
  proposed_name: string;
  destination_relative_path: string;
  size_bytes: number;
  extension?: string | null;
  category?: string | null;
  status: "ready" | "conflict" | "unchanged";
  conflict_reason?: string | null;
}

export interface SmartRenamePlanResult {
  change_plan_id: string;
  managed_folder_id: string;
  managed_folder_name: string;
  strategy: string;
  title: string;
  status: string;
  created_at: string;
  files_analyzed_count: number;
  files_to_rename_count: number;
  files_unchanged_count: number;
  conflicts_count: number;
  total_size_bytes: number;
  items: SmartRenamePreviewItem[];
}

export interface ChangePlanItemResponse {
  id: string;
  change_plan_id: string;
  operation: string;
  source_relative_path?: string | null;
  destination_relative_path?: string | null;
  expected_size_bytes?: number | null;
  status: string;
  conflict_reason?: string | null;
  sequence_no: number;
}

export interface ChangePlanResponse {
  id: string;
  managed_folder_id: string;
  analysis_run_id?: string | null;
  title: string;
  plan_type: string;
  status: string;
  created_by: string;
  approved_at?: string | null;
  approved_by?: string | null;
  created_at: string;
  updated_at?: string;
  items: ChangePlanItemResponse[];
  latest_execution_job?: ExecutionJobResponse | null;
}

export interface PlanValidationIssue {
  item_index: number;
  sequence_no: number;
  operation: string;
  source_relative_path?: string | null;
  destination_relative_path?: string | null;
  issue_type: "error" | "conflict" | "warning";
  message: string;
}

export interface PlanValidationSummary {
  is_valid: boolean;
  can_execute: boolean;
  total_items: number;
  issues: PlanValidationIssue[];
}

export interface AuditLogItem {
  id: string;
  actor_type: "user" | "ai" | "system";
  action: string;
  entity_type: string;
  entity_id?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  total: number;
  items: AuditLogItem[];
}

export interface ExecutionHistoryOperationLog {
  id: string;
  operation: string;
  source_path_snapshot?: string | null;
  destination_path_snapshot?: string | null;
  status: string;
  backup_reference?: string | null;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
}

export interface ExecutionHistoryItem {
  id: string;
  change_plan_id: string;
  change_plan_title: string;
  plan_type: string;
  managed_folder_id: string;
  managed_folder_name: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  created_at: string;
  operations_count: number;
  completed_count: number;
  failed_count: number;
  rolled_back_count: number;
  operation_logs: ExecutionHistoryOperationLog[];
}

export interface ExecutionHistoryListResponse {
  total: number;
  items: ExecutionHistoryItem[];
}

export interface HistorySummaryStats {
  total_activities: number;
  file_changes_count: number;
  executions_succeeded: number;
  executions_failed: number;
  rollbacks_count: number;
  pending_plans_count: number;
}

// -----------------------------------------------------------------------------
// Monitoring Types
// -----------------------------------------------------------------------------

export interface WatcherItem {
  folder_id: string;
  folder_name: string;
  root_path: string;
  status: "watching" | "paused" | "stopped" | "error" | "initializing";
  is_enabled: boolean;
  recursive: boolean;
  debounce_ms: number;
  ignore_patterns: string[];
  events_count_24h: number;
  last_event_at?: string | null;
  error_message?: string | null;
}

export interface MonitoringConfigUpdatePayload {
  is_enabled?: boolean;
  recursive?: boolean;
  debounce_ms?: number;
  ignore_patterns?: string[];
}

export interface MonitoringEventItem {
  id: string;
  managed_folder_id: string;
  managed_folder_name: string;
  event_type: "created" | "modified" | "deleted" | "moved";
  relative_path: string;
  destination_relative_path?: string | null;
  status: string;
  occurred_at: string;
  size_bytes?: number | null;
}

export interface MonitoringEventListResponse {
  total: number;
  items: MonitoringEventItem[];
}

export interface MonitoringSummaryStats {
  monitored_folders_count: number;
  active_watchers_count: number;
  total_events_24h: number;
  files_created_count: number;
  files_modified_count: number;
  files_deleted_count: number;
  total_change_size_bytes: number;
}

export interface ActivityChartPoint {
  timestamp: string;
  created: number;
  modified: number;
  deleted: number;
}

export interface ActivityChartResponse {
  time_range: string;
  data_points: ActivityChartPoint[];
}

export interface DistributionItem {
  event_type: string;
  count: number;
  percentage: number;
}

export interface DistributionResponse {
  total_events: number;
  distribution: DistributionItem[];
}

// ==========================================
// Settings Types
// ==========================================
export interface GeneralSettings {
  app_name: string;
  default_workspace: string;
  download_location: string;
  temp_location: string;
  start_on_startup: boolean;
  run_in_background: boolean;
  minimize_to_tray: boolean;
  restore_last_page: boolean;
  ask_before_exit: boolean;
  start_monitoring_on_launch: boolean;
  theme: string;
  sidebar_behavior: string;
  default_file_view: string;
  default_table_density: string;
  show_file_extensions: boolean;
  show_hidden_files: boolean;
  language: string;
  date_format: string;
  time_format: string;
  desktop_notifications: boolean;
  job_notifications: boolean;
  monitoring_notifications: boolean;
  notification_sound: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
}

export interface AISettings {
  ai_provider: string;
  hermes_endpoint?: string;
  hermes_timeout_seconds?: number;
  hermes_max_concurrent_tasks?: number;
  hermes_status?: string;
  has_hermes_auth?: boolean;
  router_endpoint: string;
  router_timeout_seconds: number;
  router_status: string;
  has_router_api_key: boolean;
  masked_router_api_key: string;
  openrouter_endpoint?: string;
  openrouter_model?: string;
  auto_fallback_enabled?: boolean;
  has_openrouter_api_key?: boolean;
  masked_openrouter_api_key?: string;
  default_model: string;
  analysis_model: string;
  vision_model: string;
  enabled_models?: string[];
  max_tokens: number;
  temperature: number;
  default_analysis_mode: string;
  max_concurrent_analysis_jobs: number;
  analyze_file_content: boolean;
  analyze_images: boolean;
  analyze_documents: boolean;
  max_file_size_mb: number;
  allow_remote_ai_processing: boolean;
  metadata_only: boolean;
  content_extraction_consent: boolean;
  sensitive_folder_exclusions: string[];
  sensitive_file_extensions: string[];
}

export interface AISettingsUpdate {
  hermes_endpoint?: string;
  hermes_timeout_seconds?: number;
  hermes_max_concurrent_tasks?: number;
  hermes_auth_token?: string;
  clear_hermes_auth?: boolean;
  router_endpoint?: string;
  router_timeout_seconds?: number;
  router_api_key?: string;
  clear_router_api_key?: boolean;
  openrouter_endpoint?: string;
  openrouter_model?: string;
  auto_fallback_enabled?: boolean;
  openrouter_api_key?: string;
  clear_openrouter_api_key?: boolean;
  default_model?: string;
  analysis_model?: string;
  vision_model?: string;
  enabled_models?: string[];
  max_tokens?: number;
  temperature?: number;
  default_analysis_mode?: string;
  max_concurrent_analysis_jobs?: number;
  analyze_file_content?: boolean;
  analyze_images?: boolean;
  analyze_documents?: boolean;
  max_file_size_mb?: number;
  allow_remote_ai_processing?: boolean;
  metadata_only?: boolean;
  content_extraction_consent?: boolean;
  sensitive_folder_exclusions?: string[];
  sensitive_file_extensions?: string[];
}

export interface OrganizationSettings {
  default_strategy: string;
  default_folder_naming: string;
  use_number_prefix: boolean;
  prefix_separator: string;
  default_archive_folder_name: string;
  require_approval_for_new_rules: boolean;
  enable_approved_rule_automation: boolean;
  detect_destination_conflicts: boolean;
  conflict_resolution_strategy: string;
  require_review_for_ambiguous: boolean;
}

export interface MonitoringGlobalSettings {
  enable_monitoring: boolean;
  start_monitoring_on_launch: boolean;
  run_in_background: boolean;
  recursive_monitoring_default: boolean;
  watcher_recovery_on_startup: boolean;
  watcher_health_check_interval_seconds: number;
  debounce_interval_ms: number;
  deduplication_enabled: boolean;
  max_queue_size: number;
  batch_size: number;
  notify_file_created: boolean;
  notify_file_modified: boolean;
  notify_file_deleted: boolean;
  notify_folder_changed: boolean;
  notify_watcher_error: boolean;
  notify_rule_triggered: boolean;
  global_ignore_patterns: string[];
}

export interface MandatorySafetyPolicy {
  policy_id: string;
  name: string;
  description: string;
  status: string;
  can_disable: boolean;
}

export interface SecuritySettings {
  mandatory_policies: MandatorySafetyPolicy[];
  require_confirmation_before_execution: boolean;
  require_confirmation_before_folder_remove: boolean;
  lock_settings: boolean;
  auto_lock_inactivity_minutes: number;
  require_reapproval_on_scope_change: boolean;
  anonymous_usage_reporting: boolean;
  crash_reporting: boolean;
}

export interface DatabaseInfo {
  engine: string;
  location: string;
  size_bytes: number;
  wal_size_bytes: number;
  tables_count: number;
  health: string;
  last_integrity_check?: string | null;
  last_integrity_result?: string | null;
}

export interface CacheInfo {
  total_cache_bytes: number;
  file_scan_cache_bytes: number;
  analysis_cache_bytes: number;
  thumbnail_cache_bytes: number;
}

export interface StorageSettings {
  database: DatabaseInfo;
  cache: CacheInfo;
  workspace_path: string;
  export_path: string;
  temp_path: string;
}

export interface AboutSettings {
  app_name: string;
  version: string;
  build_number: string;
  release_channel: string;
  tauri_version: string;
  react_version: string;
  python_version: string;
  sqlite_version: string;
  os_name: string;
  os_version: string;
  architecture: string;
}

export interface AllSettingsResponse {
  general: GeneralSettings;
  ai: AISettings;
  organization: OrganizationSettings;
  monitoring: MonitoringGlobalSettings;
  security: SecuritySettings;
  storage: StorageSettings;
  about: AboutSettings;
}

export interface TestConnectionResponse {
  success: boolean;
  status: string;
  message: string;
  latency_ms?: number | null;
  detected_version?: string | null;
}

export interface ModelInfo {
  id: string;
  name: string;
  context_length: number;
  provider: string;
  supports_vision: boolean;
  is_default?: boolean;
}

export interface AvailableModelsResponse {
  models: ModelInfo[];
  source?: string;
  total_count?: number;
}

export interface MaintenanceActionResult {
  success: boolean;
  action: string;
  message: string;
  details: Record<string, any>;
}

export interface DashboardSummaryCardsData {
  managed_folders_count: number;
  total_files_count: number;
  total_size_bytes: number;
  pending_changes_count: number;
}

export interface DashboardCategoryItemData {
  category: string;
  files_count: number;
  total_size_bytes: number;
  percentage: number;
}

export interface DashboardFolderDistributionItemData {
  id: string;
  name: string;
  root_path: string;
  size_bytes: number;
  files_count: number;
  percentage: number;
}

export interface DashboardManagedFolderItemData {
  id: string;
  name: string;
  root_path: string;
  size_bytes: number;
  files_count: number;
  is_monitoring_active: boolean;
  is_accessible: boolean;
  last_scanned_at?: string | null;
}

export interface DashboardRecentActivityItemData {
  id: string;
  timestamp: string;
  action: string;
  actor_type: string;
  entity_type: string;
  entity_id?: string | null;
  location?: string | null;
  details?: string | null;
  status: string;
}

export interface DashboardRecommendationItemData {
  id: string;
  title: string;
  description: string;
  type: "organization" | "smart_rename" | "duplicates" | "empty_folders" | "general";
  target_route: string;
  impact_count: number;
  impact_bytes: number;
}

export interface DashboardJobItemData {
  id: string;
  job_name: string;
  job_type: "scan" | "analysis" | "transaction";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress_percent: number;
  folder_name?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
}

export interface DashboardStorageTrendPointData {
  date: string;
  total_size_bytes: number;
  files_count: number;
  files_added: number;
  files_modified: number;
  files_deleted: number;
}

export interface DashboardOverviewResponse {
  summary_cards: DashboardSummaryCardsData;
  storage_categories: DashboardCategoryItemData[];
  folder_distribution: DashboardFolderDistributionItemData[];
  managed_folders: DashboardManagedFolderItemData[];
  recent_activities: DashboardRecentActivityItemData[];
  recommendations: DashboardRecommendationItemData[];
  jobs: DashboardJobItemData[];
  storage_history: DashboardStorageTrendPointData[];
  is_stale: boolean;
  last_refreshed_at: string;
}

export interface DashboardAnalyzeRequest {
  folder_id?: string | null;
  mode: "all" | "single" | "metadata" | "deep";
}

// -----------------------------------------------------------------------------
// Contextual Assistant Types
// -----------------------------------------------------------------------------

export type AssistantTargetType = "file" | "folder" | "analysis" | "plan" | "general";

export interface AssistantActionProposalItem {
  operation: "create_directory" | "rename" | "move" | "copy" | "delete_to_recycle_bin";
  source_relative_path?: string | null;
  destination_relative_path?: string | null;
  sequence_no: number;
}

export interface AssistantActionProposal {
  proposal_id: string;
  title: string;
  description: string;
  plan_type: "manual" | "organize" | "rename";
  items: AssistantActionProposalItem[];
}

export interface AssistantExplainRequest {
  managed_folder_id: string;
  target_type: AssistantTargetType;
  relative_path?: string | null;
  entity_id?: string | null;
  user_query?: string | null;
}

export interface AssistantExplainResponse {
  managed_folder_id: string;
  target_type: AssistantTargetType;
  target_name: string;
  relative_path?: string | null;
  title: string;
  summary: string;
  key_insights: string[];
  metadata: Record<string, any>;
  safety_assessment: string;
  suggested_actions: AssistantActionProposal[];
  timestamp: string;
}

export interface AssistantSuggestPlanRequest {
  managed_folder_id: string;
  title: string;
  plan_type?: "manual" | "organize" | "rename";
  items: AssistantActionProposalItem[];
}

export interface AssistantSuggestPlanResponse {
  plan_id: string;
  title: string;
  plan_type: string;
  status: string;
  items_count: number;
  message: string;
  created_at: string;
}

export interface QuickPromptItem {
  label: string;
  prompt: string;
  target_type: AssistantTargetType;
}

export interface OCRExtractRequest {
  folder_id: string;
  relative_path: string;
  max_pages?: number;
}

export interface OCRLineItem {
  text: string;
  confidence: number;
  box?: number[][];
}

export interface OCRPageResult {
  page_number: number;
  text: string;
  lines: OCRLineItem[];
  confidence: number;
}

export interface OCRExtractResponse {
  success: boolean;
  filename: string;
  folder_id: string;
  relative_path: string;
  full_text: string;
  word_count: number;
  confidence: number;
  pages: OCRPageResult[];
  duration_ms: number;
  engine: string;
  error?: string;
}

export interface OCRStatusResponse {
  available: boolean;
  engine: string;
  supported_formats: string[];
}

export interface StorageCleanupItemInput {
  managed_folder_id: string;
  relative_path: string;
  reason?: string;
}

export interface StorageCleanupPlanRequest {
  cleanup_type: "duplicates" | "large_files" | "empty_folders";
  title?: string;
  items: StorageCleanupItemInput[];
}

export interface StorageCleanupPlanResponse {
  created_plan_ids: string[];
  total_items_queued: number;
  message: string;
}

export interface UndoExecutionResponse {
  job_id: string;
  reverted_count: number;
  skipped_count: number;
  failed_count: number;
  status: string;
  details: string[];
}

export interface RuleScope {
  subpath: string;
  extensions: string[];
  min_size_bytes?: number | null;
  max_size_bytes?: number | null;
}

export interface RuleCondition {
  field: string;
  operator:
    | "equals"
    | "contains"
    | "starts_with"
    | "ends_with"
    | "matches_regex"
    | "in"
    | "greater_than"
    | "less_than";
  value: string | number | string[];
}

export interface RuleAction {
  action_type: "move" | "rename" | "create_directory";
  target_directory?: string | null;
  naming_pattern?: string | null;
  create_subfolders?: boolean;
}

export interface OrganizationRuleCreate {
  managed_folder_id: string;
  name: string;
  rule_type: "organize" | "rename";
  scope: RuleScope;
  conditions: RuleCondition[];
  actions: RuleAction[];
  is_enabled?: boolean;
}

export interface OrganizationRuleResponse {
  id: string;
  managed_folder_id: string;
  name: string;
  rule_type: string;
  scope: RuleScope;
  conditions: RuleCondition[];
  actions: RuleAction[];
  is_enabled: boolean;
  approved_at?: string | null;
  approved_by?: string | null;
  is_approved: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface RuleExecutionResponse {
  id: string;
  organization_rule_id: string;
  monitoring_event_id?: string | null;
  execution_job_id?: string | null;
  rule_version: number;
  status: string;
  reason?: string | null;
  created_at: string;
}

export interface GlobalSearchHit {
  managed_folder_id: string;
  managed_folder_name: string;
  name: string;
  relative_path: string;
  parent_relative_path: string;
  item_type: string;
  size_bytes: number;
  extension?: string | null;
  category: string;
  modified_at?: string | null;
}

export interface GlobalSearchResponse {
  query: string;
  hits: GlobalSearchHit[];
  truncated: boolean;
}

export interface InstallerArtifactInfo {
  filename: string;
  path: string;
  installer_type: "nsis" | "msi" | string;
  size_bytes: number;
  modified_at: string;
}

export interface AppUpdateStatusResponse {
  current_version: string;
  latest_version: string;
  build_number: string;
  update_available: boolean;
  data_directory: string;
  installers: InstallerArtifactInfo[];
  message: string;
}

export interface ApplyUpdateResponse {
  success: boolean;
  installer_path: string;
  message: string;
}







