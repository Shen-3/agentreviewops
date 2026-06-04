import type { PolicyConfigPayload, RuleId } from "../api/types";

export const ruleLabels: Record<RuleId, string> = {
  require_tests_for_code_changes: "Require tests for code changes",
  flag_dependency_changes: "Flag dependency changes",
  flag_ci_changes: "Flag CI changes",
  flag_auth_changes: "Flag auth changes",
  flag_large_generated_files: "Flag generated files",
};

export const defaultPolicyConfig: PolicyConfigPayload = {
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
