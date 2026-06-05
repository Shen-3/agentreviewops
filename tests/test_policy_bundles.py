import yaml

from agentreview.config import parse_config
from agentreview.models import AgentReviewConfig
from agentreview.policy_bundles import (
    REQUIRED_POLICY_BUNDLE_IDS,
    get_policy_bundle,
    list_policy_bundles,
    policy_bundle_to_yaml,
)


def test_required_policy_bundle_ids_exist_and_are_unique() -> None:
    bundles = list_policy_bundles()
    bundle_ids = [bundle.id for bundle in bundles]

    assert bundle_ids == list(REQUIRED_POLICY_BUNDLE_IDS)
    assert len(bundle_ids) == len(set(bundle_ids))


def test_each_policy_bundle_config_validates() -> None:
    for bundle in list_policy_bundles():
        assert isinstance(bundle.config, AgentReviewConfig)
        assert bundle.name
        assert bundle.description
        assert bundle.intended_use


def test_policy_bundle_yaml_round_trips_to_config() -> None:
    for bundle_id in REQUIRED_POLICY_BUNDLE_IDS:
        raw_config = yaml.safe_load(policy_bundle_to_yaml(bundle_id))

        config = parse_config(raw_config, source=f"bundle {bundle_id}")

        assert config == get_policy_bundle(bundle_id).config


def test_starter_bundle_is_not_overly_strict() -> None:
    starter = get_policy_bundle("starter").config

    assert starter.risk.fail_level == "high"
    assert starter.risk.large_diff.max_files >= 20
    assert starter.risk.large_diff.max_lines >= 800
    assert starter.review_routing.enabled is True
    assert starter.review_routing.codeowners.enabled is True


def test_enterprise_strict_is_stricter_than_starter() -> None:
    starter = get_policy_bundle("starter").config
    enterprise = get_policy_bundle("enterprise-strict").config

    assert enterprise.risk.fail_level == "medium"
    assert enterprise.risk.large_diff.max_files < starter.risk.large_diff.max_files
    assert enterprise.risk.large_diff.max_lines < starter.risk.large_diff.max_lines
    assert len(enterprise.critical_paths) > len(starter.critical_paths)


def test_github_actions_bundle_routes_workflow_changes() -> None:
    bundle = get_policy_bundle("github-actions").config
    routing_rules = bundle.review_routing.rules

    assert ".github/workflows/**" in bundle.critical_paths
    assert any(".github/workflows/**" in rule.paths for rule in routing_rules)
    assert any("github-actions-pull-request-target" in rule.rule_ids for rule in routing_rules)


def test_python_bundle_includes_python_and_dependency_paths() -> None:
    bundle = get_policy_bundle("python").config

    assert "src/**" in bundle.critical_paths
    assert "pyproject.toml" in bundle.critical_paths
    assert "requirements*.txt" in bundle.critical_paths
    assert "uv.lock" in bundle.critical_paths
    assert any("python-eval-exec" in rule.rule_ids for rule in bundle.review_routing.rules)
