import type {
  ApiAuditEvent,
  ApiAuthPayload,
  ApiDetail,
  ApiKeyCreatePayload,
  ApiKeyPayload,
  ApiPolicyPayload,
  ApiRepositoryPayload,
  ApiSummary,
  ApiUserPayload,
  AuditExportFormat,
  DiffSubmitFormState,
  PolicyConfigPayload,
} from "./types";

export const DEFAULT_API_BASE_URL = import.meta.env.VITE_AGENTREVIEW_API_URL ?? "http://127.0.0.1:8000";

type ApiClientOptions = {
  baseUrl: string;
  apiKey: string;
};

type CreateRepositoryPayload = {
  provider: string;
  owner: string;
  name: string;
  default_branch?: string;
  visibility?: string;
};

type CreateUserPayload = {
  email: string;
  name?: string;
  role: "admin" | "reviewer";
};

type CreatePolicyPayload = {
  name: string;
  config: PolicyConfigPayload;
  enabled: boolean;
  scope: "organization" | "repository";
  repository_id?: string;
};

type UpdatePolicyPayload = {
  name?: string;
  config?: PolicyConfigPayload;
  enabled?: boolean;
};

export class ApiClientError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

export function createApiClient(options: ApiClientOptions) {
  return new ApiClient(options);
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor({ baseUrl, apiKey }: ApiClientOptions) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  getMe() {
    return this.request<ApiAuthPayload>("/api/auth/me");
  }

  listAnalysisRuns() {
    return this.request<ApiSummary[]>("/api/analysis-runs");
  }

  getAnalysisRun(id: string) {
    return this.request<ApiDetail>(`/api/analysis-runs/${id}`);
  }

  listAuditEvents(limit = 50) {
    return this.request<ApiAuditEvent[]>(`/api/audit-events?limit=${limit}`);
  }

  listApiKeys() {
    return this.request<ApiKeyPayload[]>("/api/api-keys");
  }

  createApiKey(name: string, role: string) {
    return this.request<ApiKeyCreatePayload>("/api/api-keys", {
      method: "POST",
      body: JSON.stringify({ name, role }),
    });
  }

  updateApiKeyRole(apiKeyId: string, role: string) {
    return this.request<ApiKeyPayload>(`/api/api-keys/${apiKeyId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  }

  revokeApiKey(apiKeyId: string) {
    return this.request<ApiKeyPayload>(`/api/api-keys/${apiKeyId}/revoke`, {
      method: "POST",
    });
  }

  listUsers() {
    return this.request<ApiUserPayload[]>("/api/users");
  }

  createUser(payload: CreateUserPayload) {
    return this.request<ApiUserPayload>("/api/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  updateUserRole(userId: string, role: "admin" | "reviewer") {
    return this.request<ApiUserPayload>(`/api/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  }

  deleteUser(userId: string) {
    return this.request<void>(`/api/users/${userId}`, {
      method: "DELETE",
    });
  }

  listRepositories() {
    return this.request<ApiRepositoryPayload[]>("/api/repositories");
  }

  createRepository(payload: CreateRepositoryPayload) {
    return this.request<ApiRepositoryPayload>("/api/repositories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  deleteRepository(repositoryId: string) {
    return this.request<void>(`/api/repositories/${repositoryId}`, {
      method: "DELETE",
    });
  }

  createRepositoryMembership(repositoryId: string, userId: string, role: string) {
    return this.request<ApiRepositoryPayload>(`/api/repositories/${repositoryId}/memberships`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, role }),
    });
  }

  removeRepositoryMembership(repositoryId: string, userId: string) {
    return this.request<ApiRepositoryPayload>(`/api/repositories/${repositoryId}/memberships/${userId}`, {
      method: "DELETE",
    });
  }

  updateRepositoryMembershipRole(repositoryId: string, userId: string, role: string) {
    return this.request<ApiRepositoryPayload>(`/api/repositories/${repositoryId}/memberships/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  }

  listPolicies() {
    return this.request<ApiPolicyPayload[]>("/api/policies");
  }

  createPolicy(payload: CreatePolicyPayload) {
    return this.request<ApiPolicyPayload>("/api/policies", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  updatePolicy(policyId: string, payload: UpdatePolicyPayload) {
    return this.request<ApiPolicyPayload>(`/api/policies/${policyId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  submitDiff(form: DiffSubmitFormState) {
    return this.request<ApiDetail>("/api/analyze/diff", {
      method: "POST",
      body: JSON.stringify({
        diff: form.diff,
        repository: form.repository || null,
        pull_request_number: form.pullRequestNumber ? Number(form.pullRequestNumber) : null,
        title: form.title || null,
        author: form.author || null,
        agent_name: form.agentName || null,
        branch: form.branch || null,
      }),
      timeoutMs: 10000,
    });
  }

  async exportAuditEvents(actionFilter: string, format: AuditExportFormat) {
    const response = await this.rawRequest(buildAuditExportPath(actionFilter, format));
    return response.blob();
  }

  private async request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}) {
    const response = await this.rawRequest(path, init);
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch (error) {
      throw new ApiClientError("API returned invalid JSON", response.status);
    }
  }

  private async rawRequest(path: string, init: RequestInit & { timeoutMs?: number } = {}) {
    const { timeoutMs = 5000, ...requestInit } = init;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    const headers = new Headers(requestInit.headers);
    headers.set("Authorization", `Bearer ${this.apiKey}`);
    if (requestInit.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...requestInit,
        headers,
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new ApiClientError(`API returned ${response.status}`, response.status);
      }
      return response;
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error;
      }
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiClientError("API request timed out");
      }
      throw new ApiClientError(error instanceof Error ? error.message : "API request failed");
    } finally {
      window.clearTimeout(timeout);
    }
  }
}

export function buildAuditExportFilename(actionFilter: string, format: AuditExportFormat) {
  return `agentreview-audit-${fileSafeSegment(actionFilter)}.${format}`;
}

function buildAuditExportPath(actionFilter: string, format: AuditExportFormat) {
  const params = new URLSearchParams({ format });
  if (actionFilter !== "all") {
    params.set("action", actionFilter);
  }
  return `/api/audit-events/export?${params.toString()}`;
}

function fileSafeSegment(value: string) {
  return value === "all" ? "all" : value.replace(/[^a-z0-9._-]+/gi, "-").toLowerCase();
}
