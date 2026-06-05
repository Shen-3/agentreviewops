from __future__ import annotations

import yaml
from pydantic import BaseModel, Field

from agentreview.models import AgentReviewConfig

REQUIRED_POLICY_BUNDLE_IDS = (
    "starter",
    "security",
    "github-actions",
    "python",
    "dependency-governance",
    "ai-pr-strict",
    "enterprise-strict",
)


class PolicyBundle(BaseModel):
    id: str
    name: str
    description: str
    intended_use: str
    config: AgentReviewConfig
    notes: list[str] = Field(default_factory=list)


def list_policy_bundles() -> list[PolicyBundle]:
    return [bundle.model_copy(deep=True) for bundle in POLICY_BUNDLES]


def get_policy_bundle(bundle_id: str) -> PolicyBundle:
    normalized = bundle_id.strip().lower()
    bundle = POLICY_BUNDLE_MAP.get(normalized)
    if bundle is None:
        available = ", ".join(REQUIRED_POLICY_BUNDLE_IDS)
        raise ValueError(f"Unknown policy bundle '{bundle_id}'. Available bundles: {available}")
    return bundle.model_copy(deep=True)


def policy_bundle_to_yaml(bundle_id: str) -> str:
    bundle = get_policy_bundle(bundle_id)
    config_dict = bundle.config.model_dump(mode="json")
    return yaml.safe_dump(config_dict, sort_keys=False)


def _bundle(
    *,
    bundle_id: str,
    name: str,
    description: str,
    intended_use: str,
    config: dict,
    notes: list[str] | None = None,
) -> PolicyBundle:
    return PolicyBundle(
        id=bundle_id,
        name=name,
        description=description,
        intended_use=intended_use,
        config=AgentReviewConfig.model_validate(config),
        notes=notes or [],
    )


def _config(
    *,
    fail_level: str = "high",
    max_files: int = 20,
    max_lines: int = 800,
    critical_paths: list[str],
    test_patterns: list[str] | None = None,
    routing_rules: list[dict],
) -> dict:
    return {
        "version": 1,
        "risk": {
            "fail_level": fail_level,
            "large_diff": {
                "max_files": max_files,
                "max_lines": max_lines,
            },
        },
        "critical_paths": critical_paths,
        "test_patterns": test_patterns or ["tests/**", "**/*test*", "**/*spec*"],
        "rules": {
            "require_tests_for_code_changes": True,
            "flag_dependency_changes": True,
            "flag_ci_changes": True,
            "flag_auth_changes": True,
            "flag_large_generated_files": True,
        },
        "review_routing": {
            "enabled": True,
            "codeowners": {
                "enabled": True,
                "path": None,
            },
            "rules": routing_rules,
        },
    }


def _rule(
    rule_id: str,
    *,
    reason: str,
    paths: list[str] | None = None,
    rule_ids: list[str] | None = None,
    risk_levels: list[str] | None = None,
    require_roles: list[str] | None = None,
) -> dict:
    payload = {
        "id": rule_id,
        "reason": reason,
        "require_roles": require_roles or ["maintainer"],
    }
    if paths:
        payload["paths"] = paths
    if rule_ids:
        payload["rule_ids"] = rule_ids
    if risk_levels:
        payload["risk_levels"] = risk_levels
    return payload


SECURITY_RULE_IDS = [
    "sensitive-area-change",
    "critical-path-change",
    "python-subprocess-shell-true",
    "python-eval-exec",
    "python-unsafe-yaml-load",
]

GITHUB_ACTIONS_RULE_IDS = [
    "ci-change",
    "github-actions-write-all-permissions",
    "github-actions-pull-request-target",
    "github-actions-unpinned-action",
]

DEPENDENCY_PATHS = [
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "pyproject.toml",
    "poetry.lock",
    "requirements*.txt",
    "uv.lock",
]

INFRA_PATHS = [
    "infra/**",
    "deploy/**",
    "deployment/**",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "k8s/**",
    "helm/**",
]

STARTER_CRITICAL_PATHS = [
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
]

POLICY_BUNDLES = (
    _bundle(
        bundle_id="starter",
        name="Starter",
        description="Safe default governance for most repositories with useful reports and a low false-positive rate.",
        intended_use="General application repositories adopting AgentReviewOps for PR comments and review routing.",
        config=_config(
            fail_level="high",
            max_files=25,
            max_lines=1000,
            critical_paths=STARTER_CRITICAL_PATHS,
            routing_rules=[
                _rule(
                    "security-review",
                    paths=["auth/**", "security/**", "payments/**"],
                    rule_ids=SECURITY_RULE_IDS,
                    require_roles=["maintainer", "owner"],
                    reason="Sensitive or dangerous code path changed.",
                ),
                _rule(
                    "ci-review",
                    paths=[".github/workflows/**"],
                    rule_ids=GITHUB_ACTIONS_RULE_IDS,
                    reason="CI/CD or supply-chain sensitive workflow changed.",
                ),
                _rule(
                    "dependency-review",
                    rule_ids=["dependency-change"],
                    reason="Dependency metadata changed.",
                ),
                _rule(
                    "block-risk-review",
                    risk_levels=["block"],
                    require_roles=["owner"],
                    reason="Policy classified this pull request as block risk.",
                ),
            ],
        ),
        notes=["Use `--fail-on high` in CI once the initial signal is calibrated."],
    ),
    _bundle(
        bundle_id="security",
        name="Security",
        description="Stronger routing for AppSec and security-sensitive repositories.",
        intended_use="Authentication, authorization, payments, security, and deployment-sensitive services.",
        config=_config(
            fail_level="high",
            max_files=15,
            max_lines=600,
            critical_paths=[
                "auth/**",
                "**/auth/**",
                "security/**",
                "**/security/**",
                "payments/**",
                "**/payments/**",
                "secrets/**",
                "crypto/**",
                ".github/workflows/**",
                *INFRA_PATHS,
                *DEPENDENCY_PATHS,
            ],
            routing_rules=[
                _rule(
                    "security-owner-review",
                    paths=["auth/**", "**/auth/**", "security/**", "**/security/**", "payments/**", "**/payments/**"],
                    rule_ids=SECURITY_RULE_IDS,
                    require_roles=["maintainer", "owner"],
                    reason="Security-sensitive code or dangerous Python pattern changed.",
                ),
                _rule(
                    "supply-chain-review",
                    paths=[".github/workflows/**", *DEPENDENCY_PATHS],
                    rule_ids=[*GITHUB_ACTIONS_RULE_IDS, "dependency-change"],
                    require_roles=["maintainer", "owner"],
                    reason="Supply-chain, dependency, or CI/CD controls changed.",
                ),
                _rule(
                    "high-risk-review",
                    risk_levels=["high", "block"],
                    require_roles=["owner"],
                    reason="Security bundle classified this pull request as high or block risk.",
                ),
            ],
        ),
        notes=["Pair with CODEOWNERS entries for auth, payments, and infrastructure owners."],
    ),
    _bundle(
        bundle_id="github-actions",
        name="GitHub Actions",
        description="Workflow and supply-chain governance for repositories where CI security matters.",
        intended_use="Repositories with sensitive GitHub Actions workflows or release automation.",
        config=_config(
            fail_level="high",
            max_files=20,
            max_lines=800,
            critical_paths=[
                ".github/workflows/**",
                "action.yml",
                "action.yaml",
                "Dockerfile",
                *DEPENDENCY_PATHS,
            ],
            routing_rules=[
                _rule(
                    "workflow-security-review",
                    paths=[".github/workflows/**", "action.yml", "action.yaml"],
                    rule_ids=GITHUB_ACTIONS_RULE_IDS,
                    require_roles=["maintainer", "owner"],
                    reason="GitHub Actions workflow or action metadata changed.",
                ),
                _rule(
                    "dependency-review",
                    paths=DEPENDENCY_PATHS,
                    rule_ids=["dependency-change"],
                    reason="Dependency metadata changed near workflow execution.",
                ),
                _rule(
                    "block-risk-review",
                    risk_levels=["block"],
                    require_roles=["owner"],
                    reason="Policy classified this pull request as block risk.",
                ),
            ],
        ),
        notes=["Review unpinned actions and pull_request_target usage before merge."],
    ),
    _bundle(
        bundle_id="python",
        name="Python",
        description="Python application governance with dependency and dangerous-pattern coverage.",
        intended_use="Python services, CLIs, FastAPI apps, and libraries.",
        config=_config(
            fail_level="high",
            max_files=20,
            max_lines=800,
            critical_paths=[
                "src/**",
                "app/**",
                "backend/**",
                "apps/api/**",
                "pyproject.toml",
                "requirements*.txt",
                "poetry.lock",
                "uv.lock",
                ".github/workflows/**",
            ],
            test_patterns=["tests/**", "**/test_*.py", "**/*_test.py", "**/*test*", "**/*spec*"],
            routing_rules=[
                _rule(
                    "python-app-review",
                    paths=["src/**", "app/**", "backend/**", "apps/api/**"],
                    rule_ids=["missing-tests", *SECURITY_RULE_IDS],
                    require_roles=["maintainer"],
                    reason="Python application code or dangerous Python pattern changed.",
                ),
                _rule(
                    "python-dependency-review",
                    paths=["pyproject.toml", "requirements*.txt", "poetry.lock", "uv.lock"],
                    rule_ids=["dependency-change"],
                    reason="Python dependency metadata changed.",
                ),
                _rule(
                    "ci-review",
                    paths=[".github/workflows/**"],
                    rule_ids=GITHUB_ACTIONS_RULE_IDS,
                    reason="Python CI/CD workflow changed.",
                ),
            ],
        ),
        notes=["Keep tests under `tests/**` or adjust test_patterns in the generated config."],
    ),
    _bundle(
        bundle_id="dependency-governance",
        name="Dependency Governance",
        description="Focused review routing for dependency and supply-chain changes.",
        intended_use="Repositories that want consistent maintainer review for manifests and lockfiles.",
        config=_config(
            fail_level="high",
            max_files=18,
            max_lines=700,
            critical_paths=[*DEPENDENCY_PATHS, ".github/workflows/**"],
            routing_rules=[
                _rule(
                    "dependency-maintainer-review",
                    paths=DEPENDENCY_PATHS,
                    rule_ids=["dependency-change"],
                    require_roles=["maintainer"],
                    reason="Dependency manifest or lockfile changed.",
                ),
                _rule(
                    "workflow-supply-chain-review",
                    paths=[".github/workflows/**"],
                    rule_ids=GITHUB_ACTIONS_RULE_IDS,
                    require_roles=["maintainer"],
                    reason="Workflow changes can alter dependency installation or release behavior.",
                ),
                _rule(
                    "block-risk-review",
                    risk_levels=["block"],
                    require_roles=["owner"],
                    reason="Policy classified this pull request as block risk.",
                ),
            ],
        ),
        notes=["Useful when dependency-only PRs should still leave audit evidence."],
    ),
    _bundle(
        bundle_id="ai-pr-strict",
        name="AI PR Strict",
        description="Strict human-review routing for teams merging AI-generated pull requests.",
        intended_use="Teams that require broad maintainer review before AI-generated PRs merge.",
        config=_config(
            fail_level="medium",
            max_files=12,
            max_lines=500,
            critical_paths=[
                "src/**",
                "app/**",
                "backend/**",
                "apps/**",
                "packages/**",
                "auth/**",
                "security/**",
                "payments/**",
                ".github/workflows/**",
                "**/migrations/**",
                *INFRA_PATHS,
                *DEPENDENCY_PATHS,
            ],
            routing_rules=[
                _rule(
                    "ai-sensitive-review",
                    paths=["auth/**", "security/**", "payments/**", ".github/workflows/**", "**/migrations/**"],
                    rule_ids=[*SECURITY_RULE_IDS, *GITHUB_ACTIONS_RULE_IDS, "database-migration-change"],
                    require_roles=["maintainer", "owner"],
                    reason="AI-generated sensitive, workflow, or migration change requires human review.",
                ),
                _rule(
                    "ai-dependency-review",
                    paths=DEPENDENCY_PATHS,
                    rule_ids=["dependency-change"],
                    require_roles=["maintainer"],
                    reason="AI-generated dependency changes require maintainer review.",
                ),
                _rule(
                    "ai-high-risk-review",
                    risk_levels=["medium", "high", "block"],
                    require_roles=["maintainer", "owner"],
                    reason="AI PR strict bundle routes medium or higher risk to humans.",
                ),
            ],
        ),
        notes=["Recommended generated workflow setting: `fail-on: high` or stricter after calibration."],
    ),
    _bundle(
        bundle_id="enterprise-strict",
        name="Enterprise Strict",
        description="Conservative enterprise governance for broad sensitive surfaces.",
        intended_use="Regulated or change-controlled repositories that require strong audit evidence.",
        config=_config(
            fail_level="medium",
            max_files=8,
            max_lines=300,
            critical_paths=[
                "src/**",
                "app/**",
                "backend/**",
                "apps/**",
                "packages/**",
                "services/**",
                "auth/**",
                "security/**",
                "payments/**",
                "api/**",
                "config/**",
                ".github/**",
                "**/migrations/**",
                *INFRA_PATHS,
                *DEPENDENCY_PATHS,
            ],
            routing_rules=[
                _rule(
                    "enterprise-sensitive-review",
                    paths=["auth/**", "security/**", "payments/**", "api/**", "config/**", ".github/**", *INFRA_PATHS],
                    rule_ids=[*SECURITY_RULE_IDS, *GITHUB_ACTIONS_RULE_IDS, "database-migration-change"],
                    require_roles=["maintainer", "owner"],
                    reason="Enterprise-sensitive code, policy, infrastructure, or workflow changed.",
                ),
                _rule(
                    "enterprise-dependency-review",
                    paths=DEPENDENCY_PATHS,
                    rule_ids=["dependency-change"],
                    require_roles=["maintainer", "owner"],
                    reason="Enterprise dependency metadata changed.",
                ),
                _rule(
                    "enterprise-risk-review",
                    risk_levels=["medium", "high", "block"],
                    require_roles=["owner"],
                    reason="Enterprise strict bundle routes medium or higher risk to owners.",
                ),
            ],
        ),
        notes=["Use repository memberships and CODEOWNERS to avoid unconfigured review requirements."],
    ),
)

POLICY_BUNDLE_MAP = {bundle.id: bundle for bundle in POLICY_BUNDLES}
