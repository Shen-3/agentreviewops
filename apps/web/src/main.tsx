import React from "react";
import ReactDOM from "react-dom/client";
import { AlertTriangle, ClipboardCopy, Database, KeyRound, LogOut, RefreshCcw, Search, ShieldCheck } from "lucide-react";

import "./styles.css";

type RiskLevel = "low" | "medium" | "high" | "block";
type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";
type LoadMode = "loading" | "ready" | "empty" | "error";
type DataSource = "api" | "demo";

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

const API_BASE_URL = import.meta.env.VITE_AGENTREVIEW_API_URL || "http://127.0.0.1:8000";
const API_KEY_STORAGE_KEY = "agentreviewops.apiKey";

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

function Dashboard() {
  const [analyses, setAnalyses] = React.useState<Analysis[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<LoadMode>("loading");
  const [dataSource, setDataSource] = React.useState<DataSource>("api");
  const [riskFilter, setRiskFilter] = React.useState<RiskLevel | "all">("all");
  const [query, setQuery] = React.useState("");
  const [apiKey, setApiKey] = React.useState(() => window.localStorage.getItem(API_KEY_STORAGE_KEY) || "");
  const [apiKeyInput, setApiKeyInput] = React.useState("");

  const loadAnalyses = React.useCallback(async () => {
    setMode("loading");
    if (!apiKey) {
      setAnalyses(seededAnalyses);
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/api/analysis-runs`, apiKey);
      const summaries = (await response.json()) as ApiSummary[];
      const normalized = summaries.map(normalizeSummary);
      setAnalyses(normalized);
      setDataSource("api");
      setMode(normalized.length ? "ready" : "empty");
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
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
    }
  }, [apiKey]);

  React.useEffect(() => {
    void loadAnalyses();
  }, [loadAnalyses]);

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
  const medianScore = median(filteredAnalyses.map((analysis) => analysis.riskScore));
  const highCount = filteredAnalyses.filter((analysis) => ["high", "block"].includes(analysis.riskLevel)).length;
  const findingCount = filteredAnalyses.reduce((total, analysis) => total + analysis.findingCount, 0);

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
    setSelectedId(seededAnalyses[0].id);
    setDataSource("demo");
    setMode("ready");
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
            <button className="primary" type="button" onClick={() => void loadAnalyses()}>
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
          <Metric label="Median score" value={medianScore} />
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

async function fetchWithTimeout(url: string, apiKey: string) {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
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

function getBanner(mode: LoadMode, dataSource: DataSource) {
  if (mode === "loading") {
    return "Loading analysis runs from the AgentReviewOps API...";
  }
  if (mode === "error") {
    return "Unable to load analysis runs. Check the API URL or retry later.";
  }
  if (mode === "empty") {
    return "No analysis runs match this workspace yet.";
  }
  if (dataSource === "demo") {
    return "API unavailable. Showing demo analysis data.";
  }
  return "";
}

function median(values: number[]) {
  if (!values.length) {
    return 0;
  }
  return [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
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

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>,
);
