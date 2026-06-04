from __future__ import annotations

import re
import shlex
from fnmatch import fnmatchcase
from pathlib import Path

from agentreview.models import AddedDiffLine, AgentReviewConfig, DiffFile, DiffStatus

LANGUAGE_BY_EXTENSION = {
    ".css": "css",
    ".go": "go",
    ".html": "html",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".yml": "yaml",
    ".yaml": "yaml",
}

LANGUAGE_BY_FILENAME = {
    "Dockerfile": "dockerfile",
}

HUNK_HEADER_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,\d+)? \+(?P<new_start>\d+)(?:,\d+)? @@")


def parse_diff_file(path: str | Path, config: AgentReviewConfig | None = None) -> list[DiffFile]:
    diff_path = Path(path)
    return parse_unified_diff(diff_path.read_text(encoding="utf-8"), config=config)


def parse_unified_diff(diff_text: str, config: AgentReviewConfig | None = None) -> list[DiffFile]:
    active_config = config or AgentReviewConfig()
    parsed_files: list[DiffFile] = []
    current: _PartialDiffFile | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                parsed_files.append(_build_diff_file(current, active_config))
            old_path, new_path = _parse_diff_git_paths(line)
            current = _PartialDiffFile(path=new_path or old_path, previous_path=None, status="modified")
            continue

        if current is None:
            continue

        if line.startswith("new file mode "):
            current.status = "added"
        elif line.startswith("deleted file mode "):
            current.status = "deleted"
        elif line.startswith("rename from "):
            current.previous_path = line.removeprefix("rename from ").strip()
            current.status = "renamed"
        elif line.startswith("rename to "):
            current.path = line.removeprefix("rename to ").strip()
            current.status = "renamed"
        elif line.startswith("--- "):
            old_path = _parse_file_marker_path(line)
            if old_path is None:
                current.status = "added"
            elif current.status == "deleted":
                current.path = old_path
        elif line.startswith("+++ "):
            new_path = _parse_file_marker_path(line)
            if new_path is None:
                current.status = "deleted"
            else:
                current.path = new_path
        elif line.startswith("@@ "):
            old_line_number, new_line_number = _parse_hunk_line_numbers(line)
            current.old_line_number = old_line_number
            current.new_line_number = new_line_number
        elif line.startswith("+"):
            current.additions += 1
            current.added_lines.append(
                AddedDiffLine(
                    content=line[1:],
                    line_number=current.new_line_number,
                )
            )
            if current.new_line_number is not None:
                current.new_line_number += 1
        elif line.startswith("-"):
            current.deletions += 1
            if current.old_line_number is not None:
                current.old_line_number += 1
        elif line.startswith(" "):
            if current.old_line_number is not None:
                current.old_line_number += 1
            if current.new_line_number is not None:
                current.new_line_number += 1

    if current is not None:
        parsed_files.append(_build_diff_file(current, active_config))

    return parsed_files


class _PartialDiffFile:
    def __init__(
        self,
        *,
        path: str,
        previous_path: str | None,
        status: DiffStatus,
    ) -> None:
        self.path = path
        self.previous_path = previous_path
        self.status: DiffStatus = status
        self.additions = 0
        self.deletions = 0
        self.added_lines: list[AddedDiffLine] = []
        self.old_line_number: int | None = None
        self.new_line_number: int | None = None


def _build_diff_file(partial: _PartialDiffFile, config: AgentReviewConfig) -> DiffFile:
    paths = [partial.path]
    if partial.previous_path is not None:
        paths.append(partial.previous_path)

    return DiffFile(
        path=partial.path,
        previous_path=partial.previous_path,
        status=partial.status,
        additions=partial.additions,
        deletions=partial.deletions,
        language=detect_language(partial.path),
        is_test_file=_matches_any(paths, config.test_patterns),
        is_critical_file=_matches_any(paths, config.critical_paths),
        added_lines=partial.added_lines,
    )


def _parse_diff_git_paths(line: str) -> tuple[str, str]:
    parts = shlex.split(line)
    if len(parts) < 4:
        return "", ""
    return _strip_git_prefix(parts[2]) or "", _strip_git_prefix(parts[3]) or ""


def _parse_file_marker_path(line: str) -> str | None:
    marker_path = line[4:].split("\t", maxsplit=1)[0].strip()
    return _strip_git_prefix(marker_path)


def _parse_hunk_line_numbers(line: str) -> tuple[int | None, int | None]:
    match = HUNK_HEADER_RE.match(line)
    if match is None:
        return None, None
    return int(match.group("old_start")), int(match.group("new_start"))


def _strip_git_prefix(path: str) -> str | None:
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def detect_language(path: str) -> str | None:
    filename = Path(path).name
    if filename in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[filename]
    return LANGUAGE_BY_EXTENSION.get(Path(path).suffix.lower())


def _matches_any(paths: list[str], patterns: list[str]) -> bool:
    return any(_matches_pattern(path, pattern) for path in paths for pattern in patterns)


def _matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = path.strip("/")
    normalized_pattern = pattern.strip("/")
    if fnmatchcase(normalized_path, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatchcase(normalized_path, normalized_pattern[3:])
    return False
