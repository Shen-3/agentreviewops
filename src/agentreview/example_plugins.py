from __future__ import annotations

from agentreview.models import RiskFinding
from agentreview.plugins import AnalysisContext


class DependencyManifestPlugin:
    id = "dependency-manifest"
    name = "Dependency Manifest Plugin"
    permissions = ["read_diff"]

    def analyze(self, context: AnalysisContext) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        for changed_file in context.changed_files:
            if changed_file.path in {"package.json", "pyproject.toml", "requirements.txt"}:
                findings.append(
                    RiskFinding(
                        rule_id="plugin-dependency-manifest",
                        severity="medium",
                        title="Plugin flagged dependency manifest",
                        description=f"{self.name} flagged {changed_file.path} for owner review.",
                        score_delta=5,
                        file_path=changed_file.path,
                        evidence={"plugin_id": self.id},
                    )
                )
        return findings
