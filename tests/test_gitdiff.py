from pathlib import Path

from agentreview.config import parse_config
from agentreview.gitdiff import detect_language, parse_diff_file, parse_unified_diff

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_docs_only_diff_parses_changed_file() -> None:
    changed_files = parse_diff_file(FIXTURES_DIR / "docs_only.diff")

    assert len(changed_files) == 1
    changed_file = changed_files[0]
    assert changed_file.path == "README.md"
    assert changed_file.previous_path is None
    assert changed_file.status == "modified"
    assert changed_file.additions == 2
    assert changed_file.deletions == 1
    assert changed_file.language == "markdown"
    assert changed_file.is_test_file is False


def test_source_diff_parses_multiple_files_and_test_classification() -> None:
    changed_files = parse_diff_file(FIXTURES_DIR / "source_with_tests.diff")

    assert [changed_file.path for changed_file in changed_files] == [
        "src/agentreview/cli.py",
        "tests/test_cli.py",
    ]
    assert changed_files[0].status == "modified"
    assert changed_files[0].additions == 2
    assert changed_files[0].deletions == 1
    assert changed_files[0].is_test_file is False
    assert changed_files[1].status == "modified"
    assert changed_files[1].additions == 2
    assert changed_files[1].deletions == 1
    assert changed_files[1].is_test_file is True


def test_rename_diff_preserves_previous_path() -> None:
    changed_files = parse_diff_file(FIXTURES_DIR / "rename.diff")

    assert len(changed_files) == 1
    changed_file = changed_files[0]
    assert changed_file.path == "src/agentreview/new_name.py"
    assert changed_file.previous_path == "src/agentreview/old_name.py"
    assert changed_file.status == "renamed"
    assert changed_file.additions == 1
    assert changed_file.deletions == 1


def test_custom_test_patterns_are_used() -> None:
    config = parse_config({"version": 1, "test_patterns": ["specs/**"]})
    diff_text = """diff --git a/specs/example.py b/specs/example.py
index 1111111..2222222 100644
--- a/specs/example.py
+++ b/specs/example.py
@@ -1 +1,2 @@
 assert True
+assert 1 == 1
"""

    changed_files = parse_unified_diff(diff_text, config=config)

    assert changed_files[0].is_test_file is True


def test_added_and_deleted_statuses_parse_from_dev_null_headers() -> None:
    diff_text = """diff --git a/src/new_module.py b/src/new_module.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/src/new_module.py
@@ -0,0 +1,2 @@
+VALUE = 1
+ENABLED = True
diff --git a/src/removed_module.py b/src/removed_module.py
deleted file mode 100644
index 2222222..0000000
--- a/src/removed_module.py
+++ /dev/null
@@ -1,2 +0,0 @@
-VALUE = 1
-ENABLED = True
"""

    changed_files = parse_unified_diff(diff_text)

    assert [(file.path, file.status) for file in changed_files] == [
        ("src/new_module.py", "added"),
        ("src/removed_module.py", "deleted"),
    ]
    assert changed_files[0].additions == 2
    assert changed_files[0].deletions == 0
    assert changed_files[1].additions == 0
    assert changed_files[1].deletions == 2


def test_added_lines_preserve_content_and_new_line_numbers() -> None:
    diff_text = """diff --git a/src/example.py b/src/example.py
index 1111111..2222222 100644
--- a/src/example.py
+++ b/src/example.py
@@ -10,2 +10,3 @@
 value = 1
+enabled = True
 return value
"""

    changed_files = parse_unified_diff(diff_text)

    assert changed_files[0].additions == 1
    assert changed_files[0].added_lines[0].content == "enabled = True"
    assert changed_files[0].added_lines[0].line_number == 11


def test_detect_language_uses_common_extensions_and_filenames() -> None:
    assert detect_language("src/app.py") == "python"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("unknown/file.lock") is None
