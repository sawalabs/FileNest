import type {
  BackendHealth,
  ChangePlanItemResponse,
  ChangePlanResponse,
  DirectoryListingResponse,
  ExecutionJobResponse,
  FileItemMetadata,
  FolderSummaryResponse,
  ManagedFolder,
  OrganizationPlanRequest,
  OrganizationPlanResult,
  SmartRenamePlanRequest,
  SmartRenamePlanResult,
  StorageAnalysisRequest,
  StorageAnalysisResult,
  PlanValidationSummary,
  AuditLogListResponse,
  ExecutionHistoryListResponse,
  HistorySummaryStats,
  WatcherItem,
  MonitoringConfigUpdatePayload,
  MonitoringEventListResponse,
  MonitoringSummaryStats,
  ActivityChartResponse,
  DistributionResponse,
  AllSettingsResponse,
  AvailableModelsResponse,
  FolderCapabilities,
  FolderExclusionItem,
  FolderHealthCheck,
  FolderSummaryCards,
  FolderUsageStats,
  MaintenanceActionResult,
  StorageSettings,
  TestConnectionResponse,
  DashboardOverviewResponse,
  DashboardAnalyzeRequest,
  DashboardJobItemData,
  AssistantExplainRequest,
  AssistantExplainResponse,
  AssistantSuggestPlanRequest,
  AssistantSuggestPlanResponse,
  AssistantTargetType,
  QuickPromptItem,
  OCRExtractRequest,
  OCRExtractResponse,
  OCRStatusResponse,
  ItemOCRAnalyzeResponse,
  BatchOCRJobStatus,
  StorageCleanupPlanRequest,
  StorageCleanupPlanResponse,
  UndoExecutionResponse,
  OrganizationRuleCreate,
  OrganizationRuleResponse,
  RuleExecutionResponse,
  GlobalSearchResponse,
  AppUpdateStatusResponse,
  ApplyUpdateResponse,
} from "@/types";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const nativeFetch = globalThis.fetch;

const fetchWithToken = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  let token = ApiService.getAppToken();
  if (!token) {
    await ApiService.initSession();
    token = ApiService.getAppToken();
  }

  const buildHeaders = (baseInit?: RequestInit): Headers => {
    const headers = new Headers(baseInit?.headers || {});
    const curToken = ApiService.getAppToken();
    if (curToken && !headers.has("X-App-Token")) {
      headers.set("X-App-Token", curToken);
    }
    return headers;
  };

  let response = await nativeFetch(input, {
    ...init,
    headers: buildHeaders(init),
  });

  // If unauthorized (e.g. backend restarted and token rotated), re-negotiate session and retry once
  if (response.status === 401) {
    const refreshed = await ApiService.initSession();
    if (refreshed) {
      response = await nativeFetch(input, {
        ...init,
        headers: buildHeaders(init),
      });
    }
  }

  return response;
};

// Shadow global fetch for all ApiService endpoints to attach X-App-Token automatically
const fetch = fetchWithToken;

export interface RegisterFolderPayload {
  name: string;
  root_path: string;
  monitoring_enabled?: boolean;
  scan_on_startup?: boolean;
  exclude_patterns?: string[];
}

export class ApiService {
  private static baseUrl = BACKEND_URL;
  private static appToken: string | null = null;

  public static setAppToken(token: string | null): void {
    this.appToken = token;
    if (typeof window !== "undefined") {
      if (token) {
        window.sessionStorage.setItem("x-app-token", token);
      } else {
        window.sessionStorage.removeItem("x-app-token");
      }
    }
  }

  public static getAppToken(): string | null {
    if (!this.appToken && typeof window !== "undefined") {
      this.appToken = window.sessionStorage.getItem("x-app-token") || null;
    }
    return this.appToken;
  }

  public static async initSession(): Promise<string | null> {
    try {
      const response = await nativeFetch(`${this.baseUrl}/api/v1/auth/session`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        if (data.token) {
          this.setAppToken(data.token);
          return data.token;
        }
      }
    } catch {
      // Backend may be offline or starting up
    }
    return null;
  }

  public static async checkHealth(): Promise<BackendHealth> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/health`, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        return {
          status: "error",
          error: `Backend responded with HTTP ${response.status}`,
        };
      }

      const data = await response.json();
      return {
        status: data.status,
        project: data.project,
        version: data.version,
        environment: data.environment,
        timestamp: data.timestamp,
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to reach backend";
      return {
        status: "error",
        error: message,
      };
    }
  }

  // ---------------------------------------------------------------------------
  // Managed Folders
  // ---------------------------------------------------------------------------

  public static async listFolders(onlyEnabled = true): Promise<ManagedFolder[]> {
    const url = `${this.baseUrl}/api/v1/folders${onlyEnabled ? "?only_enabled=true" : ""}`;
    const response = await fetch(url);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch folders: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async registerFolder(payload: RegisterFolderPayload): Promise<ManagedFolder> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to register folder: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async toggleFolder(folderId: string, enable: boolean): Promise<ManagedFolder> {
    const action = enable ? "enable" : "disable";
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/${action}`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to ${action} folder`);
    }
    return response.json();
  }

  public static async unregisterFolder(folderId: string, permanent: boolean = true): Promise<ManagedFolder> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/folders/${folderId}${permanent ? "?permanent=true" : ""}`,
      {
        method: "DELETE",
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to unregister folder");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Filesystem Browsing & Metadata
  // ---------------------------------------------------------------------------

  public static async browseDirectory(
    folderId: string,
    relativePath = "",
    includeHidden = false,
    sortBy: "name" | "size" | "modified" = "name",
    sortOrder: "asc" | "desc" = "asc"
  ): Promise<DirectoryListingResponse> {
    const params = new URLSearchParams({
      folder_id: folderId,
      relative_path: relativePath,
      include_hidden: String(includeHidden),
      sort_by: sortBy,
      sort_order: sortOrder,
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/browse?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to browse directory: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async getItemMetadata(
    folderId: string,
    relativePath: string
  ): Promise<FileItemMetadata> {
    const params = new URLSearchParams({
      folder_id: folderId,
      relative_path: relativePath,
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/metadata?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to get item metadata: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async getFolderSummary(
    folderId: string,
    relativePath = ""
  ): Promise<FolderSummaryResponse> {
    const params = new URLSearchParams({
      folder_id: folderId,
      relative_path: relativePath,
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/summary?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to get folder summary: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async getFilePreviewBlob(
    folderId: string,
    relativePath: string,
    thumbnail = false
  ): Promise<string> {
    const params = new URLSearchParams({
      folder_id: folderId,
      relative_path: relativePath,
      thumbnail: String(thumbnail),
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/preview?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to load preview: HTTP ${response.status}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }

  public static async getFileTextPreview(
    folderId: string,
    relativePath: string,
    maxBytes = 65536
  ): Promise<{
    relative_path: string;
    name: string;
    extension: string;
    size_bytes: number;
    preview_bytes: number;
    lines_count: number;
    truncated: boolean;
    content: string;
  }> {
    const params = new URLSearchParams({
      folder_id: folderId,
      relative_path: relativePath,
      max_bytes: String(maxBytes),
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/preview/text?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to load text preview: HTTP ${response.status}`);
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Transaction Manager Quick Operations
  // ---------------------------------------------------------------------------

  public static async quickCreateFolder(
    folderId: string,
    parentRelativePath: string,
    folderName: string
  ): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/quick/create-folder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        managed_folder_id: folderId,
        parent_relative_path: parentRelativePath,
        folder_name: folderName,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to create folder");
    }
    return response.json();
  }

  public static async quickRename(
    folderId: string,
    sourceRelativePath: string,
    newName: string
  ): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/quick/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        managed_folder_id: folderId,
        source_relative_path: sourceRelativePath,
        new_name: newName,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to rename item");
    }
    return response.json();
  }

  public static async quickMove(
    folderId: string,
    sourceRelativePaths: string[],
    destinationDirectory: string
  ): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/quick/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        managed_folder_id: folderId,
        source_relative_paths: sourceRelativePaths,
        destination_directory_relative_path: destinationDirectory,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to move items");
    }
    return response.json();
  }

  public static async quickCopy(
    folderId: string,
    sourceRelativePaths: string[],
    destinationDirectory: string
  ): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/quick/copy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        managed_folder_id: folderId,
        source_relative_paths: sourceRelativePaths,
        destination_directory_relative_path: destinationDirectory,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to copy items");
    }
    return response.json();
  }

  public static async quickDelete(
    folderId: string,
    relativePaths: string[]
  ): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/quick/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        managed_folder_id: folderId,
        relative_paths: relativePaths,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to delete items");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Storage Analysis
  // ---------------------------------------------------------------------------

  public static async getLatestStorageAnalysis(
    folderId?: string
  ): Promise<StorageAnalysisResult | null> {
    const params = new URLSearchParams();
    if (folderId) {
      params.append("managed_folder_id", folderId);
    }
    const queryString = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/storage/analysis${queryString}`);
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch storage analysis: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async triggerStorageAnalysis(
    request: StorageAnalysisRequest = {}
  ): Promise<StorageAnalysisResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/storage/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to analyze storage: HTTP ${response.status}`);
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Organization Plans
  // ---------------------------------------------------------------------------

  public static async createOrganizationPlan(
    payload: OrganizationPlanRequest
  ): Promise<OrganizationPlanResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/organization/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to generate organization plan: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async getProtectedFolders(
    folderId: string
  ): Promise<import("@/types").ProtectedFoldersListResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/organization/protected-folders/${folderId}`
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load protected folders");
    }
    return response.json();
  }

  public static async detectProtectedFolders(
    folderId: string,
    useAi: boolean = true
  ): Promise<import("@/types").ProtectedFoldersDetectResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/organization/protected-folders/${folderId}/detect?use_ai=${useAi}`,
      { method: "POST" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to auto-detect protected folders");
    }
    return response.json();
  }

  public static async addProtectedFolder(
    folderId: string,
    relativePath: string,
    reason?: string
  ): Promise<import("@/types").ProtectedSubfolderItem> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/organization/protected-folders/${folderId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ relative_path: relativePath, reason }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to flag protected folder");
    }
    return response.json();
  }

  public static async toggleProtectedFolder(
    folderId: string,
    itemId: string,
    isProtected: boolean
  ): Promise<import("@/types").ProtectedSubfolderItem> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/organization/protected-folders/${folderId}/${itemId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_protected: isProtected }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to update protection state");
    }
    return response.json();
  }

  public static async deleteProtectedFolder(
    folderId: string,
    itemId: string
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/organization/protected-folders/${folderId}/${itemId}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to remove protected folder flag");
    }
  }

  // ---------------------------------------------------------------------------
  // Smart Rename Plans
  // ---------------------------------------------------------------------------

  public static async createSmartRenamePlan(
    payload: SmartRenamePlanRequest
  ): Promise<SmartRenamePlanResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/smart-rename/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to generate smart rename plan: HTTP ${response.status}`);
    }
    return response.json();
  }

  public static async analyzeSmartRenameItemOCR(
    planId: string,
    itemId: string
  ): Promise<ItemOCRAnalyzeResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/smart-rename/items/${itemId}/analyze-ocr`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, item_id: itemId }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to analyze item with OCR");
    }
    return response.json();
  }

  public static async startBatchOCRBackground(planId: string): Promise<BatchOCRJobStatus> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/smart-rename/plans/${planId}/batch-ocr`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to start background OCR batch job");
    }
    return response.json();
  }

  public static async getBatchOCRStatus(planId: string): Promise<BatchOCRJobStatus> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/smart-rename/plans/${planId}/batch-ocr/status`,
      {
        method: "GET",
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to get batch OCR status");
    }
    return response.json();
  }

  public static async quickSuggestOCRRename(
    folderId: string,
    relativePath: string
  ): Promise<{
    original_name: string;
    proposed_name: string;
    relative_path: string;
    extracted_text?: string | null;
    category: string;
    success: boolean;
    error_message?: string | null;
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/smart-rename/quick-ocr-suggest`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          folder_id: folderId,
          relative_path: relativePath,
        }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Gagal mendapatkan saran rename OCR + AI");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Change Plan Editing & Workflow
  // ---------------------------------------------------------------------------

  public static async updatePlanItem(
    planId: string,
    itemId: string,
    newDestination: string
  ): Promise<ChangePlanItemResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/transactions/plans/${planId}/items/${itemId}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_destination_relative_path: newDestination }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to update plan item");
    }
    return response.json();
  }

  public static async deletePlanItem(planId: string, itemId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/transactions/plans/${planId}/items/${itemId}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to remove item from plan");
    }
  }

  public static async submitPlan(planId: string): Promise<ChangePlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}/submit`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to submit plan for review");
    }
    return response.json();
  }

  public static async listPlans(
    folderId?: string,
    status?: string
  ): Promise<ChangePlanResponse[]> {
    const params = new URLSearchParams();
    if (folderId) params.append("folder_id", folderId);
    if (status) params.append("status", status);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans${qs}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to list change plans");
    }
    return response.json();
  }

  public static async getPlan(planId: string): Promise<ChangePlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to retrieve change plan");
    }
    return response.json();
  }

  public static async validatePlan(planId: string): Promise<PlanValidationSummary> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}/validate`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Plan validation failed");
    }
    return response.json();
  }

  public static async approvePlan(
    planId: string,
    approvedBy = "user"
  ): Promise<ChangePlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_by: approvedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to approve plan");
    }
    return response.json();
  }

  public static async rejectPlan(
    planId: string,
    reason?: string
  ): Promise<ChangePlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to reject plan");
    }
    return response.json();
  }

  public static async executePlan(planId: string): Promise<ExecutionJobResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/${planId}/execute`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to execute plan");
    }
    return response.json();
  }

  public static async executeApprovedPlans(
    planIds?: string[]
  ): Promise<ExecutionJobResponse[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/execute-approved`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(planIds ? { plan_ids: planIds } : {}),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to execute approved plans");
    }
    return response.json();
  }

  public static async batchApprovePlans(
    planIds: string[],
    approvedBy = "user"
  ): Promise<ChangePlanResponse[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/batch-approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_ids: planIds, approved_by: approvedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to batch approve plans");
    }
    return response.json();
  }

  public static async batchRejectPlans(
    planIds: string[],
    reason?: string
  ): Promise<ChangePlanResponse[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/plans/batch-reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_ids: planIds, reason }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to batch reject plans");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // History & Audit Logs
  // ---------------------------------------------------------------------------

  public static async getAuditLogs(params: Record<string, any> = {}): Promise<AuditLogListResponse> {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== "") {
        qs.append(key, String(val));
      }
    });
    const url = `${this.baseUrl}/api/v1/history/audit-logs${qs.toString() ? `?${qs.toString()}` : ""}`;
    const response = await fetch(url);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to retrieve audit logs");
    }
    return response.json();
  }

  public static async getExecutionHistory(
    params: Record<string, any> = {}
  ): Promise<ExecutionHistoryListResponse> {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== "") {
        qs.append(key, String(val));
      }
    });
    const url = `${this.baseUrl}/api/v1/history/executions${qs.toString() ? `?${qs.toString()}` : ""}`;
    const response = await fetch(url);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to retrieve execution history");
    }
    return response.json();
  }

  public static async getHistoryStats(): Promise<HistorySummaryStats> {
    const response = await fetch(`${this.baseUrl}/api/v1/history/stats`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to retrieve history statistics");
    }
    return response.json();
  }

  public static async exportHistory(
    format: "csv" | "json",
    params: Record<string, any> = {}
  ): Promise<Blob> {
    const qs = new URLSearchParams();
    qs.append("format", format);
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== "") {
        qs.append(key, String(val));
      }
    });
    const response = await fetch(`${this.baseUrl}/api/v1/history/export?${qs.toString()}`);
    if (!response.ok) {
      throw new Error("Failed to export history");
    }
    return response.blob();
  }

  // ---------------------------------------------------------------------------
  // Filesystem Monitoring
  // ---------------------------------------------------------------------------

  public static async getMonitoringStatus(): Promise<{
    status: string;
    active_watchers: number;
    total_monitored: number;
  }> {
    const response = await fetch(`${this.baseUrl}/api/v1/monitoring/status`);
    if (!response.ok) {
      throw new Error("Failed to fetch monitoring service status");
    }
    return response.json();
  }

  public static async listWatchers(): Promise<WatcherItem[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/monitoring/watchers`);
    if (!response.ok) {
      throw new Error("Failed to fetch monitoring watchers");
    }
    return response.json();
  }

  public static async startWatcher(folderId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/watchers/${folderId}/start`,
      { method: "POST" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to start watcher");
    }
  }

  public static async stopWatcher(folderId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/watchers/${folderId}/stop`,
      { method: "POST" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to stop watcher");
    }
  }

  public static async pauseWatcher(folderId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/watchers/${folderId}/pause`,
      { method: "POST" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to pause watcher");
    }
  }

  public static async resumeWatcher(folderId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/watchers/${folderId}/resume`,
      { method: "POST" }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to resume watcher");
    }
  }

  public static async updateWatcherConfig(
    folderId: string,
    payload: MonitoringConfigUpdatePayload
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/watchers/${folderId}/config`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to update watcher configuration");
    }
  }

  public static async getMonitoringEvents(
    params: Record<string, any> = {}
  ): Promise<MonitoringEventListResponse> {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== "") {
        qs.append(key, String(val));
      }
    });
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/events${qs.toString() ? `?${qs.toString()}` : ""}`
    );
    if (!response.ok) {
      throw new Error("Failed to fetch monitoring events");
    }
    return response.json();
  }

  public static async getMonitoringStats(): Promise<MonitoringSummaryStats> {
    const response = await fetch(`${this.baseUrl}/api/v1/monitoring/stats`);
    if (!response.ok) {
      throw new Error("Failed to fetch monitoring summary statistics");
    }
    return response.json();
  }

  public static async getMonitoringActivityChart(
    timeRange = "last_24h"
  ): Promise<ActivityChartResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/monitoring/activity-chart?time_range=${timeRange}`
    );
    if (!response.ok) {
      throw new Error("Failed to fetch activity chart data");
    }
    return response.json();
  }

  public static async getMonitoringDistribution(): Promise<DistributionResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/monitoring/distribution`);
    if (!response.ok) {
      throw new Error("Failed to fetch event distribution");
    }
    return response.json();
  }

  // ==========================================
  // Managed Folders Enhanced API
  // ==========================================
  public static async getManagedFoldersCardsSummary(): Promise<FolderSummaryCards> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/summary`);
    if (!response.ok) {
      throw new Error("Failed to fetch folder summary statistics");
    }
    return response.json();
  }

  public static async enableFolder(folderId: string): Promise<ManagedFolder> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/enable`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Failed to enable folder");
    }
    return response.json();
  }

  public static async disableFolder(folderId: string): Promise<ManagedFolder> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/disable`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Failed to disable folder");
    }
    return response.json();
  }

  public static async getFolderCapabilities(folderId: string): Promise<FolderCapabilities> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/capabilities`);
    if (!response.ok) {
      throw new Error("Failed to fetch folder capabilities");
    }
    return response.json();
  }

  public static async updateFolderCapabilities(
    folderId: string,
    capabilities: FolderCapabilities
  ): Promise<FolderCapabilities> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/capabilities`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(capabilities),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to update capabilities" }));
      throw new Error(err.detail || "Failed to update capabilities");
    }
    return response.json();
  }

  public static async getFolderExclusions(folderId: string): Promise<FolderExclusionItem[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/exclusions`);
    if (!response.ok) {
      throw new Error("Failed to fetch folder exclusions");
    }
    return response.json();
  }

  public static async addFolderExclusion(
    folderId: string,
    payload: { exclusion_type: string; value: string; reason?: string }
  ): Promise<FolderExclusionItem> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/exclusions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to add exclusion" }));
      throw new Error(err.detail || "Failed to add exclusion");
    }
    return response.json();
  }

  public static async deleteFolderExclusion(folderId: string, exclusionId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/folders/${folderId}/exclusions/${exclusionId}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      throw new Error("Failed to delete exclusion");
    }
  }

  public static async getFolderHealth(folderId: string): Promise<FolderHealthCheck> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/health`);
    if (!response.ok) {
      throw new Error("Failed to fetch folder health diagnostics");
    }
    return response.json();
  }

  public static async getFolderUsage(folderId: string): Promise<FolderUsageStats> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/${folderId}/usage`);
    if (!response.ok) {
      throw new Error("Failed to fetch folder usage");
    }
    return response.json();
  }

  public static async registerMultipleFolders(paths: string[]): Promise<ManagedFolder[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/folders/register-multiple`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(paths),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to register folders" }));
      throw new Error(err.detail || "Failed to register folders");
    }
    return response.json();
  }

  // ==========================================
  // Application Settings API
  // ==========================================
  public static async getAllSettings(): Promise<AllSettingsResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings`);
    if (!response.ok) {
      throw new Error("Failed to fetch application settings");
    }
    return response.json();
  }

  public static async getCategorySettings<T = any>(category: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/${category}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch settings for category '${category}'`);
    }
    return response.json();
  }

  public static async updateCategorySettings<T = any>(
    category: string,
    payload: Record<string, any>
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/${category}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to update settings" }));
      throw new Error(err.detail || "Failed to update settings");
    }
    return response.json();
  }

  public static async resetCategorySettings(category: string): Promise<Record<string, any>> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/reset?category=${category}`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to reset settings" }));
      throw new Error(err.detail || "Failed to reset settings");
    }
    return response.json();
  }

  public static async test9RouterConnection(
    endpoint?: string,
    apiKey?: string,
    timeoutSeconds = 10
  ): Promise<TestConnectionResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/ai/9router/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint,
        api_key: apiKey,
        timeout_seconds: timeoutSeconds,
      }),
    });
    if (!response.ok) {
      return { success: false, status: "error", message: `HTTP ${response.status}` };
    }
    return response.json();
  }

  public static async testOpenRouterConnection(
    endpoint?: string,
    apiKey?: string,
    timeoutSeconds = 15
  ): Promise<TestConnectionResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/ai/openrouter/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint,
        api_key: apiKey,
        timeout_seconds: timeoutSeconds,
      }),
    });
    if (!response.ok) {
      return { success: false, status: "error", message: `HTTP ${response.status}` };
    }
    return response.json();
  }

  public static async getAvailableModels(endpoint?: string): Promise<AvailableModelsResponse> {
    const url = endpoint
      ? `${this.baseUrl}/api/v1/router/models?endpoint=${encodeURIComponent(endpoint)}`
      : `${this.baseUrl}/api/v1/router/models`;
    try {
      const response = await fetch(url);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback to settings endpoint
    }
    const fallbackRes = await fetch(`${this.baseUrl}/api/v1/settings/ai/models`);
    if (!fallbackRes.ok) {
      throw new Error("Failed to fetch available AI models");
    }
    return fallbackRes.json();
  }

  public static async getStorageMetrics(): Promise<StorageSettings> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/storage`);
    if (!response.ok) {
      throw new Error("Failed to fetch storage settings");
    }
    return response.json();
  }

  public static async checkDatabaseIntegrity(): Promise<MaintenanceActionResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/database/integrity-check`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Failed to execute database integrity check");
    }
    return response.json();
  }

  public static async compactDatabase(): Promise<MaintenanceActionResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/database/compact`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Failed to compact database");
    }
    return response.json();
  }

  public static async clearCache(cacheTypes?: string[]): Promise<MaintenanceActionResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/cache/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cacheTypes || []),
    });
    if (!response.ok) {
      throw new Error("Failed to clear application cache");
    }
    return response.json();
  }

  // =========================================================================
  // Dashboard Overview
  // =========================================================================

  public static async getDashboardOverview(): Promise<DashboardOverviewResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/dashboard/overview`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load dashboard overview");
    }
    return response.json();
  }

  public static async triggerDashboardAnalyze(
    payload: DashboardAnalyzeRequest
  ): Promise<DashboardJobItemData> {
    const response = await fetch(`${this.baseUrl}/api/v1/dashboard/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to trigger analysis");
    }
    return response.json();
  }

  // =========================================================================
  // Contextual Assistant
  // =========================================================================

  public static async explainAssistant(
    request: AssistantExplainRequest
  ): Promise<AssistantExplainResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/assistant/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to get explanation from assistant");
    }
    return response.json();
  }

  public static async suggestAssistantPlan(
    request: AssistantSuggestPlanRequest
  ): Promise<AssistantSuggestPlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/assistant/suggest-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to propose plan via assistant");
    }
    return response.json();
  }

  public static async getAssistantQuickPrompts(
    targetType: AssistantTargetType
  ): Promise<QuickPromptItem[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/assistant/quick-prompts?target_type=${encodeURIComponent(
        targetType
      )}`
    );
    if (!response.ok) {
      return [];
    }
    return response.json();
  }

  public static async getOCRStatus(): Promise<OCRStatusResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/ocr/status`);
    if (!response.ok) {
      throw new Error("Failed to get OCR status");
    }
    return response.json();
  }

  public static async extractOCR(request: OCRExtractRequest): Promise<OCRExtractResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/ocr/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to extract text using OCR");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Global Cross-Folder Search (FEAT-05)
  // ---------------------------------------------------------------------------

  public static async searchFiles(
    query: string,
    limit = 30
  ): Promise<GlobalSearchResponse> {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
    });
    const response = await fetch(`${this.baseUrl}/api/v1/fs/search?${params.toString()}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to search managed folders");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Storage Cleanup Plan Generator (FEAT-02)
  // ---------------------------------------------------------------------------

  public static async createStorageCleanupPlan(
    payload: StorageCleanupPlanRequest
  ): Promise<StorageCleanupPlanResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/storage/cleanup-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to generate storage cleanup plan");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Execution Undo / Revert (FEAT-03)
  // ---------------------------------------------------------------------------

  public static async undoExecutionJob(jobId: string): Promise<UndoExecutionResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/transactions/jobs/${jobId}/undo`, {
      method: "POST",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to undo execution job");
    }
    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Organization Rules & Rule Execution History (FEAT-04)
  // ---------------------------------------------------------------------------

  public static async listRules(
    managedFolderId?: string
  ): Promise<OrganizationRuleResponse[]> {
    const params = new URLSearchParams();
    if (managedFolderId) {
      params.set("managed_folder_id", managedFolderId);
    }
    const qs = params.toString();
    const response = await fetch(`${this.baseUrl}/api/v1/rules${qs ? `?${qs}` : ""}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load organization rules");
    }
    return response.json();
  }

  public static async createRule(
    payload: OrganizationRuleCreate
  ): Promise<OrganizationRuleResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to create organization rule");
    }
    return response.json();
  }

  public static async approveRule(
    ruleId: string,
    approvedBy = "user"
  ): Promise<OrganizationRuleResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/rules/${ruleId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_by: approvedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to approve organization rule");
    }
    return response.json();
  }

  public static async toggleRule(
    ruleId: string,
    enabled: boolean
  ): Promise<OrganizationRuleResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/rules/${ruleId}/toggle?enabled=${enabled}`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to toggle organization rule");
    }
    return response.json();
  }

  public static async deleteRule(ruleId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/rules/${ruleId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to delete organization rule");
    }
  }

  public static async listRuleExecutions(
    ruleId?: string,
    limit = 50
  ): Promise<RuleExecutionResponse[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (ruleId) {
      params.set("rule_id", ruleId);
    }
    const response = await fetch(
      `${this.baseUrl}/api/v1/rules/executions/list?${params.toString()}`
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load rule executions");
    }
    return response.json();
  }

  public static async getUpdateStatus(): Promise<AppUpdateStatusResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/update/status`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to check update & installer status");
    }
    return response.json();
  }

  public static async applyInstallerUpdate(
    installerPath?: string
  ): Promise<ApplyUpdateResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/settings/update/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(installerPath ? { installer_path: installerPath } : {}),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to launch installer package");
    }
    return response.json();
  }
}
