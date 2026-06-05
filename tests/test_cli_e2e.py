import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from agentreview.cli import app
from agentreview.config import parse_config
from agentreview.policy_bundles import policy_bundle_to_yaml

PROJECT_ROOT = Path(__file__).parents[1]


def test_scan_diff_smoke_with_bundle_generated_config(tmp_path: Path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "agentreview.yml"
    markdown_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"
    sarif_path = tmp_path / "report.sarif.json"
    config_path.write_text(policy_bundle_to_yaml("starter"), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "scan-diff",
            "--diff-file",
            str(PROJECT_ROOT / "examples" / "sample.diff"),
            "--config",
            str(config_path),
            "--output",
            str(markdown_path),
            "--json-output",
            str(json_path),
            "--sarif-output",
            str(sarif_path),
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0, result.output
    parse_config(yaml.safe_load(config_path.read_text(encoding="utf-8")), source=str(config_path))
    assert markdown_path.read_text(encoding="utf-8").startswith("# AgentReviewOps Report")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["risk_score"] >= 0
    assert payload["risk_level"] in {"low", "medium", "high", "block"}
    assert isinstance(payload["findings"], list)
    assert isinstance(payload["changed_files"], list)
    assert isinstance(payload["review_requirements"], list)

    sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
