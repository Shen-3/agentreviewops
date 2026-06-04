import type {
  Analysis,
  ApiKeyRecord,
  AuditEvent,
  MetricsOverview,
  MetricsRepositories,
  MetricsRouting,
  MetricsRules,
  PolicyRecord,
  RepositoryRecord,
  UserRecord,
} from "../api/types";
import { defaultPolicyConfig } from "../config/defaultPolicy";

export const seededAnalyses: Analysis[] = [
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
    reviewRequirements: [
      {
        requirementId: "security-review",
        title: "Security review",
        reason: "Sensitive or dangerous code path changed.",
        matchedFiles: ["auth/session.py"],
        matchedRuleIds: ["critical-path-change", "sensitive-area-change"],
        requiredRoles: ["maintainer", "owner"],
        suggestedReviewers: [{ source: "repository_membership", identifier: "@reviewer", role: "maintainer" }],
      },
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
    reviewRequirements: [],
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
    reviewRequirements: [
      {
        requirementId: "ci-review",
        title: "Ci review",
        reason: "CI/CD or supply-chain sensitive workflow changed.",
        matchedFiles: [".github/workflows/release.yml"],
        matchedRuleIds: ["ci-change"],
        requiredRoles: ["maintainer"],
        suggestedReviewers: [],
      },
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

export const seededAuditEvents: AuditEvent[] = [
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

export const seededApiKeys: ApiKeyRecord[] = [
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

export const seededUsers: UserRecord[] = [
  {
    id: "user_reviewer",
    email: "reviewer@example.com",
    name: "Reviewer",
    githubLogin: "reviewer",
    role: "admin",
    createdAt: "05/23/2026, 10:38",
  },
];

export const seededRepositories: RepositoryRecord[] = [
  {
    id: "repo_checkout_api",
    provider: "github",
    owner: "platform",
    name: "checkout-api",
    fullName: "platform/checkout-api",
    defaultBranch: "main",
    visibility: "private",
    reviewers: [
      {
        userId: "user_reviewer",
        email: "reviewer@example.com",
        name: "Reviewer",
        githubLogin: "reviewer",
        role: "maintainer",
      },
    ],
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

export const seededPolicies: PolicyRecord[] = [
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

export const seededMetricsOverview: MetricsOverview = {
  analysis_count: 3,
  risk_distribution: { low: 1, medium: 0, high: 1, block: 1 },
  high_or_block_count: 2,
  average_risk_score: 44.33,
  unique_repository_count: 3,
  unique_agent_count: 3,
  analysis_count_by_agent: { Codex: 1, Cursor: 1, Devin: 1 },
  recent_trend: [
    { date: "2026-05-21", analysis_count: 0 },
    { date: "2026-05-22", analysis_count: 1 },
    { date: "2026-05-23", analysis_count: 2 },
  ],
  generated_at: "2026-05-23T11:36:00Z",
};

export const seededMetricsRules: MetricsRules = {
  total_finding_count: 7,
  severity_distribution: { info: 1, low: 0, medium: 3, high: 3, critical: 0 },
  high_impact_rule_count: 3,
  top_rules: [
    { rule_id: "critical-path-change", finding_count: 2, average_score_delta: 25, high_impact_count: 2 },
    { rule_id: "missing-tests", finding_count: 2, average_score_delta: 15, high_impact_count: 0 },
    { rule_id: "ci-change", finding_count: 1, average_score_delta: 20, high_impact_count: 1 },
  ],
  generated_at: "2026-05-23T11:36:00Z",
};

export const seededMetricsRouting: MetricsRouting = {
  total_review_requirement_count: 2,
  unconfigured_review_requirement_count: 1,
  configured_review_requirement_count: 1,
  routing_hit_rate: 0.5,
  reviewer_source_distribution: { repository_membership: 1 },
  required_role_distribution: { maintainer: 2, owner: 1 },
  top_unconfigured_requirements: [{ requirement_id: "ci-review", title: "Ci review", count: 1 }],
  generated_at: "2026-05-23T11:36:00Z",
};

export const seededMetricsRepositories: MetricsRepositories = {
  repositories: [
    {
      repository: "platform/checkout-api",
      analysis_count: 1,
      average_risk_score: 55,
      high_or_block_count: 1,
      last_analysis_time: "2026-05-23T11:34:00Z",
      top_risk_level: "high",
      unconfigured_review_requirement_count: 0,
      top_triggered_rule_ids: ["critical-path-change", "sensitive-area-change", "missing-tests"],
    },
    {
      repository: "infra/deployments",
      analysis_count: 1,
      average_risk_score: 78,
      high_or_block_count: 1,
      last_analysis_time: "2026-05-22T17:46:00Z",
      top_risk_level: "block",
      unconfigured_review_requirement_count: 1,
      top_triggered_rule_ids: ["critical-path-change", "ci-change", "missing-tests"],
    },
  ],
  generated_at: "2026-05-23T11:36:00Z",
};
