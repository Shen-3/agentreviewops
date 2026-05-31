import React from "react";
import ReactDOM from "react-dom/client";
import { AlertTriangle, ClipboardCopy, Database, Download, KeyRound, LogOut, RefreshCcw, Search, ShieldCheck } from "lucide-react";

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
  keyPrefix: string;
  createdAt: string;
  revokedAt: string | null;
  isCurrent: boolean;
};

type CreatedApiKey = {
  name: string;
  value: string;
};

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
  enabled: boolean;
  config: PolicyConfigPayload;
  createdAt: string;
  updatedAt: string;
};

type PolicyFormState = {
  name: string;
  enabled: boolean;
  failLevel: RiskLevel;
  maxFiles: string;
  maxLines: string;
  criticalPathsText: string;
  testPatternsText: string;
  rules: RulesConfigPayload;
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
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
  is_current: boolean;
};

type ApiKeyCreatePayload = ApiKeyPayload & {
  api_key: string;
};

type ApiPolicyPayload = {
  policy_id: string;
  name: string;
  scope: string;
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
    keyPrefix: "arok_demo_ci",
    createdAt: "05/23/2026, 10:39",
    revokedAt: null,
    isCurrent: true,
  },
  {
    id: "key_dashboard_operator",
    name: "Dashboard operator",
    keyPrefix: "arok_demo_ui",
    createdAt: "05/23/2026, 10:42",
    revokedAt: null,
    isCurrent: false,
  },
  {
    id: "key_retired",
    name: "Retired bootstrap key",
    keyPrefix: "arok_demo_old",
    createdAt: "05/22/2026, 18:12",
    revokedAt: "05/23/2026, 09:05",
    isCurrent: false,
  },
];

const seededPolicies: PolicyRecord[] = [
  {
    id: "policy_default",
    name: "Default review policy",
    scope: "organization",
    enabled: true,
    config: defaultPolicyConfig,
    createdAt: "05/23/2026, 10:42",
    updatedAt: "05/23/2026, 10:42",
  },
];

function Dashboard() {
  const [analyses, setAnalyses] = React.useState<Analysis[]>([]);
  const [auditEvents, setAuditEvents] = React.useState<AuditEvent[]>([]);
  const [apiKeys, setApiKeys] = React.useState<ApiKeyRecord[]>([]);
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
  const [createdApiKey, setCreatedApiKey] = React.useState<CreatedApiKey | null>(null);

  const loadWorkspaceData = React.useCallback(async () => {
    setMode("loading");
    if (!apiKey) {
      setAnalyses(seededAnalyses);
      setAuditEvents(seededAuditEvents);
      setApiKeys(seededApiKeys);
      setPolicies(seededPolicies);
      setPolicyForm(policyToForm(seededPolicies[0]));
      setCreatedApiKey(null);
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
      return;
    }
    try {
      const [analysisResponse, auditResponse, apiKeysResponse, policiesResponse] = await Promise.all([
        fetchWithTimeout(`${API_BASE_URL}/api/analysis-runs`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/audit-events?limit=50`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/api-keys`, apiKey),
        fetchWithTimeout(`${API_BASE_URL}/api/policies`, apiKey),
      ]);
      const summaries = (await analysisResponse.json()) as ApiSummary[];
      const auditPayload = (await auditResponse.json()) as ApiAuditEvent[];
      const apiKeyPayload = (await apiKeysResponse.json()) as ApiKeyPayload[];
      const policyPayload = (await policiesResponse.json()) as ApiPolicyPayload[];
      const normalized = summaries.map(normalizeSummary);
      const normalizedAudit = auditPayload.map(normalizeAuditEvent);
      const normalizedApiKeys = apiKeyPayload.map(normalizeApiKey);
      const normalizedPolicies = policyPayload.map(normalizePolicy);
      setAnalyses(normalized);
      setAuditEvents(normalizedAudit);
      setApiKeys(normalizedApiKeys);
      setPolicies(normalizedPolicies);
      setPolicyForm(policyToForm(normalizedPolicies[0] ?? seededPolicies[0]));
      setDataSource("api");
      setMode(normalized.length || normalizedAudit.length || normalizedApiKeys.length || normalizedPolicies.length ? "ready" : "empty");
      setSelectedId(normalized[0]?.id ?? null);
      if (normalized[0]) {
        void loadAnalysisDetail(normalized[0].id, apiKey, setAnalyses, setMode);
      }
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
        setMode("error");
        return;
      }
      setAnalyses(seededAnalyses);
      setAuditEvents(seededAuditEvents);
      setApiKeys(seededApiKeys);
      setPolicies(seededPolicies);
      setPolicyForm(policyToForm(seededPolicies[0]));
      setCreatedApiKey(null);
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
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
    setPolicies(seededPolicies);
    setPolicyForm(policyToForm(seededPolicies[0]));
    setPolicyStatus("");
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
        body: JSON.stringify({ name: normalizedName }),
      });
      const payload = (await response.json()) as ApiKeyCreatePayload;
      const record = normalizeApiKey(payload);
      setApiKeys((current) => [record, ...current]);
      setCreatedApiKey({ name: record.name, value: payload.api_key });
      setNewApiKeyName("");
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        window.localStorage.removeItem(API_KEY_STORAGE_KEY);
        setApiKey("");
      }
      setMode("error");
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
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/policies`, apiKey, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: policyForm.name.trim(),
          enabled: policyForm.enabled,
          scope: "organization",
          config,
        }),
      });
      const saved = normalizePolicy((await response.json()) as ApiPolicyPayload);
      setPolicies((current) => [saved, ...current]);
      setPolicyForm(policyToForm(saved));
      setPolicyStatus("Policy saved. New analyses will use the latest enabled policy.");
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
            <button type="button" onClick={() => setMode("loading")}>
              <RefreshCcw size={16} />
              Loading
            </button>
            <button type="button" onClick={() => setMode("error")}>
              <AlertTriangle size={16} />
              Error
            </button>
            <button type="button" onClick={() => setMode("empty")}>
              <Database size={16} />
              Empty
            </button>
            <button className="primary" type="button" onClick={() => void loadWorkspaceData()}>
              <ShieldCheck size={16} />
              Live data
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

        <PolicyEditor
          policies={policies}
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
          createdApiKey={createdApiKey}
          onNameChange={setNewApiKeyName}
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

function PolicyEditor({
  policies,
  form,
  mode,
  dataSource,
  status,
  onFormChange,
  onSave,
}: {
  policies: PolicyRecord[];
  form: PolicyFormState;
  mode: LoadMode;
  dataSource: DataSource;
  status: string;
  onFormChange: React.Dispatch<React.SetStateAction<PolicyFormState>>;
  onSave: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const liveData = dataSource === "api";
  const activePolicy = policies.find((policy) => policy.enabled) ?? policies[0] ?? null;
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
          <button className="primary" type="submit" disabled={!liveData || mode === "loading"}>
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
  createdApiKey,
  onNameChange,
  onCreate,
  onDismissCreated,
  onRevoke,
}: {
  apiKeys: ApiKeyRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  newApiKeyName: string;
  createdApiKey: CreatedApiKey | null;
  onNameChange: (value: string) => void;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onDismissCreated: () => void;
  onRevoke: (apiKeyId: string) => void;
}) {
  const liveData = dataSource === "api";
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
      <td colSpan={5}>{message}</td>
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

async function fetchWithTimeout(url: string, apiKey: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${apiKey}`);

  const response = await fetch(url, {
    ...init,
    headers,
    signal: AbortSignal.timeout(900),
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
    keyPrefix: payload.key_prefix,
    createdAt: formatDate(payload.created_at),
    revokedAt: payload.revoked_at ? formatDate(payload.revoked_at) : null,
    isCurrent: payload.is_current,
  };
}

function normalizePolicy(payload: ApiPolicyPayload): PolicyRecord {
  return {
    id: payload.policy_id,
    name: payload.name,
    scope: payload.scope,
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

function parsePatternLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
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
    return "Unable to load workspace data. Check the API URL or retry later.";
  }
  if (mode === "empty") {
    return "No analysis runs or audit events match this workspace yet.";
  }
  if (dataSource === "demo") {
    return "API unavailable. Showing demo analysis and audit data.";
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
