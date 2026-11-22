# Target: tests/test_release_hygiene.py
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Forbidden patterns in tracked repository files prior to public release
FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("WORKSTATION_HOME_PATH", re.compile(r"/home/serg(?:/|\b)")),
    ("PRIVATE_KEY_HEADER", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("OPENAI_OR_SK_TOKEN", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("GITHUB_PAT_TOKEN", re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("REAL_PHONE_NUMBER", re.compile(r"\+49\s?1[567]\d[\s-]?\d{6,8}")),
)

FORBIDDEN_TRACKED_SUFFIXES: tuple[str, ...] = (
    ".duckdb",
    ".duckdb.wal",
    ".log",
    ".stdout",
    ".stderr",
    ".env",
)


def _git_tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    rel_paths = [p for p in proc.stdout.split("\x00") if p]
    return [REPO_ROOT / p for p in rel_paths]


def test_no_secrets_pii_or_forbidden_artifacts_in_tracked_files() -> None:
    tracked = _git_tracked_files()
    assert len(tracked) >= 10, "Expected tracked repository files from git ls-files"

    violations: list[str] = []
    for path in tracked:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.endswith(FORBIDDEN_TRACKED_SUFFIXES) or rel == ".env":
            violations.append(f"FORBIDDEN_TRACKED_FILE: {rel}")
            continue
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for code, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                violations.append(f"{code} in {rel}")

    assert not violations, "Release hygiene gate failed:\n" + "\n".join(violations)


def test_staged_ci_and_publish_script_ready_for_public_promotion() -> None:
    staged_ci = REPO_ROOT / "docs" / "ci" / "ci.yml"
    active_ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    publish_script = REPO_ROOT / "scripts" / "publish_to_github.sh"

    assert publish_script.is_file(), "Missing scripts/publish_to_github.sh"
    script_text = publish_script.read_text(encoding="utf-8")
    assert ".venv/bin/ruff check src tests" in script_text
    assert ".venv/bin/mypy src tests --strict" in script_text
    assert ".venv/bin/pytest -v -m \"not integration\"" in script_text
    assert "git mv docs/ci/ci.yml .github/workflows/ci.yml" in script_text

    # Before public promotion, CI stays staged in docs/ci/ci.yml
    if not active_ci.exists():
        assert staged_ci.is_file(), "Missing staged CI blueprint docs/ci/ci.yml"
        ci_text = staged_ci.read_text(encoding="utf-8")
    else:
        ci_text = active_ci.read_text(encoding="utf-8")

    for expected_step in (
        "ruff check src tests",
        "mypy src tests --strict",
        "pytest -v -m \"not integration\"",
        "cyclonedx-py environment -o sbom.cdx.json",
    ):
        assert expected_step in ci_text, f"Missing '{expected_step}' in CI workflow"


@pytest.mark.parametrize(
    ("code", "sample"),
    [
        ("WORKSTATION_HOME_PATH", "ARTIFACT: /home/serg/projects/sandbox-init/logs/run.log"),
        ("PRIVATE_KEY_HEADER", "-----BEGIN OPENSSH PRIVATE KEY-----"),
        ("OPENAI_OR_SK_TOKEN", "api_key = 'sk-proj1234567890abcdefghij'"),
        ("GITHUB_PAT_TOKEN", "token = 'ghp_1234567890abcdefghijklmnop'"),
        ("AWS_ACCESS_KEY", "aws_id = 'AKIAIOSFODNN7EXAMPLE'"),
        ("REAL_PHONE_NUMBER", "contact: +4915141519079"),
    ],
)
def test_hygiene_patterns_catch_seeded_leaks(code: str, sample: str) -> None:
    matched = [name for name, pat in FORBIDDEN_PATTERNS if pat.search(sample)]
    assert code in matched
