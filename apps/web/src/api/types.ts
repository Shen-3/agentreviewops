export type RiskLevel = "low" | "medium" | "high" | "block";
export type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";
export type LoadMode = "loading" | "ready" | "empty" | "error";
export type DataSource = "api" | "demo";
export type AuditExportFormat = "json" | "csv";
export type AuditMetadata = Record<string, unknown>;
export type RuleId = "require_tests_for_code_changes" | "flag_dependency_changes" | "flag_ci_changes" | "flag_auth_changes" | "flag_large_generated_files";

export type Finding = {
  severity: FindingSeverity;
  rule: string;
  file: string;
  reason: string;
};

export type ChangedFile = {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  critical: boolean;
  test: boolean;
};

export type SuggestedReviewer = {
  source: string;
  identifier: string;
  role: string | null;
};

export type ReviewRequirement = {
  requirementId: string;
  title: string;
  reason: string;
  matchedFiles: string[];
  matchedRuleIds: string[];
  requiredRoles: string[];
  suggestedReviewers: SuggestedReviewer[];
};

export type Analysis = {
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
  reviewRequirements: ReviewRequirement[];
  report: string;
};

export type AuditEvent = {
  id: string;
  createdAt: string;
  action: string;
  actor: string;
  target: string;
  summary: string;
  metadata: AuditMetadata;
};

export type ApiKeyRecord = {
  id: string;
  name: string;
  role: "admin" | "ci" | "read_only";
  keyPrefix: string;
  createdAt: string;
  revokedAt: string | null;
  isCurrent: boolean;
};

export type UserRecord = {
  id: string;
  email: string;
  name: string;
  role: string;
  createdAt: string;
};

export type RepositoryRecord = {
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

export type RepositoryReviewer = {
  userId: string;
  email: string;
  name: string | null;
  role: string;
};

export type CreatedApiKey = {
  name: string;
  value: string;
};

export type ApiKeyRole = "admin" | "ci" | "read_only";

export type DashboardAuth = {
  organizationId: string;
  apiKeyId: string;
  apiKeyName: string;
  apiKeyRole: ApiKeyRole;
};

export type DashboardAccess = {
  role: ApiKeyRole | null;
  roleLabel: string;
  canSubmitAnalysis: boolean;
  canManageGovernance: boolean;
  analysisHint: string | null;
  governanceHint: string | null;
};

export type RulesConfigPayload = Record<RuleId, boolean>;

export type PolicyConfigPayload = {
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

export type PolicyRecord = {
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

export type PolicyFormState = {
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

export type DiffSubmitFormState = {
  diff: string;
  repository: string;
  pullRequestNumber: string;
  title: string;
  author: string;
  agentName: string;
  branch: string;
};

export type RepositoryFormState = {
  provider: string;
  owner: string;
  name: string;
  defaultBranch: string;
  visibility: string;
};

export type UserFormState = {
  email: string;
  name: string;
  role: "admin" | "reviewer";
};

export type MembershipFormState = {
  repositoryId: string;
  userId: string;
  role: "owner" | "maintainer" | "reviewer";
};

export type ApiSummary = {
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

export type ApiDetail = {
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
  review_requirements: Array<{
    requirement_id: string;
    title: string;
    reason: string;
    matched_files: string[];
    matched_rule_ids: string[];
    required_roles: string[];
    suggested_reviewers: Array<{
      source: string;
      identifier: string;
      role: string | null;
    }>;
  }>;
  markdown: string;
};

export type ApiAuditEvent = {
  audit_event_id: string;
  created_at: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata: AuditMetadata;
};

export type ApiKeyPayload = {
  api_key_id: string;
  name: string;
  role: ApiKeyRole;
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
  is_current: boolean;
};

export type ApiAuthPayload = {
  organization_id: string;
  api_key_id: string;
  api_key_name: string;
  api_key_role: ApiKeyRole;
};

export type ApiUserPayload = {
  user_id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
};

export type ApiRepositoryPayload = {
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

export type ApiKeyCreatePayload = ApiKeyPayload & {
  api_key: string;
};

export type ApiPolicyPayload = {
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
