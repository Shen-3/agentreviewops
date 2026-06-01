import React from "react";
import ReactDOM from "react-dom/client";
import { ClipboardCopy, Download, KeyRound, LogOut, RefreshCcw, Search, ShieldCheck } from "lucide-react";

import "./styles.css";

type RiskLevel = "low" | "medium" | "high" | "block";
type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";
type LoadMode = "loading" | "ready" | "empty" | "error";
type DataSource = "api" | "demo";
type AuditExportFormat = "json" | "csv";
type AuditMetadata = Record<string, unknown>;
type RuleId = "require_tests_for_code_changes" | "flag_dependency_changes" | "flag_ci_changes" | "flag_auth_changes" | "flag_large_generated_files";

type Finding = {
  severity: FindingSeverity;
  rule: string;
  file: string;
  reason: string;
};

type ChangedFile = {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  critical: boolean;
  test: boolean;
};

type Analysis = {
  id: string;
  repo: string;
  prLabel: string;
  title: string;
  author: string;
  agent: string;
  branch: string;
  createdAt: string;
  riskLevel: RiskLevel;
  riskScore: number;
  changedFileCount: number;
  findingCount: number;
  changedFiles: ChangedFile[];
  findings: Finding[];
  report: string;
};

type AuditEvent = {
  id: string;
  createdAt: string;
  action: string;
  actor: string;
  target: string;
  summary: string;
  metadata: AuditMetadata;
};

type ApiKeyRecord = {
  id: string;
  name: string;
  role: "admin" | "ci" | "read_only";
  keyPrefix: string;
  createdAt: string;
  revokedAt: string | null;
  isCurrent: boolean;
};

type UserRecord = {
  id: string;
  email: string;
  name: string;
  role: string;
  createdAt: string;
};

type RepositoryRecord = {
  id: string;
  provider: string;
  owner: string;
  name: string;
  fullName: string;
  defaultBranch: string;
  visibility: string;
  reviewers: RepositoryReviewer[];
  createdAt: string;
};

type RepositoryReviewer = {
  userId: string;
  email: string;
  name: string | null;
  role: string;
};

type CreatedApiKey = {
  name: string;
  value: string;
};

type ApiKeyRole = "admin" | "ci" | "read_only";

type RulesConfigPayload = Record<RuleId, boolean>;

type PolicyConfigPayload = {
  version: 1;
  risk: {
    fail_level: RiskLevel;
    large_diff: {
      max_files: number;
      max_lines: number;
    };
  };
  critical_paths: string[];
  test_patterns: string[];
  rules: RulesConfigPayload;
};

type PolicyRecord = {
  id: string;
  name: string;
  scope: string;
  repositoryId: string | null;
  repositoryFullName: string | null;
  enabled: boolean;
  config: PolicyConfigPayload;
  createdAt: string;
  updatedAt: string;
};

type PolicyFormState = {
  name: string;
  enabled: boolean;
  scope: "organization" | "repository";
  repositoryId: string;
  failLevel: RiskLevel;
  maxFiles: string;
  maxLines: string;
  criticalPathsText: string;
  testPatternsText: string;
  rules: RulesConfigPayload;
};

type DiffSubmitFormState = {
  diff: string;
  repository: string;
  pullRequestNumber: string;
  title: string;
  author: string;
  agentName: string;
  branch: string;
};

type RepositoryFormState = {
  provider: string;
  owner: string;
  name: string;
  defaultBranch: string;
  visibility: string;
};

type UserFormState = {
  email: string;
  name: string;
  role: "admin" | "reviewer";
};

type MembershipFormState = {
  repositoryId: string;
  userId: string;
  role: "owner" | "maintainer" | "reviewer";
};

type ApiSummary = {
  analysis_run_id: string;
  created_at: string;
  source: string;
  repository: string | null;
  pull_request_number: number | null;
  title: string | null;
  author: string | null;
  agent_name: string | null;
  branch: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  summary: string;
  changed_file_count: number;
  finding_count: number;
};

type ApiDetail = {
  analysis_run_id: string;
  created_at: string;
  risk_score: number;
  risk_level: RiskLevel;
  findings: Array<{
    severity: FindingSeverity;
    rule_id: string;
    file_path: string | null;
    description: string;
  }>;
  changed_files: Array<{
    path: string;
    status: string;
    additions: number;
    deletions: number;
    is_critical_file: boolean;
    is_test_file: boolean;
  }>;
  markdown: string;
};

type ApiAuditEvent = {
  audit_event_id: string;
  created_at: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata: AuditMetadata;
};

type ApiKeyPayload = {
  api_key_id: string;
  name: string;
  role: ApiKeyRole;
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
  is_current: boolean;
};

type ApiUserPayload = {
  user_id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
};

type ApiRepositoryPayload = {
  repository_id: string;
  provider: string;
  owner: string;
  name: string;
  full_name: string;
  default_branch: string | null;
  visibility: string | null;
  reviewers: Array<{
    user_id: string;
    email: string;
    name: string | null;
    role: string;
  }>;
  created_at: string;
};

type ApiKeyCreatePayload = ApiKeyPayload & {
  api_key: string;
};

type ApiPolicyPayload = {
  policy_id: string;
  name: string;
  scope: string;
  repository_id: string | null;
  repository_full_name: string | null;
  enabled: boolean;
  config: PolicyConfigPayload;
  created_at: string;
  updated_at: string;
};

const API_BASE_URL = import.meta.env.VITE_AGENTREVIEW_API_URL || "http://127.0.0.1:8000";
const API_KEY_STORAGE_KEY = "agentreviewops.apiKey";
const ruleLabels: Record<RuleId, string> = {
  require_tests_for_code_changes: "Require tests for code changes",
  flag_dependency_changes: "Flag dependency changes",
  flag_ci_changes: "Flag CI changes",
  flag_auth_changes: "Flag auth changes",
  flag_large_generated_files: "Flag generated files",
};
const defaultPolicyConfig: PolicyConfigPayload = {
  version: 1,
  risk: {
    fail_level: "high",
    large_diff: {
      max_files: 20,
      max_lines: 800,
    },
  },
  critical_paths: [
    "auth/**",
    "security/**",
    "payments/**",
    "infra/**",
    ".github/workflows/**",
    "Dockerfile",
    "docker-compose.yml",
    "package.json",
    "pyproject.toml",
    "requirements*.txt",
  ],
  test_patterns: ["tests/**", "**/*test*", "**/*spec*"],
  rules: {
    require_tests_for_code_changes: true,
    flag_dependency_changes: true,
    flag_ci_changes: true,
    flag_auth_changes: true,
    flag_large_generated_files: true,
  },
};

const seededAnalyses: Analysis[] = [
  {
    id: "run_8fb2",
    repo: "platform/checkout-api",
    prLabel: "#1842",
    title: "Tighten inactive-user session handling",
    author: "codex-agent",
    agent: "Codex",
    branch: "codex/auth-session-hardening",
    createdAt: "05/23/2026, 11:34",
    riskLevel: "high",
    riskScore: 55,
    changedFileCount: 1,
    findingCount: 3,
    changedFiles: [{ path: "auth/session.py", status: "modified", additions: 3, deletions: 1, critical: true, test: false }],
    findings: [
      { severity: "high", rule: "critical-path-change", file: "auth/session.py", reason: "Configured critical path changed." },
      { severity: "high", rule: "sensitive-area-change", file: "auth/session.py", reason: "Auth behavior changed and needs owner review." },
      { severity: "medium", rule: "missing-tests", file: "Change set", reason: "Production code changed without tests." },
    ],
    report: `# AgentReviewOps Report

Risk: HIGH (55/100)

## Summary

1 file changed with 4 positive risk findings. Review auth/session.py before merge.

## Human Review Checklist

- [ ] Verify critical-path changes are intentional and scoped.
- [ ] Review auth behavior with a human owner.
- [ ] Require tests for changed behavior or document why tests are not needed.`,
  },
  {
    id: "run_79ac",
    repo: "growth/web-console",
    prLabel: "#921",
    title: "Update pricing copy and docs",
    author: "cursor-agent",
    agent: "Cursor",
    branch: "cursor/pricing-copy",
    createdAt: "05/23/2026, 10:18",
    riskLevel: "low",
    riskScore: 0,
    changedFileCount: 1,
    findingCount: 1,
    changedFiles: [{ path: "docs/pricing.md", status: "modified", additions: 12, deletions: 4, critical: false, test: false }],
    findings: [{ severity: "info", rule: "docs-updated", file: "docs/pricing.md", reason: "Documentation changed with no source risk findings." }],
    report: `# AgentReviewOps Report

Risk: LOW (0/100)

## Summary

Documentation-only change. Confirm copy matches the product offer.`,
  },
  {
    id: "run_42dd",
    repo: "infra/deployments",
    prLabel: "#311",
    title: "Rotate worker image and CI release path",
    author: "devin",
    agent: "Devin",
    branch: "devin/release-worker-update",
    createdAt: "05/22/2026, 17:46",
    riskLevel: "block",
    riskScore: 78,
    changedFileCount: 2,
    findingCount: 3,
    changedFiles: [
      { path: ".github/workflows/release.yml", status: "modified", additions: 18, deletions: 6, critical: true, test: false },
      { path: "deploy/docker-compose.yml", status: "modified", additions: 9, deletions: 2, critical: true, test: false },
    ],
    findings: [
      { severity: "high", rule: "critical-path-change", file: ".github/workflows/release.yml", reason: "Release automation changed." },
      { severity: "medium", rule: "ci-change", file: ".github/workflows/release.yml", reason: "CI/CD workflow changed." },
      { severity: "medium", rule: "missing-tests", file: "Change set", reason: "Infrastructure change has no validation fixture." },
    ],
    report: `# AgentReviewOps Report

Risk: BLOCK (78/100)

## Summary

Release infrastructure changed. Require platform owner review before merge.

## Human Review Checklist

- [ ] Confirm CI/CD changes do not weaken release controls.
- [ ] Verify deployment image and rollback path.`,
  },
];

const seededAuditEvents: AuditEvent[] = [
  {
    id: "audit_analysis_8fb2",
    createdAt: "05/23/2026, 11:35",
    action: "analysis.created",
    actor: "api key local-ci",
    target: "analysis run run_8fb2",
    summary: "platform/checkout-api #1842 analyzed at high risk.",
    metadata: {
      repository: "platform/checkout-api",
      pull_request_number: 1842,
      agent_name: "Codex",
      risk_level: "high",
      risk_score: 55,
      changed_file_count: 1,
      finding_count: 3,
    },
  },
  {
    id: "audit_policy_default",
    createdAt: "05/23/2026, 10:42",
    action: "policy.created",
    actor: "api key platform-admin",
    target: "policy default-review-policy",
    summary: "Default review policy saved for organization scope.",
    metadata: {
      policy_name: "Default review policy",
      enabled: true,
      scope: "organization",
    },
  },
  {
    id: "audit_key_local_ci",
    createdAt: "05/23/2026, 10:39",
    action: "api_key.created",
    actor: "system",
    target: "api key local-ci",
    summary: "Bootstrap key created for CI and dashboard access.",
    metadata: {
      api_key_name: "Local CI",
      source: "bootstrap",
    },
  },
  {
    id: "audit_org_bootstrap",
    createdAt: "05/23/2026, 10:38",
    action: "organization.bootstrapped",
    actor: "system",
    target: "organization acme",
    summary: "Self-hosted organization bootstrapped.",
    metadata: {
      source: "bootstrap",
    },
  },
];

const seededApiKeys: ApiKeyRecord[] = [
  {
    id: "key_local_ci",
    name: "Local CI",
    role: "admin",
    keyPrefix: "arok_demo_ci",
    createdAt: "05/23/2026, 10:39",
    revokedAt: null,
    isCurrent: true,
  },
  {
    id: "key_dashboard_operator",
    name: "Dashboard operator",
    role: "admin",
    keyPrefix: "arok_demo_ui",
    createdAt: "05/23/2026, 10:42",
    revokedAt: null,
    isCurrent: false,
  },
  {
    id: "key_retired",
    name: "Retired bootstrap key",
    role: "read_only",
    keyPrefix: "arok_demo_old",
    createdAt: "05/22/2026, 18:12",
    revokedAt: "05/23/2026, 09:05",
    isCurrent: false,
  },
];

const seededUsers: UserRecord[] = [
  {
    id: "user_reviewer",
    email: "reviewer@example.com",
    name: "Reviewer",
    role: "admin",
    createdAt: "05/23/2026, 10:38",
  },
];

const seededRepositories: RepositoryRecord[] = [
  {
    id: "repo_checkout_api",
    provider: "github",
    owner: "platform",
    name: "checkout-api",
    fullName: "platform/checkout-api",
    defaultBranch: "main",
    visibility: "private",
    reviewers: [{ userId: "user_reviewer", email: "reviewer@example.com", name: "Reviewer", role: "maintainer" }],
    createdAt: "05/23/2026, 10:38",
  },
  {
    id: "repo_web_console",
    provider: "github",
    owner: "growth",
    name: "web-console",
    fullName: "growth/web-console",
    defaultBranch: "main",
    visibility: "private",
    reviewers: [],
    createdAt: "05/23/2026, 10:41",
  },
];

const seededPolicies: PolicyRecord[] = [
  {
    id: "policy_default",
    name: "Default review policy",
    scope: "organization",
    repositoryId: null,
    repositoryFullName: null,
    enabled: true,
    config: defaultPolicyConfig,
    createdAt: "05/23/2026, 10:42",
    updatedAt: "05/23/2026, 10:42",
  },
];

const emptyDiffSubmitForm: DiffSubmitFormState = {
  diff: "",
  repository: "",
  pullRequestNumber: "",
  title: "",
  author: "",
  agentName: "",
  branch: "",
};

const emptyRepositoryForm: RepositoryFormState = {
  provider: "github",
  owner: "",
  name: "",
  defaultBranch: "main",
  visibility: "private",
};

const emptyUserForm: UserFormState = {
  email: "",
  name: "",
  role: "reviewer",
};

const emptyMembershipForm: MembershipFormState = {
  repositoryId: "",
  userId: "",
  role: "reviewer",
};

function Dashboard() {
  const [analyses, setAnalyses] = React.useState<Analysis[]>([]);
  const [auditEvents, setAuditEvents] = React.useState<AuditEvent[]>([]);
  const [apiKeys, setApiKeys] = React.useState<ApiKeyRecord[]>([]);
  const [users, setUsers] = React.useState<UserRecord[]>([]);
  const [repositories, setRepositories] = React.useState<RepositoryRecord[]>([]);
  const [policies, setPolicies] = React.useState<PolicyRecord[]>([]);
  const [policyForm, setPolicyForm] = React.useState<PolicyFormState>(() => policyToForm(seededPolicies[0]));
  const [policyStatus, setPolicyStatus] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<LoadMode>("loading");
  const [dataSource, setDataSource] = React.useState<DataSource>("api");
  const [riskFilter, setRiskFilter] = React.useState<RiskLevel | "all">("all");
  const [auditActionFilter, setAuditActionFilter] = React.useState("all");
  const [query, setQuery] = React.useState("");
  const [apiKey, setApiKey] = React.useState(() => window.localStorage.getItem(API_KEY_STORAGE_KEY) || "");
  const [apiKeyInput, setApiKeyInput] = React.useState("");
  const [newApiKeyName, setNewApiKeyName] = React.useState("");
  const [newApiKeyRole, setNewApiKeyRole] = React.useState<ApiKeyRole>("admin");
  const [createdApiKey, setCreatedApiKey] = React.useState<CreatedApiKey | null>(null);
  const [diffForm, setDiffForm] = React.useState<DiffSubmitFormState>(emptyDiffSubmitForm);
  const [diffSubmitStatus, setDiffSubmitStatus] = React.useState("");
  const [isSubmittingDiff, setIsSubmittingDiff] = React.useState(false);
  const [repositoryForm, setRepositoryForm] = React.useState<RepositoryFormState>(emptyRepositoryForm);
  const [repositoryStatus, setRepositoryStatus] = React.useState("");
  const [userForm, setUserForm] = React.useState<UserFormState>(emptyUserForm);
  const [userStatus, setUserStatus] = React.useState("");
  const [membershipForm, setMembershipForm] = React.useState<MembershipFormState>(emptyMembershipForm);
  const [membershipStatus, setMembershipStatus] = React.useState("");

  const loadWorkspaceData = React.useCallback(async () => {
    setMode("loading");
    if (!apiKey) {
      setAnalyses(seededAnalyses);
      setAuditEvents(seededAuditEvents);
      setApiKeys(seededApiKeys);
      setUsers(seededUsers);
      setRepositories(seededRepositories);
      setPolicies(seededPolicies);
      setPolicyForm(policyToForm(seededPolicies[0]));
      setCreatedApiKey(null);
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
      return;
    }
    try {
      const [analysisResponse, auditResponse, apiKeysResponse, usersResponse, repositoriesResponse, policiesResponse] = await Promise.all([
        fetchWithTimeout(`${API_BASE_URL}/api/analysis-runs`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/audit-events?limit=50`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/api-keys`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/users`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/repositories`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/policies`, apiKey),
      ]);
      const summaries = (await analysisResponse.json()) as ApiSummary[];
      const auditPayload = (await auditResponse.json()) as ApiAuditEvent[];
      const apiKeyPayload = (await apiKeysResponse.json()) as ApiKeyPayload[];
      const userPayload = (await usersResponse.json()) as ApiUserPayload[];
      const repositoryPayload = (await repositoriesResponse.json()) as ApiRepositoryPayload[];
      const policyPayload = (await policiesResponse.json()) as ApiPolicyPayload[];
      const normalized = summaries.map(normalizeSummary);
      const normalizedAudit = auditPayload.map(normalizeAuditEvent);
      const normalizedApiKeys = apiKeyPayload.map(normalizeApiKey);
      const normalizedUsers = userPayload.map(normalizeUser);
      const normalizedRepositories = repositoryPayload.map(normalizeRepository);
      const normalizedPolicies = policyPayload.map(normalizePolicy);
      setAnalyses(normalized);
      setAuditEvents(normalizedAudit);
      setApiKeys(normalizedApiKeys);
      setUsers(normalizedUsers);
      setRepositories(normalizedRepositories);
      setPolicies(normalizedPolicies);
      setPolicyForm(policyToForm(normalizedPolicies[0] ?? seededPolicies[0]));
      setDataSource("api");
      setMode(normalized.length || normalizedAudit.length || normalizedApiKeys.length || normalizedUsers.length || normalizedRepositories.length || normalizedPolicies.length ? "ready" : "empty");
      setSelectedId(normalized[0]?.id ?? null);
      if (normalized[0]) {
        void loadAnalysisDetail(normalized[0].id, apiKey, setAnalyses, setMode);
      }
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setAnalyses([]);
      setAuditEvents([]);
      setApiKeys([]);
      setUsers([]);
      setRepositories([]);
      setPolicies([]);
      setCreatedApiKey(null);
      setSelectedId(null);
      setDataSource("api");
      setMode("error");
    }
  }, [apiKey]);

  React.useEffect(() => {
    void loadWorkspaceData();
  }, [loadWorkspaceData]);

  const filteredAnalyses = React.useMemo(() => {
    if (mode === "empty") {
      return [];
    }
    const normalizedQuery = query.toLowerCase();
    return analyses.filter((analysis) => {
      const matchesRisk = riskFilter === "all" || analysis.riskLevel === riskFilter;
      const searchable = `${analysis.repo} ${analysis.branch} ${analysis.author} ${analysis.title}`.toLowerCase();
      return matchesRisk && searchable.includes(normalizedQuery);
    });
  }, [analyses, mode, query, riskFilter]);

  const selected = filteredAnalyses.find((analysis) => analysis.id === selectedId) ?? filteredAnalyses[0] ?? null;
  const highCount = filteredAnalyses.filter((analysis) => ["high", "block"].includes(analysis.riskLevel)).length;
  const findingCount = filteredAnalyses.reduce((total, analysis) => total + analysis.findingCount, 0);
  const auditActionOptions = React.useMemo(() => ["all", ...Array.from(new Set(auditEvents.map((event) => event.action))).sort()], [auditEvents]);
  const filteredAuditEvents = React.useMemo(() => {
    if (mode === "empty") {
      return [];
    }
    return auditEvents.filter((event) => auditActionFilter === "all" || event.action === auditActionFilter);
  }, [auditActionFilter, auditEvents, mode]);
  const activeApiKeyCount = apiKeys.filter((record) => record.revokedAt === null).length;

  const banner = getBanner(mode, dataSource);
  const saveApiKey = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = apiKeyInput.trim();
    if (!normalized) {
      return;
    }
    window.localStorage.setItem(API_KEY_STORAGE_KEY, normalized);
    setApiKey(normalized);
    setApiKeyInput("");
  };
  const signOut = () => {
    window.localStorage.removeItem(API_KEY_STORAGE_KEY);
    setApiKey("");
    setAnalyses(seededAnalyses);
    setAuditEvents(seededAuditEvents);
    setApiKeys(seededApiKeys);
    setUsers(seededUsers);
    setRepositories(seededRepositories);
    setPolicies(seededPolicies);
    setPolicyForm(policyToForm(seededPolicies[0]));
    setPolicyStatus("");
    setUserStatus("");
    setMembershipStatus("");
    setNewApiKeyRole("admin");
    setCreatedApiKey(null);
    setSelectedId(seededAnalyses[0].id);
    setDataSource("demo");
    setMode("ready");
  };
  const createDashboardApiKey = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedName = newApiKeyName.trim();
    if (!apiKey || !normalizedName) {
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/api-keys`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: normalizedName, role: newApiKeyRole }),
      });
      const payload = (await response.json()) as ApiKeyCreatePayload;
      const record = normalizeApiKey(payload);
      setApiKeys((current) => [record, ...current]);
      setCreatedApiKey({ name: record.name, value: payload.api_key });
      setNewApiKeyName("");
      setNewApiKeyRole("admin");
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setMode("error");
    }
  };
  const createDashboardRepository = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!repositoryForm.owner.trim() || !repositoryForm.name.trim()) {
      setRepositoryStatus("Owner and name are required.");
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/repositories`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(compactPayload({
          provider: repositoryForm.provider.trim() || "github",
          owner: repositoryForm.owner.trim(),
          name: repositoryForm.name.trim(),
          default_branch: repositoryForm.defaultBranch.trim() || null,
          visibility: repositoryForm.visibility.trim() || null,
        })),
      });
      const repository = normalizeRepository((await response.json()) as ApiRepositoryPayload);
      setRepositories((current) => [repository, ...current.filter((record) => record.id !== repository.id)]);
      setRepositoryForm(emptyRepositoryForm);
      setRepositoryStatus(`${repository.fullName} onboarded.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setRepositoryStatus(error instanceof Error && error.message.includes("409") ? "Repository already exists." : "Repository could not be created.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const createDashboardUser = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!userForm.email.trim()) {
      setUserStatus("User email is required.");
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/users`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(compactPayload({
          email: userForm.email.trim(),
          name: userForm.name.trim() || null,
          role: userForm.role,
        })),
      });
      const user = normalizeUser((await response.json()) as ApiUserPayload);
      setUsers((current) => [user, ...current.filter((record) => record.id !== user.id)]);
      setUserForm(emptyUserForm);
      setUserStatus(`${user.email} added.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setUserStatus(error instanceof Error && error.message.includes("409") ? "User already exists." : "User could not be created.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const assignDashboardMembership = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!membershipForm.repositoryId || !membershipForm.userId) {
      setMembershipStatus("Choose a repository and user.");
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/repositories/${membershipForm.repositoryId}/memberships`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: membershipForm.userId,
          role: membershipForm.role,
        }),
      });
      const repository = normalizeRepository((await response.json()) as ApiRepositoryPayload);
      setRepositories((current) => current.map((record) => (record.id === repository.id ? repository : record)));
      setMembershipForm(emptyMembershipForm);
      setMembershipStatus(`${repository.fullName} routing updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setMembershipStatus(error instanceof Error && error.message.includes("409") ? "User is already assigned to that repository." : "Review routing could not be updated.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const removeDashboardMembership = async (repositoryId: string, userId: string) => {
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/repositories/${repositoryId}/memberships/${userId}`, apiKey, {
        method: "DELETE",
      });
      const repository = normalizeRepository((await response.json()) as ApiRepositoryPayload);
      setRepositories((current) => current.map((record) => (record.id === repository.id ? repository : record)));
      setMembershipStatus(`${repository.fullName} routing updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setMembershipStatus("Review routing could not be removed.");
      setMode("error");
    }
  };
  const deleteDashboardUser = async (userId: string) => {
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      await fetchWithTimeout(`${API_BASE_URL}/api/users/${userId}`, apiKey, {
        method: "DELETE",
      });
      setUsers((current) => current.filter((record) => record.id !== userId));
      setUserStatus("User removed.");
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setUserStatus(error instanceof Error && error.message.includes("400") ? "Cannot remove the last admin." : "User could not be removed.");
      if (!(error instanceof Error) || !error.message.includes("400")) {
        setMode("error");
      }
    }
  };
  const revokeDashboardApiKey = async (apiKeyId: string) => {
    if (!apiKey) {
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/api-keys/${apiKeyId}/revoke`, apiKey, {
        method: "POST",
      });
      const revoked = normalizeApiKey((await response.json()) as ApiKeyPayload);
      setApiKeys((current) => current.map((record) => (record.id === revoked.id ? revoked : record)));
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setMode("error");
    }
  };
  const saveDashboardPolicy = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey || dataSource !== "api") {
      return;
    }
    const config = policyConfigFromForm(policyForm);
    if (!policyForm.name.trim()) {
      setPolicyStatus("Policy name is required.");
      return;
    }
    if (!config) {
      setPolicyStatus("Large diff thresholds must be positive whole numbers.");
      return;
    }
    if (policyForm.scope === "repository" && !policyForm.repositoryId) {
      setPolicyStatus("Choose a repository for repository-scoped policies.");
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/policies`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: policyForm.name.trim(),
          enabled: policyForm.enabled,
          scope: policyForm.scope,
          repository_id: policyForm.scope === "repository" ? policyForm.repositoryId : null,
          config,
        }),
      });
      const saved = normalizePolicy((await response.json()) as ApiPolicyPayload);
      setPolicies((current) => [saved, ...current]);
      setPolicyForm(policyToForm(saved));
      setPolicyStatus(
        saved.scope === "repository"
          ? `Policy saved for ${saved.repositoryFullName}.`
          : "Policy saved. New analyses will use the latest enabled policy.",
      );
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setPolicyStatus("Policy could not be saved.");
      setMode("error");
    }
  };
  const exportAuditEvents = async (format: AuditExportFormat) => {
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const response = await fetchWithTimeout(buildAuditExportUrl(auditActionFilter, format), apiKey);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = buildAuditExportFilename(auditActionFilter, format);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setMode("error");
    }
  };
  const submitDashboardDiff = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey || dataSource !== "api") {
      return;
    }
    const diff = diffForm.diff.trim();
    if (!diff) {
      setDiffSubmitStatus("Diff is required.");
      return;
    }
    const pullRequestNumber = parseOptionalPositiveInteger(diffForm.pullRequestNumber);
    if (pullRequestNumber === null) {
      setDiffSubmitStatus("Pull request number must be a positive whole number.");
      return;
    }

    setIsSubmittingDiff(true);
    try {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/analyze/diff`,
        apiKey,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(compactPayload({
            diff,
            repository: diffForm.repository.trim() || null,
            pull_request_number: pullRequestNumber,
            title: diffForm.title.trim() || null,
            author: diffForm.author.trim() || null,
            agent_name: diffForm.agentName.trim() || null,
            branch: diffForm.branch.trim() || null,
          })),
        },
        15000,
      );
      const detail = (await response.json()) as ApiDetail;
      const submitted = normalizeSubmittedAnalysis(detail, diffForm);
      setAnalyses((current) => [submitted, ...current.filter((analysis) => analysis.id !== submitted.id)]);
      setSelectedId(submitted.id);
      setDataSource("api");
      setMode("ready");
      setDiffForm(emptyDiffSubmitForm);
      setDiffSubmitStatus(`Analysis ${shortId(submitted.id)} created.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setDiffSubmitStatus("Analysis could not be created.");
      setMode("error");
    } finally {
      setIsSubmittingDiff(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <div>
            <strong>AgentReviewOps</strong>
            <span>Review control plane</span>
          </div>
        </div>
        <nav>
          <a className="nav-link active" href="#analyses">
            Analyses
          </a>
          <a className="nav-link" href="#repositories">
            Repositories
          </a>
          <a className="nav-link" href="#users">
            Users
          </a>
          <a className="nav-link" href="#policies">
            Policies
          </a>
          <a className="nav-link" href="#keys">
            API keys
          </a>
          <a className="nav-link" href="#audit">
            Audit
          </a>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-heading">
            <p className="eyebrow">Read-only dashboard</p>
            <h1>AI pull request review queue</h1>
          </div>
          <div className="topbar-actions">
            <form className="api-key-form" onSubmit={saveApiKey}>
              <label htmlFor="api-key-input">API key</label>
              <input
                id="api-key-input"
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
                type="password"
                placeholder={apiKey ? "Key saved" : "Paste API key"}
                autoComplete="off"
              />
              <button type="submit">
                <KeyRound size={16} />
                Sign in
              </button>
              {apiKey ? (
                <button type="button" onClick={signOut} aria-label="Sign out">
                  <LogOut size={16} />
                </button>
              ) : null}
            </form>
            <button className="primary" type="button" onClick={() => void loadWorkspaceData()}>
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </header>

        {banner ? (
          <section className="state-banner" aria-live="polite">
            {banner}
          </section>
        ) : null}

        <section className="metrics" aria-label="Analysis metrics">
          <Metric label="Total analyses" value={filteredAnalyses.length} />
          <Metric label="High or block" value={highCount} />
          <Metric label="Open findings" value={findingCount} />
          <Metric label="Active keys" value={activeApiKeyCount} />
        </section>

        <DiffSubmitPanel
          form={diffForm}
          mode={mode}
          dataSource={dataSource}
          status={diffSubmitStatus}
          isSubmitting={isSubmittingDiff}
          onFormChange={setDiffForm}
          onSubmit={submitDashboardDiff}
        />

        <section className="content-grid">
          <section className="analysis-list" aria-labelledby="analysis-list-title">
            <div className="section-head">
              <div>
                <h2 id="analysis-list-title">Analysis runs</h2>
                <p>Filter risk and inspect the runs that need human review.</p>
              </div>
              <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value as RiskLevel | "all")} aria-label="Filter by risk level">
                <option value="all">All risk</option>
                <option value="block">Block</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <label className="search">
              <span>Search</span>
              <span className="search-box">
                <Search size={16} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder="Repository, branch, or author" />
              </span>
            </label>
            <div className="analysis-rows" role="list">
              <AnalysisRows
                analyses={filteredAnalyses}
                mode={mode}
                selectedId={selected?.id ?? null}
                onSelect={(id) => {
                  setSelectedId(id);
                  if (dataSource === "api") {
                    void loadAnalysisDetail(id, apiKey, setAnalyses, setMode);
                  }
                }}
              />
            </div>
          </section>

          <AnalysisDetail selected={selected} />
        </section>

        <RepositoryAdmin
          repositories={repositories}
          users={users}
          mode={mode}
          dataSource={dataSource}
          form={repositoryForm}
          status={repositoryStatus}
          membershipForm={membershipForm}
          membershipStatus={membershipStatus}
          onFormChange={setRepositoryForm}
          onCreate={createDashboardRepository}
          onMembershipFormChange={setMembershipForm}
          onAssignMembership={assignDashboardMembership}
          onRemoveMembership={(repositoryId, userId) => void removeDashboardMembership(repositoryId, userId)}
        />

        <UserAdmin
          users={users}
          mode={mode}
          dataSource={dataSource}
          form={userForm}
          status={userStatus}
          onFormChange={setUserForm}
          onCreate={createDashboardUser}
          onDelete={(userId) => void deleteDashboardUser(userId)}
        />

        <PolicyEditor
          policies={policies}
          repositories={repositories}
          form={policyForm}
          mode={mode}
          dataSource={dataSource}
          status={policyStatus}
          onFormChange={setPolicyForm}
          onSave={saveDashboardPolicy}
        />

        <ApiKeyAdmin
          apiKeys={apiKeys}
          mode={mode}
          dataSource={dataSource}
          newApiKeyName={newApiKeyName}
          newApiKeyRole={newApiKeyRole}
          createdApiKey={createdApiKey}
          onNameChange={setNewApiKeyName}
          onRoleChange={setNewApiKeyRole}
          onCreate={createDashboardApiKey}
          onDismissCreated={() => setCreatedApiKey(null)}
          onRevoke={(apiKeyId) => void revokeDashboardApiKey(apiKeyId)}
        />

        <AuditHistory
          events={filteredAuditEvents}
          mode={mode}
          dataSource={dataSource}
          actionFilter={auditActionFilter}
          actionOptions={auditActionOptions}
          onActionFilterChange={setAuditActionFilter}
          onExport={(format) => void exportAuditEvents(format)}
        />
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DiffSubmitPanel({
  form,
  mode,
  dataSource,
  status,
  isSubmitting,
  onFormChange,
  onSubmit,
}: {
  form: DiffSubmitFormState;
  mode: LoadMode;
  dataSource: DataSource;
  status: string;
  isSubmitting: boolean;
  onFormChange: React.Dispatch<React.SetStateAction<DiffSubmitFormState>>;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  return (
    <section className="diff-submit-panel" id="submit-diff" aria-labelledby="diff-submit-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Analyze</p>
          <h2 id="diff-submit-title">Submit diff</h2>
        </div>
        {status ? <span className="policy-status">{status}</span> : null}
      </div>
      <form className="diff-submit-form" onSubmit={onSubmit}>
        <div className="diff-submit-grid">
          <label>
            <span>Repository</span>
            <input
              value={form.repository}
              onChange={(event) => onFormChange((current) => ({ ...current, repository: event.target.value }))}
              disabled={!liveData || isSubmitting}
              placeholder="owner/name"
            />
          </label>
          <label>
            <span>PR</span>
            <input
              value={form.pullRequestNumber}
              onChange={(event) => onFormChange((current) => ({ ...current, pullRequestNumber: event.target.value }))}
              disabled={!liveData || isSubmitting}
              inputMode="numeric"
            />
          </label>
          <label>
            <span>Title</span>
            <input
              value={form.title}
              onChange={(event) => onFormChange((current) => ({ ...current, title: event.target.value }))}
              disabled={!liveData || isSubmitting}
            />
          </label>
          <label>
            <span>Branch</span>
            <input
              value={form.branch}
              onChange={(event) => onFormChange((current) => ({ ...current, branch: event.target.value }))}
              disabled={!liveData || isSubmitting}
            />
          </label>
          <label>
            <span>Author</span>
            <input
              value={form.author}
              onChange={(event) => onFormChange((current) => ({ ...current, author: event.target.value }))}
              disabled={!liveData || isSubmitting}
            />
          </label>
          <label>
            <span>Agent</span>
            <input
              value={form.agentName}
              onChange={(event) => onFormChange((current) => ({ ...current, agentName: event.target.value }))}
              disabled={!liveData || isSubmitting}
            />
          </label>
        </div>
        <label className="diff-input">
          <span>Unified diff</span>
          <textarea
            value={form.diff}
            onChange={(event) => onFormChange((current) => ({ ...current, diff: event.target.value }))}
            disabled={!liveData || isSubmitting}
            rows={9}
            placeholder="diff --git a/file b/file"
          />
        </label>
        <div className="policy-actions">
          <button className="primary" type="submit" disabled={!liveData || isSubmitting}>
            <ShieldCheck size={16} />
            {isSubmitting ? "Analyzing" : "Analyze diff"}
          </button>
        </div>
      </form>
    </section>
  );
}

function AnalysisRows({
  analyses,
  mode,
  selectedId,
  onSelect,
}: {
  analyses: Analysis[];
  mode: LoadMode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (mode === "loading") {
    return <EmptyState message="Loading runs..." />;
  }
  if (mode === "error") {
    return <EmptyState message="Analysis data could not be loaded." />;
  }
  if (!analyses.length) {
    return <EmptyState message="No analysis runs to display." />;
  }
  return (
    <>
      {analyses.map((analysis) => (
        <button key={analysis.id} type="button" className={`analysis-row ${analysis.id === selectedId ? "active" : ""}`} onClick={() => onSelect(analysis.id)}>
          <div className="row-top">
            <div className="row-title">
              {analysis.repo} <span>{analysis.prLabel}</span>
            </div>
            <RiskBadge level={analysis.riskLevel} label={analysis.riskLevel.toUpperCase()} />
          </div>
          <p>{analysis.title}</p>
          <div className="row-meta">
            <span>
              {analysis.agent} by {analysis.author}
            </span>
            <span>{analysis.createdAt}</span>
          </div>
        </button>
      ))}
    </>
  );
}

function AnalysisDetail({ selected }: { selected: Analysis | null }) {
  if (!selected) {
    return (
      <section className="analysis-detail" aria-labelledby="analysis-detail-title">
        <DetailHeader level="low" label="NONE" />
        <DetailGrid repository="-" pullRequest="-" agent="-" files={0} />
        <FindingsTable findings={[]} emptyText="No analysis selected." />
        <ReportPreview report="No report available." />
      </section>
    );
  }
  return (
    <section className="analysis-detail" aria-labelledby="analysis-detail-title">
      <DetailHeader level={selected.riskLevel} label={`${selected.riskLevel.toUpperCase()} ${selected.riskScore}`} />
      <DetailGrid repository={selected.repo} pullRequest={`${selected.prLabel} ${selected.title}`} agent={selected.agent} files={selected.changedFileCount} />
      <FindingsTable findings={selected.findings} emptyText="No findings loaded for this analysis." />
      <ReportPreview report={selected.report || "Report detail is loading."} />
    </section>
  );
}

function DetailHeader({ level, label }: { level: RiskLevel; label: string }) {
  return (
    <div className="section-head detail-head">
      <div>
        <p className="eyebrow">Selected run</p>
        <h2 id="analysis-detail-title">Analysis detail</h2>
      </div>
      <RiskBadge level={level} label={label} />
    </div>
  );
}

function DetailGrid({ repository, pullRequest, agent, files }: { repository: string; pullRequest: string; agent: string; files: number }) {
  return (
    <dl className="detail-grid">
      <div>
        <dt>Repository</dt>
        <dd>{repository}</dd>
      </div>
      <div>
        <dt>Pull request</dt>
        <dd>{pullRequest}</dd>
      </div>
      <div>
        <dt>Agent</dt>
        <dd>{agent}</dd>
      </div>
      <div>
        <dt>Changed files</dt>
        <dd>{files}</dd>
      </div>
    </dl>
  );
}

function FindingsTable({ findings, emptyText }: { findings: Finding[]; emptyText: string }) {
  return (
    <section className="findings-section">
      <h3>Findings</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Rule</th>
              <th>File</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {findings.length ? (
              findings.map((finding) => (
                <tr key={`${finding.rule}-${finding.file}-${finding.reason}`}>
                  <td>
                    <span className={`severity ${finding.severity}`}>{finding.severity.toUpperCase()}</span>
                  </td>
                  <td>{finding.rule}</td>
                  <td>{finding.file}</td>
                  <td>{finding.reason}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4}>{emptyText}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReportPreview({ report }: { report: string }) {
  return (
    <section className="report-section">
      <div className="section-head">
        <div>
          <h3>Report preview</h3>
          <p>Markdown generated for the human reviewer packet.</p>
        </div>
        <button type="button" onClick={() => void navigator.clipboard.writeText(report)}>
          <ClipboardCopy size={16} />
          Copy
        </button>
      </div>
      <pre tabIndex={0}>{report}</pre>
    </section>
  );
}

function RepositoryAdmin({
  repositories,
  users,
  mode,
  dataSource,
  form,
  status,
  membershipForm,
  membershipStatus,
  onFormChange,
  onCreate,
  onMembershipFormChange,
  onAssignMembership,
  onRemoveMembership,
}: {
  repositories: RepositoryRecord[];
  users: UserRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  form: RepositoryFormState;
  status: string;
  membershipForm: MembershipFormState;
  membershipStatus: string;
  onFormChange: React.Dispatch<React.SetStateAction<RepositoryFormState>>;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onMembershipFormChange: React.Dispatch<React.SetStateAction<MembershipFormState>>;
  onAssignMembership: (event: React.FormEvent<HTMLFormElement>) => void;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  return (
    <section className="repository-panel" id="repositories" aria-labelledby="repository-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Repository scope</p>
          <h2 id="repository-admin-title">Repositories</h2>
          <p>{repositories.length} onboarded</p>
        </div>
        <form className="repository-create-form" onSubmit={onCreate}>
          <label>
            <span>Provider</span>
            <input
              value={form.provider}
              onChange={(event) => onFormChange((current) => ({ ...current, provider: event.target.value }))}
              disabled={!liveData}
            />
          </label>
          <label>
            <span>Owner</span>
            <input
              value={form.owner}
              onChange={(event) => onFormChange((current) => ({ ...current, owner: event.target.value }))}
              disabled={!liveData}
              placeholder="platform"
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!liveData}
              placeholder="checkout-api"
            />
          </label>
          <label>
            <span>Default branch</span>
            <input
              value={form.defaultBranch}
              onChange={(event) => onFormChange((current) => ({ ...current, defaultBranch: event.target.value }))}
              disabled={!liveData}
            />
          </label>
          <label>
            <span>Visibility</span>
            <select value={form.visibility} onChange={(event) => onFormChange((current) => ({ ...current, visibility: event.target.value }))} disabled={!liveData}>
              <option value="private">Private</option>
              <option value="public">Public</option>
              <option value="">Unspecified</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={!liveData || !form.owner.trim() || !form.name.trim()}>
            <ShieldCheck size={16} />
            Add
          </button>
        </form>
      </div>
      {status ? <span className="policy-status">{status}</span> : null}
      <form className="repository-routing-form" onSubmit={onAssignMembership}>
        <label>
          <span>Route repository</span>
          <select
            value={membershipForm.repositoryId}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, repositoryId: event.target.value }))}
            disabled={!liveData || !repositories.length}
          >
            <option value="">Choose repository</option>
            {repositories.map((repository) => (
              <option value={repository.id} key={repository.id}>
                {repository.fullName}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Reviewer</span>
          <select
            value={membershipForm.userId}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, userId: event.target.value }))}
            disabled={!liveData || !users.length}
          >
            <option value="">Choose user</option>
            {users.map((user) => (
              <option value={user.id} key={user.id}>
                {user.name || user.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Repository role</span>
          <select
            value={membershipForm.role}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, role: event.target.value as "owner" | "maintainer" | "reviewer" }))}
            disabled={!liveData}
          >
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="reviewer">Reviewer</option>
          </select>
        </label>
        <button className="primary" type="submit" disabled={!liveData || !membershipForm.repositoryId || !membershipForm.userId}>
          <ShieldCheck size={16} />
          Assign
        </button>
        {membershipStatus ? <span className="policy-status">{membershipStatus}</span> : null}
      </form>
      <div className="table-wrap repository-table-wrap">
        <table className="repository-table">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Provider</th>
              <th>Default branch</th>
              <th>Visibility</th>
              <th>Review routing</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <RepositoryRows repositories={repositories} mode={mode} liveData={liveData} onRemoveMembership={onRemoveMembership} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RepositoryRows({
  repositories,
  mode,
  liveData,
  onRemoveMembership,
}: {
  repositories: RepositoryRecord[];
  mode: LoadMode;
  liveData: boolean;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
}) {
  if (mode === "loading") {
    return <RepositoryEmptyRow message="Loading repositories..." />;
  }
  if (mode === "error") {
    return <RepositoryEmptyRow message="Repositories could not be loaded." />;
  }
  if (!repositories.length) {
    return <RepositoryEmptyRow message="No repositories onboarded." />;
  }
  return (
    <>
      {repositories.map((repository) => (
        <tr key={repository.id}>
          <td>{repository.fullName}</td>
          <td>{repository.provider}</td>
          <td>{repository.defaultBranch || "-"}</td>
          <td>{repository.visibility || "-"}</td>
          <td>
            <ReviewersCell repository={repository} liveData={liveData} onRemoveMembership={onRemoveMembership} />
          </td>
          <td>{repository.createdAt}</td>
        </tr>
      ))}
    </>
  );
}

function ReviewersCell({
  repository,
  liveData,
  onRemoveMembership,
}: {
  repository: RepositoryRecord;
  liveData: boolean;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
}) {
  if (!repository.reviewers.length) {
    return <>No reviewers assigned</>;
  }
  return (
    <div className="reviewer-list">
      {repository.reviewers.map((reviewer) => (
        <span className="reviewer-pill" key={reviewer.userId}>
          {reviewer.name || reviewer.email} ({reviewer.role})
          <button type="button" disabled={!liveData} onClick={() => onRemoveMembership(repository.id, reviewer.userId)} aria-label={`Remove ${reviewer.name || reviewer.email} from ${repository.fullName}`}>
            Remove
          </button>
        </span>
      ))}
    </div>
  );
}

function RepositoryEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6}>{message}</td>
    </tr>
  );
}

function UserAdmin({
  users,
  mode,
  dataSource,
  form,
  status,
  onFormChange,
  onCreate,
  onDelete,
}: {
  users: UserRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  form: UserFormState;
  status: string;
  onFormChange: React.Dispatch<React.SetStateAction<UserFormState>>;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onDelete: (userId: string) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  return (
    <section className="user-panel" id="users" aria-labelledby="user-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Access</p>
          <h2 id="user-admin-title">Users</h2>
          <p>{users.length} organization user(s)</p>
        </div>
        <form className="user-create-form" onSubmit={onCreate}>
          <label>
            <span>Email</span>
            <input
              value={form.email}
              onChange={(event) => onFormChange((current) => ({ ...current, email: event.target.value }))}
              disabled={!liveData}
              placeholder="reviewer@example.com"
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!liveData}
              placeholder="Reviewer"
            />
          </label>
          <label>
            <span>Org role</span>
            <select value={form.role} onChange={(event) => onFormChange((current) => ({ ...current, role: event.target.value as "admin" | "reviewer" }))} disabled={!liveData}>
              <option value="admin">Admin</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={!liveData || !form.email.trim()}>
            <ShieldCheck size={16} />
            Add user
          </button>
        </form>
      </div>
      {status ? <span className="policy-status">{status}</span> : null}
      <div className="table-wrap user-table-wrap">
        <table className="user-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <UserRows users={users} mode={mode} liveData={liveData} onDelete={onDelete} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function UserRows({
  users,
  mode,
  liveData,
  onDelete,
}: {
  users: UserRecord[];
  mode: LoadMode;
  liveData: boolean;
  onDelete: (userId: string) => void;
}) {
  if (mode === "loading") {
    return <UserEmptyRow message="Loading users..." />;
  }
  if (mode === "error") {
    return <UserEmptyRow message="Users could not be loaded." />;
  }
  if (!users.length) {
    return <UserEmptyRow message="No users created." />;
  }
  return (
    <>
      {users.map((user) => (
        <tr key={user.id}>
          <td>
            <strong>{user.name || user.email}</strong>
            <span className="table-subtext">{user.email}</span>
          </td>
          <td>{user.role}</td>
          <td>{user.createdAt}</td>
          <td>
            <button type="button" disabled={!liveData} onClick={() => onDelete(user.id)}>
              <LogOut size={16} />
              Remove
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}

function UserEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={4}>{message}</td>
    </tr>
  );
}

function PolicyEditor({
  policies,
  repositories,
  form,
  mode,
  dataSource,
  status,
  onFormChange,
  onSave,
}: {
  policies: PolicyRecord[];
  repositories: RepositoryRecord[];
  form: PolicyFormState;
  mode: LoadMode;
  dataSource: DataSource;
  status: string;
  onFormChange: React.Dispatch<React.SetStateAction<PolicyFormState>>;
  onSave: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const activePolicy = policies.find((policy) => policy.enabled) ?? policies[0] ?? null;
  const repositoryOptions = repositories.map((repository) => ({ id: repository.id, label: repository.fullName }));
  const updateRule = (rule: RuleId, enabled: boolean) => {
    onFormChange((current) => ({
      ...current,
      rules: {
        ...current.rules,
        [rule]: enabled,
      },
    }));
  };

  return (
    <section className="policy-panel" id="policies" aria-labelledby="policy-editor-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Policy control</p>
          <h2 id="policy-editor-title">Policy editor</h2>
          <p>Save a new organization policy version for future analyses.</p>
        </div>
        {activePolicy ? (
          <div className="policy-meta" aria-label="Current active policy">
            <span className={`status-badge ${activePolicy.enabled ? "active" : "revoked"}`}>{activePolicy.enabled ? "Active" : "Disabled"}</span>
            <strong>{activePolicy.name}</strong>
            <span>{policyScopeLabel(activePolicy)}</span>
            <span>{activePolicy.updatedAt}</span>
          </div>
        ) : null}
      </div>

      <form className="policy-form" onSubmit={onSave}>
        <div className="policy-grid">
          <label>
            <span>Policy name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!liveData}
              placeholder="Default review policy"
            />
          </label>
          <label>
            <span>Scope</span>
            <select
              value={form.scope}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  scope: event.target.value as "organization" | "repository",
                  repositoryId: event.target.value === "repository" ? current.repositoryId || repositoryOptions[0]?.id || "" : "",
                }))
              }
              disabled={!liveData}
            >
              <option value="organization">Organization</option>
              <option value="repository">Repository</option>
            </select>
          </label>
          <label>
            <span>Repository</span>
            <select
              value={form.repositoryId}
              onChange={(event) => onFormChange((current) => ({ ...current, repositoryId: event.target.value }))}
              disabled={!liveData || form.scope !== "repository" || !repositoryOptions.length}
            >
              <option value="">Choose repository</option>
              {repositoryOptions.map((repository) => (
                <option value={repository.id} key={repository.id}>
                  {repository.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Fail level</span>
            <select value={form.failLevel} onChange={(event) => onFormChange((current) => ({ ...current, failLevel: event.target.value as RiskLevel }))} disabled={!liveData}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="block">Block</option>
            </select>
          </label>
          <label>
            <span>Large diff files</span>
            <input
              value={form.maxFiles}
              onChange={(event) => onFormChange((current) => ({ ...current, maxFiles: event.target.value }))}
              disabled={!liveData}
              inputMode="numeric"
            />
          </label>
          <label>
            <span>Large diff lines</span>
            <input
              value={form.maxLines}
              onChange={(event) => onFormChange((current) => ({ ...current, maxLines: event.target.value }))}
              disabled={!liveData}
              inputMode="numeric"
            />
          </label>
        </div>

        <div className="policy-textareas">
          <label>
            <span>Critical paths</span>
            <textarea
              value={form.criticalPathsText}
              onChange={(event) => onFormChange((current) => ({ ...current, criticalPathsText: event.target.value }))}
              disabled={!liveData}
              rows={7}
            />
          </label>
          <label>
            <span>Test patterns</span>
            <textarea
              value={form.testPatternsText}
              onChange={(event) => onFormChange((current) => ({ ...current, testPatternsText: event.target.value }))}
              disabled={!liveData}
              rows={7}
            />
          </label>
        </div>

        <fieldset className="rule-grid">
          <legend>Rules</legend>
          {(Object.keys(ruleLabels) as RuleId[]).map((rule) => (
            <label className="checkbox-row" key={rule}>
              <input type="checkbox" checked={form.rules[rule]} onChange={(event) => updateRule(rule, event.target.checked)} disabled={!liveData} />
              <span>{ruleLabels[rule]}</span>
            </label>
          ))}
        </fieldset>

        <div className="policy-actions">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => onFormChange((current) => ({ ...current, enabled: event.target.checked }))}
              disabled={!liveData}
            />
            <span>Save as enabled</span>
          </label>
          {status ? <span className="policy-status">{status}</span> : null}
          <button className="primary" type="submit" disabled={!liveData || mode === "loading" || (form.scope === "repository" && !form.repositoryId)}>
            <ShieldCheck size={16} />
            Save policy
          </button>
        </div>
      </form>
    </section>
  );
}

function ApiKeyAdmin({
  apiKeys,
  mode,
  dataSource,
  newApiKeyName,
  newApiKeyRole,
  createdApiKey,
  onNameChange,
  onRoleChange,
  onCreate,
  onDismissCreated,
  onRevoke,
}: {
  apiKeys: ApiKeyRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  newApiKeyName: string;
  newApiKeyRole: ApiKeyRole;
  createdApiKey: CreatedApiKey | null;
  onNameChange: (value: string) => void;
  onRoleChange: (value: ApiKeyRole) => void;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onDismissCreated: () => void;
  onRevoke: (apiKeyId: string) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  return (
    <section className="api-key-panel" id="keys" aria-labelledby="api-key-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Access control</p>
          <h2 id="api-key-admin-title">API keys</h2>
          <p>Create one-time keys for CI, dashboards, and automation.</p>
        </div>
        <form className="inline-create-form" onSubmit={onCreate}>
          <label htmlFor="new-api-key-name">New key name</label>
          <input
            id="new-api-key-name"
            value={newApiKeyName}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="Release bot"
            disabled={!liveData}
          />
          <select aria-label="New key role" value={newApiKeyRole} onChange={(event) => onRoleChange(event.target.value as ApiKeyRole)} disabled={!liveData}>
            <option value="admin">Admin</option>
            <option value="ci">CI</option>
            <option value="read_only">Read only</option>
          </select>
          <button className="primary" type="submit" disabled={!liveData || !newApiKeyName.trim()}>
            <KeyRound size={16} />
            Create
          </button>
        </form>
      </div>

      {createdApiKey ? (
        <div className="one-time-key" role="status">
          <div>
            <strong>{createdApiKey.name}</strong>
            <span>{createdApiKey.value}</span>
          </div>
          <button type="button" onClick={() => void navigator.clipboard.writeText(createdApiKey.value)}>
            <ClipboardCopy size={16} />
            Copy
          </button>
          <button type="button" onClick={onDismissCreated}>
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="table-wrap">
        <table className="api-key-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Prefix</th>
              <th>Created</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <ApiKeyRows apiKeys={apiKeys} mode={mode} liveData={liveData} onRevoke={onRevoke} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ApiKeyRows({
  apiKeys,
  mode,
  liveData,
  onRevoke,
}: {
  apiKeys: ApiKeyRecord[];
  mode: LoadMode;
  liveData: boolean;
  onRevoke: (apiKeyId: string) => void;
}) {
  if (mode === "loading") {
    return <ApiKeyEmptyRow message="Loading API keys..." />;
  }
  if (mode === "error") {
    return <ApiKeyEmptyRow message="API keys could not be loaded." />;
  }
  if (!apiKeys.length) {
    return <ApiKeyEmptyRow message="No API keys to display." />;
  }
  return (
    <>
      {apiKeys.map((record) => {
        const revoked = record.revokedAt !== null;
        return (
          <tr key={record.id}>
            <td>
              {record.name}
              {record.isCurrent ? <span className="current-key-label">Current</span> : null}
            </td>
            <td>{formatApiKeyRole(record.role)}</td>
            <td>{record.keyPrefix}</td>
            <td>{record.createdAt}</td>
            <td>
              <span className={`status-badge ${revoked ? "revoked" : "active"}`}>{revoked ? "Revoked" : "Active"}</span>
            </td>
            <td>
              <button type="button" disabled={!liveData || revoked || record.isCurrent} onClick={() => onRevoke(record.id)}>
                <LogOut size={16} />
                Revoke
              </button>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function ApiKeyEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6}>{message}</td>
    </tr>
  );
}

function AuditHistory({
  events,
  mode,
  dataSource,
  actionFilter,
  actionOptions,
  onActionFilterChange,
  onExport,
}: {
  events: AuditEvent[];
  mode: LoadMode;
  dataSource: DataSource;
  actionFilter: string;
  actionOptions: string[];
  onActionFilterChange: (value: string) => void;
  onExport: (format: AuditExportFormat) => void;
}) {
  const exportDisabled = dataSource !== "api" || mode !== "ready";
  return (
    <section className="audit-panel" id="audit" aria-labelledby="audit-history-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Organization audit</p>
          <h2 id="audit-history-title">Audit history</h2>
          <p>Latest governance events from analysis, policy, API key, and bootstrap flows.</p>
        </div>
        <div className="audit-toolbar">
          <select value={actionFilter} onChange={(event) => onActionFilterChange(event.target.value)} aria-label="Filter audit events by action">
            {actionOptions.map((action) => (
              <option key={action} value={action}>
                {action === "all" ? "All actions" : action}
              </option>
            ))}
          </select>
          <button type="button" disabled={exportDisabled} onClick={() => onExport("json")}>
            <Download size={16} />
            JSON
          </button>
          <button type="button" disabled={exportDisabled} onClick={() => onExport("csv")}>
            <Download size={16} />
            CSV
          </button>
        </div>
      </div>
      <div className="table-wrap audit-table-wrap">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Target</th>
              <th>Summary</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            <AuditRows events={events} mode={mode} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AuditRows({ events, mode }: { events: AuditEvent[]; mode: LoadMode }) {
  if (mode === "loading") {
    return <AuditEmptyRow message="Loading audit events..." />;
  }
  if (mode === "error") {
    return <AuditEmptyRow message="Audit events could not be loaded." />;
  }
  if (!events.length) {
    return <AuditEmptyRow message="No audit events to display." />;
  }
  return (
    <>
      {events.map((event) => (
        <tr key={event.id}>
          <td>{event.createdAt}</td>
          <td>
            <span className="action-badge">{event.action}</span>
          </td>
          <td>{event.actor}</td>
          <td>{event.target}</td>
          <td>{event.summary}</td>
          <td>
            <MetadataPreview metadata={event.metadata} />
          </td>
        </tr>
      ))}
    </>
  );
}

function AuditEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6}>{message}</td>
    </tr>
  );
}

function MetadataPreview({ metadata }: { metadata: AuditMetadata }) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined);
  if (!entries.length) {
    return <span className="metadata-muted">No metadata</span>;
  }
  return (
    <div className="metadata-list">
      {entries.slice(0, 5).map(([key, value]) => (
        <span className="metadata-pill" key={key}>
          {key}: {formatMetadataValue(value)}
        </span>
      ))}
      {entries.length > 5 ? <span className="metadata-muted">+{entries.length - 5} more</span> : null}
    </div>
  );
}

function RiskBadge({ level, label }: { level: RiskLevel; label: string }) {
  return <span className={`risk-badge risk-${level}`}>{label}</span>;
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

async function loadAnalysisDetail(
  id: string,
  apiKey: string,
  setAnalyses: React.Dispatch<React.SetStateAction<Analysis[]>>,
  setMode: React.Dispatch<React.SetStateAction<LoadMode>>,
) {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/analysis-runs/${id}`, apiKey);
    const detail = normalizeDetail((await response.json()) as ApiDetail);
    setAnalyses((current) => current.map((analysis) => (analysis.id === id ? { ...analysis, ...detail } : analysis)));
  } catch {
    setMode("error");
  }
}

async function fetchWithTimeout(url: string, apiKey: string, init: RequestInit = {}, timeoutMs = 5000) {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${apiKey}`);

  const response = await fetch(url, {
    ...init,
    headers,
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response;
}

function isAuthError(error: unknown) {
  return error instanceof Error && error.message.includes("401");
}

function buildAuditExportUrl(actionFilter: string, format: AuditExportFormat) {
  const params = new URLSearchParams({
    format,
    limit: "500",
  });
  if (actionFilter !== "all") {
    params.set("action", actionFilter);
  }
  return `${API_BASE_URL}/api/audit-events/export?${params.toString()}`;
}

function buildAuditExportFilename(actionFilter: string, format: AuditExportFormat) {
  return `agentreview-audit-${fileSafeSegment(actionFilter)}.${format}`;
}

function fileSafeSegment(value: string) {
  return value.replace(/[^a-z0-9._-]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase() || "all";
}

function normalizeSummary(summary: ApiSummary): Analysis {
  return {
    id: summary.analysis_run_id,
    repo: summary.repository || "local/diff-analysis",
    prLabel: summary.pull_request_number ? `#${summary.pull_request_number}` : summary.source,
    title: summary.title || summary.summary,
    author: summary.author || "system",
    agent: summary.agent_name || "Unknown",
    branch: summary.branch || "unknown",
    createdAt: formatDate(summary.created_at),
    riskLevel: summary.risk_level,
    riskScore: summary.risk_score,
    changedFileCount: summary.changed_file_count,
    findingCount: summary.finding_count,
    changedFiles: [],
    findings: [],
    report: "",
  };
}

function normalizeDetail(detail: ApiDetail): Partial<Analysis> {
  return {
    changedFileCount: detail.changed_files.length,
    findingCount: detail.findings.length,
    changedFiles: detail.changed_files.map((file) => ({
      path: file.path,
      status: file.status,
      additions: file.additions,
      deletions: file.deletions,
      critical: file.is_critical_file,
      test: file.is_test_file,
    })),
    findings: detail.findings.map((finding) => ({
      severity: finding.severity,
      rule: finding.rule_id,
      file: finding.file_path || "Change set",
      reason: finding.description,
    })),
    report: detail.markdown,
  };
}

function normalizeSubmittedAnalysis(detail: ApiDetail, form: DiffSubmitFormState): Analysis {
  const partial = normalizeDetail(detail);
  return {
    id: detail.analysis_run_id,
    repo: form.repository.trim() || "local/diff-analysis",
    prLabel: form.pullRequestNumber.trim() ? `#${form.pullRequestNumber.trim()}` : "api",
    title: form.title.trim() || `${detail.changed_files.length} file(s) analyzed`,
    author: form.author.trim() || "dashboard",
    agent: form.agentName.trim() || "Unknown",
    branch: form.branch.trim() || "manual",
    createdAt: formatDate(detail.created_at),
    riskLevel: detail.risk_level,
    riskScore: detail.risk_score,
    changedFileCount: partial.changedFileCount ?? detail.changed_files.length,
    findingCount: partial.findingCount ?? detail.findings.length,
    changedFiles: partial.changedFiles ?? [],
    findings: partial.findings ?? [],
    report: partial.report ?? detail.markdown,
  };
}

function normalizeAuditEvent(event: ApiAuditEvent): AuditEvent {
  return {
    id: event.audit_event_id,
    createdAt: formatDate(event.created_at),
    action: event.action,
    actor: formatActor(event.actor_type, event.actor_id),
    target: formatTarget(event.target_type, event.target_id),
    summary: summarizeAuditEvent(event.action, event.metadata),
    metadata: event.metadata,
  };
}

function normalizeApiKey(payload: ApiKeyPayload): ApiKeyRecord {
  return {
    id: payload.api_key_id,
    name: payload.name,
    role: payload.role,
    keyPrefix: payload.key_prefix,
    createdAt: formatDate(payload.created_at),
    revokedAt: payload.revoked_at ? formatDate(payload.revoked_at) : null,
    isCurrent: payload.is_current,
  };
}

function normalizeUser(payload: ApiUserPayload): UserRecord {
  return {
    id: payload.user_id,
    email: payload.email,
    name: payload.name || "",
    role: payload.role,
    createdAt: formatDate(payload.created_at),
  };
}

function normalizeRepository(payload: ApiRepositoryPayload): RepositoryRecord {
  return {
    id: payload.repository_id,
    provider: payload.provider,
    owner: payload.owner,
    name: payload.name,
    fullName: payload.full_name,
    defaultBranch: payload.default_branch || "",
    visibility: payload.visibility || "",
    reviewers: payload.reviewers.map((reviewer) => ({
      userId: reviewer.user_id,
      email: reviewer.email,
      name: reviewer.name,
      role: reviewer.role,
    })),
    createdAt: formatDate(payload.created_at),
  };
}

function normalizePolicy(payload: ApiPolicyPayload): PolicyRecord {
  return {
    id: payload.policy_id,
    name: payload.name,
    scope: payload.scope,
    repositoryId: payload.repository_id,
    repositoryFullName: payload.repository_full_name,
    enabled: payload.enabled,
    config: normalizePolicyConfig(payload.config),
    createdAt: formatDate(payload.created_at),
    updatedAt: formatDate(payload.updated_at),
  };
}

function normalizePolicyConfig(config: PolicyConfigPayload): PolicyConfigPayload {
  return {
    version: 1,
    risk: {
      fail_level: config.risk?.fail_level ?? defaultPolicyConfig.risk.fail_level,
      large_diff: {
        max_files: config.risk?.large_diff?.max_files ?? defaultPolicyConfig.risk.large_diff.max_files,
        max_lines: config.risk?.large_diff?.max_lines ?? defaultPolicyConfig.risk.large_diff.max_lines,
      },
    },
    critical_paths: config.critical_paths ?? defaultPolicyConfig.critical_paths,
    test_patterns: config.test_patterns ?? defaultPolicyConfig.test_patterns,
    rules: {
      ...defaultPolicyConfig.rules,
      ...config.rules,
    },
  };
}

function policyToForm(policy: PolicyRecord): PolicyFormState {
  return {
    name: policy.name,
    enabled: policy.enabled,
    scope: policy.scope === "repository" ? "repository" : "organization",
    repositoryId: policy.repositoryId ?? "",
    failLevel: policy.config.risk.fail_level,
    maxFiles: String(policy.config.risk.large_diff.max_files),
    maxLines: String(policy.config.risk.large_diff.max_lines),
    criticalPathsText: policy.config.critical_paths.join("\n"),
    testPatternsText: policy.config.test_patterns.join("\n"),
    rules: {
      ...policy.config.rules,
    },
  };
}

function policyScopeLabel(policy: PolicyRecord) {
  if (policy.scope === "repository") {
    return policy.repositoryFullName ? `Repository: ${policy.repositoryFullName}` : "Repository policy";
  }
  return "Organization policy";
}

function formatApiKeyRole(role: ApiKeyRole) {
  if (role === "read_only") {
    return "Read only";
  }
  return role === "ci" ? "CI" : "Admin";
}

function policyConfigFromForm(form: PolicyFormState): PolicyConfigPayload | null {
  const maxFiles = parsePositiveInteger(form.maxFiles);
  const maxLines = parsePositiveInteger(form.maxLines);
  if (maxFiles === null || maxLines === null) {
    return null;
  }
  return {
    version: 1,
    risk: {
      fail_level: form.failLevel,
      large_diff: {
        max_files: maxFiles,
        max_lines: maxLines,
      },
    },
    critical_paths: parsePatternLines(form.criticalPathsText),
    test_patterns: parsePatternLines(form.testPatternsText),
    rules: {
      ...form.rules,
    },
  };
}

function parsePositiveInteger(value: string) {
  const normalized = value.trim();
  if (!/^[1-9]\d*$/.test(normalized)) {
    return null;
  }
  return Number(normalized);
}

function parseOptionalPositiveInteger(value: string) {
  if (!value.trim()) {
    return undefined;
  }
  return parsePositiveInteger(value);
}

function parsePatternLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function compactPayload(payload: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== null && value !== undefined && value !== ""));
}

function summarizeAuditEvent(action: string, metadata: AuditMetadata) {
  if (action === "analysis.created") {
    const repository = readMetadataText(metadata, "repository") || "Analysis run";
    const pullRequest = readMetadataText(metadata, "pull_request_number");
    const riskLevel = readMetadataText(metadata, "risk_level");
    const riskScore = readMetadataText(metadata, "risk_score");
    const riskText = riskLevel ? ` at ${riskLevel}${riskScore ? ` risk (${riskScore})` : " risk"}` : "";
    return `${repository}${pullRequest ? ` #${pullRequest}` : ""} analyzed${riskText}.`;
  }
  if (action === "policy.created") {
    const policyName = readMetadataText(metadata, "policy_name") || "Policy";
    const enabled = metadata.enabled === false ? "disabled" : "enabled";
    return `${policyName} saved as ${enabled}.`;
  }
  if (action === "api_key.created") {
    return `${readMetadataText(metadata, "api_key_name") || "API key"} created.`;
  }
  if (action === "api_key.revoked") {
    return `${readMetadataText(metadata, "api_key_name") || "API key"} revoked.`;
  }
  if (action === "organization.bootstrapped") {
    return "Self-hosted organization bootstrapped.";
  }
  return `${formatLabel(action)} recorded.`;
}

function getBanner(mode: LoadMode, dataSource: DataSource) {
  if (mode === "loading") {
    return "Loading workspace data from the AgentReviewOps API...";
  }
  if (mode === "error") {
    return "Unable to load workspace data. Check the API URL, API key, or retry later.";
  }
  if (mode === "empty") {
    return "No analysis runs or audit events match this workspace yet.";
  }
  if (dataSource === "demo") {
    return "No API key configured. Showing demo analysis and audit data.";
  }
  return "";
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleString([], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatActor(actorType: string, actorId: string | null) {
  return actorId ? `${formatLabel(actorType)} ${shortId(actorId)}` : formatLabel(actorType);
}

function formatTarget(targetType: string, targetId: string | null) {
  return targetId ? `${formatLabel(targetType)} ${shortId(targetId)}` : formatLabel(targetType);
}

function formatLabel(value: string) {
  return value.replace(/[._-]+/g, " ");
}

function readMetadataText(metadata: AuditMetadata, key: string) {
  const value = metadata[key];
  if (value === null || value === undefined || typeof value === "object") {
    return "";
  }
  return String(value);
}

function formatMetadataValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return truncate(String(value), 42);
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return `${value.length} items`;
  }
  return truncate(JSON.stringify(value), 42);
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>,
);
