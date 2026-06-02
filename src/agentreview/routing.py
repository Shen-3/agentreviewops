from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from agentreview.models import AgentReviewConfig, DiffFile, ReviewRequirement, RiskAnalysis, SuggestedReviewer

DEFAULT_CODEOWNERS_PATHS = [
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
]


@dataclass(frozen=True)
class CodeownersEntry:
    pattern: str
    owners: tuple[str, ...]


def build_review_requirements(
    *,
    analysis: RiskAnalysis,
    changed_files: list[DiffFile],
    config: AgentReviewConfig,
    repository_reviewers: list[SuggestedReviewer] | None = None,
    codeowners_text: str | None = None,
) -> list[ReviewRequirement]:
    if not config.review_routing.enabled:
        return []

    codeowners_entries = parse_codeowners(codeowners_text or "") if config.review_routing.codeowners.enabled else []
    repository_reviewers = repository_reviewers or []
    requirements: list[ReviewRequirement] = []
    seen_requirement_ids: set[str] = set()

    for rule in config.review_routing.rules:
        matched_files = _matched_files_for_rule(rule.paths, changed_files)
        matched_rule_ids = _matched_rule_ids_for_rule(rule.rule_ids, analysis)
        risk_level_matched = analysis.risk_level in rule.risk_levels

        if not matched_files and not matched_rule_ids and not risk_level_matched:
            continue

        finding_files = _finding_files_for_rule_ids(matched_rule_ids, analysis)
        all_matched_files = _dedupe([*matched_files, *finding_files])
        suggested_reviewers = _dedupe_reviewers(
            [
                *_codeowners_reviewers_for_files(all_matched_files, codeowners_entries),
                *_repository_reviewers_for_roles(repository_reviewers, rule.require_roles),
            ]
        )

        if rule.id in seen_requirement_ids:
            continue
        seen_requirement_ids.add(rule.id)
        requirements.append(
            ReviewRequirement(
                requirement_id=rule.id,
                title=_title_for_rule_id(rule.id),
                reason=rule.reason,
                matched_files=all_matched_files,
                matched_rule_ids=matched_rule_ids,
                required_roles=rule.require_roles,
                suggested_reviewers=suggested_reviewers,
            )
        )

    return requirements


def load_codeowners_text(path: str | Path | None = None) -> str | None:
    if path is not None:
        codeowners_path = Path(path)
        if not codeowners_path.exists():
            return None
        return codeowners_path.read_text(encoding="utf-8")

    for candidate in DEFAULT_CODEOWNERS_PATHS:
        codeowners_path = Path(candidate)
        if codeowners_path.exists() and codeowners_path.is_file():
            return codeowners_path.read_text(encoding="utf-8")
    return None


def parse_codeowners(codeowners_text: str) -> list[CodeownersEntry]:
    entries: list[CodeownersEntry] = []
    for raw_line in codeowners_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = tuple(owner for owner in parts[1:] if _is_owner_token(owner))
        if not owners:
            continue
        entries.append(CodeownersEntry(pattern=pattern, owners=owners))
    return entries


def codeowners_for_path(path: str, entries: list[CodeownersEntry]) -> list[str]:
    owners: list[str] = []
    for entry in entries:
        if _matches_pattern(path, entry.pattern):
            owners.extend(entry.owners)
    return _dedupe(owners)


def _matched_files_for_rule(patterns: list[str], changed_files: list[DiffFile]) -> list[str]:
    if not patterns:
        return []
    matched_files: list[str] = []
    for changed_file in changed_files:
        paths = [changed_file.path]
        if changed_file.previous_path is not None:
            paths.append(changed_file.previous_path)
        if any(_matches_pattern(path, pattern) for path in paths for pattern in patterns):
            matched_files.append(changed_file.path)
    return _dedupe(matched_files)


def _matched_rule_ids_for_rule(rule_ids: list[str], analysis: RiskAnalysis) -> list[str]:
    if not rule_ids:
        return []
    return _dedupe([finding.rule_id for finding in analysis.findings if finding.rule_id in rule_ids])


def _finding_files_for_rule_ids(rule_ids: list[str], analysis: RiskAnalysis) -> list[str]:
    if not rule_ids:
        return []
    return _dedupe(
        [
            finding.file_path
            for finding in analysis.findings
            if finding.rule_id in rule_ids and finding.file_path is not None
        ]
    )


def _codeowners_reviewers_for_files(files: list[str], entries: list[CodeownersEntry]) -> list[SuggestedReviewer]:
    reviewers: list[SuggestedReviewer] = []
    for file_path in files:
        for owner in codeowners_for_path(file_path, entries):
            reviewers.append(SuggestedReviewer(source="codeowners", identifier=owner))
    return reviewers


def _repository_reviewers_for_roles(reviewers: list[SuggestedReviewer], roles: list[str]) -> list[SuggestedReviewer]:
    if not roles:
        return []
    role_set = set(roles)
    return [
        reviewer
        for reviewer in reviewers
        if reviewer.role in role_set
    ]


def _dedupe_reviewers(reviewers: list[SuggestedReviewer]) -> list[SuggestedReviewer]:
    deduped: list[SuggestedReviewer] = []
    seen: set[tuple[str, str, str | None]] = set()
    for reviewer in reviewers:
        key = (reviewer.source, reviewer.identifier, reviewer.role)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reviewer)
    return deduped


def _dedupe(values: list[str | None]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _is_owner_token(token: str) -> bool:
    return token.startswith("@") or "@" in token


def _title_for_rule_id(rule_id: str) -> str:
    return f"{rule_id.replace('-', ' ').capitalize()}"


def _matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = path.strip("/")
    normalized_pattern = pattern.strip("/")
    if not normalized_path or not normalized_pattern:
        return False
    if fnmatchcase(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatchcase(normalized_path, normalized_pattern[3:])
    if "/" not in normalized_pattern:
        return fnmatchcase(PurePosixPath(normalized_path).name, normalized_pattern)
    return PurePosixPath(normalized_path).match(normalized_pattern)
