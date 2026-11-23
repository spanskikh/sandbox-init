from __future__ import annotations

import json
import os
import re
from enum import StrEnum
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


class ViolationCode(StrEnum):
    MISSING_REQUIRED_FILE = "MISSING_REQUIRED_FILE"
    MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
    PLACEHOLDER_LEAK = "PLACEHOLDER_LEAK"
    LANGUAGE_DRIFT_CYRILLIC = "LANGUAGE_DRIFT_CYRILLIC"
    BROKEN_MERMAID_BLOCK = "BROKEN_MERMAID_BLOCK"
    BROKEN_RELATIVE_LINK = "BROKEN_RELATIVE_LINK"
    CHANGELOG_TRACEABILITY_GAP = "CHANGELOG_TRACEABILITY_GAP"
    LOW_MARKET_SIGNAL_OR_HYPE = "LOW_MARKET_SIGNAL_OR_HYPE"
    CLUSTER_DOC_DUPLICATE = "CLUSTER_DOC_DUPLICATE"


class DocViolation(BaseModel):
    code: ViolationCode
    file: str
    detail: str


class DocAuditReport(BaseModel):
    passed: bool
    violations: list[DocViolation] = Field(default_factory=list)


class DocRubricScore(BaseModel):
    completeness: int = Field(ge=1, le=5)
    style_consistency: int = Field(ge=1, le=5)
    interviewer_market_value: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=5, max_length=400)


PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\[\u0443\u043a\u0430\u0436\u0438"),
    re.compile(r"Lorem ipsum", re.IGNORECASE),
)

HYPE_PATTERNS = (
    re.compile(r"\bgame-changing\b", re.IGNORECASE),
    re.compile(r"\bseamless AI magic\b", re.IGNORECASE),
    re.compile(r"\b100% hallucination-free\b", re.IGNORECASE),
    re.compile(r"\brevolutionary AI\b", re.IGNORECASE),
)

ENGINEERING_SIGNAL_TOKENS = (
    "Z3",
    "PyTest",
    "Hypothesis",
    "Pydantic",
    "SAT",
    "UNSAT",
    "DuckDB",
    "PostgreSQL",
)
MERMAID_DIRECTIVES = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "erDiagram")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)]*)?\)")


def audit_documentation(root: Path, require_capa_registry: bool = False) -> DocAuditReport:
    del require_capa_registry
    violations: list[DocViolation] = []
    for dup in ("DEVPROCESS.md", "RELEASES.md", "docs/DEFECTS_AND_CAPA.md", "docs/releases"):
        if (root / dup).exists():
            violations.append(
                DocViolation(
                    code=ViolationCode.CLUSTER_DOC_DUPLICATE,
                    file=dup,
                    detail="Cluster doc must live only in spanskikh/spanskikh.",
                )
            )
    loaded: dict[str, str] = {}
    for rel in ("README.md", "CHANGELOG.md", "docs/ARCHITECTURE.md", "docs/ENGINEERING_PROFILE.md"):
        t = root / rel
        if not t.is_file() or t.stat().st_size < 120:
            violations.append(
                DocViolation(
                    code=ViolationCode.MISSING_REQUIRED_FILE,
                    file=rel,
                    detail="Required file missing or <120B.",
                )
            )
        else:
            loaded[rel] = t.read_text(encoding="utf-8")
    skip = {".venv", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    for md in sorted(root.rglob("*.md")):
        if any(part in skip for part in md.parts):
            continue
        rmd, txt = str(md.relative_to(root)), md.read_text(encoding="utf-8")
        if re.search(r"[А-Яа-яЁё]", txt):
            violations.append(
                DocViolation(
                    code=ViolationCode.LANGUAGE_DRIFT_CYRILLIC,
                    file=rmd,
                    detail="Cyrillic detected.",
                )
            )
        for pat in PLACEHOLDER_PATTERNS:
            if pat.search(txt):
                violations.append(
                    DocViolation(
                        code=ViolationCode.PLACEHOLDER_LEAK,
                        file=rmd,
                        detail=f"Placeholder: {pat.pattern}",
                    )
                )
    for rel, txt in loaded.items():
        for pat in HYPE_PATTERNS:
            if pat.search(txt):
                violations.append(
                    DocViolation(
                        code=ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE,
                        file=rel,
                        detail=f"Hype: {pat.pattern}",
                    )
                )
        ddir = (root / rel).parent
        for m in LINK_RE.finditer(txt):
            href = m.group(1)
            if (
                not href.startswith(("http://", "https://", "mailto:"))
                and not (ddir / href).exists()
            ):
                violations.append(
                    DocViolation(
                        code=ViolationCode.BROKEN_RELATIVE_LINK,
                        file=rel,
                        detail=f"Broken link: {href}",
                    )
                )
    if "README.md" in loaded:
        rm = loaded["README.md"]
        if "https://github.com/spanskikh/spanskikh" not in rm:
            violations.append(
                DocViolation(
                    code=ViolationCode.BROKEN_RELATIVE_LINK,
                    file="README.md",
                    detail="Missing spanskikh/spanskikh SSoT link.",
                )
            )
        if not any(tok in rm for tok in ENGINEERING_SIGNAL_TOKENS):
            violations.append(
                DocViolation(
                    code=ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE,
                    file="README.md",
                    detail="Missing engineering tokens.",
                )
            )
    if "docs/ARCHITECTURE.md" in loaded:
        arch = loaded["docs/ARCHITECTURE.md"]
        if arch.count("```") % 2 != 0 or "```mermaid" not in arch:
            violations.append(
                DocViolation(
                    code=ViolationCode.BROKEN_MERMAID_BLOCK,
                    file="docs/ARCHITECTURE.md",
                    detail="Broken mermaid block.",
                )
            )
        if "Risk" not in arch or "Control Matrix" not in arch:
            violations.append(
                DocViolation(
                    code=ViolationCode.MISSING_REQUIRED_SECTION,
                    file="docs/ARCHITECTURE.md",
                    detail="Missing Risk section.",
                )
            )
    if "docs/ENGINEERING_PROFILE.md" in loaded:
        prof = loaded["docs/ENGINEERING_PROFILE.md"]
        for sec in (
            "## 1. Concepts and Theories",
            "## 2. Frameworks and Libraries",
            "## 3. Dev Tools and Environment",
            "## 4. Processes and Procedures",
            "## 5. Test Approach, Tools, Environment & Metrics",
        ):
            if sec not in prof:
                violations.append(
                    DocViolation(
                        code=ViolationCode.MISSING_REQUIRED_SECTION,
                        file="docs/ENGINEERING_PROFILE.md",
                        detail=f"Missing {sec}",
                    )
                )
    if "CHANGELOG.md" in loaded and "### Verification Evidence" not in loaded["CHANGELOG.md"]:
        violations.append(
            DocViolation(
                code=ViolationCode.CHANGELOG_TRACEABILITY_GAP,
                file="CHANGELOG.md",
                detail="Missing Verification Evidence.",
            )
        )
    return DocAuditReport(passed=not violations, violations=violations)


def _seed_clean_repo(base: Path) -> None:
    (base / "docs").mkdir(parents=True, exist_ok=True)
    (base / "README.md").write_text(
        "# Project\n\nDeterministic verification with Z3, PyTest, and DuckDB.\n"
        "Governed by https://github.com/spanskikh/spanskikh single source of truth.\n",
        encoding="utf-8",
    )
    (base / "docs/ENGINEERING_PROFILE.md").write_text(
        "# Engineering Profile\n\n## 1. Concepts and Theories\n- SMT verification.\n\n"
        "## 2. Frameworks and Libraries\n- Pydantic v2 and Z3.\n\n"
        "## 3. Dev Tools and Environment\n- Linux and PyTest.\n\n"
        "## 4. Processes and Procedures\n- Traceable CR workflow.\n\n"
        "## 5. Test Approach, Tools, Environment & Metrics\n- 100% SAT/UNSAT pass rate.\n",
        encoding="utf-8",
    )
    (base / "docs/ARCHITECTURE.md").write_text(
        "# Architecture\n\n## 1. Topology\n```mermaid\nflowchart TD\n    A --> B\n```\n\n"
        "## 2. ADR-001\nUses Z3 SMT, Pydantic v2, and DuckDB.\n\n"
        "## 3. Risk & Control Matrix\nMitigates drift via PyTest.\n",
        encoding="utf-8",
    )
    (base / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-11-22 — CR-001: Baseline\n"
        "### Objective & Risk Mitigated\n- Closed drift risk.\n"
        "### Verification Evidence\n- `pytest -v`: `4 passed`.\n",
        encoding="utf-8",
    )


def test_repository_documentation_passes_quality_gate() -> None:
    report = audit_documentation(REPO_ROOT)
    assert report.passed, f"Documentation audit failed: {report.model_dump_json(indent=2)}"


@pytest.mark.parametrize(
    ("defect_name", "expected_code"),
    [
        ("missing_arch", ViolationCode.MISSING_REQUIRED_FILE),
        ("cyrillic_leak", ViolationCode.LANGUAGE_DRIFT_CYRILLIC),
        ("cyrillic_in_subdoc", ViolationCode.LANGUAGE_DRIFT_CYRILLIC),
        ("missing_risk_section", ViolationCode.MISSING_REQUIRED_SECTION),
        ("todo_placeholder", ViolationCode.PLACEHOLDER_LEAK),
        ("unclosed_mermaid", ViolationCode.BROKEN_MERMAID_BLOCK),
        ("broken_link", ViolationCode.BROKEN_RELATIVE_LINK),
        ("hype_without_proofs", ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE),
        ("missing_engineering_profile", ViolationCode.MISSING_REQUIRED_FILE),
        ("missing_profile_section", ViolationCode.MISSING_REQUIRED_SECTION),
        ("cluster_doc_duplicate", ViolationCode.CLUSTER_DOC_DUPLICATE),
    ],
)
def test_doc_auditor_catches_seeded_counterexamples(
    tmp_path: Path, defect_name: str, expected_code: ViolationCode
) -> None:
    _seed_clean_repo(tmp_path)
    assert audit_documentation(tmp_path).passed

    if defect_name == "missing_arch":
        (tmp_path / "docs/ARCHITECTURE.md").unlink()
    elif defect_name == "cyrillic_leak":
        (tmp_path / "README.md").write_text("# Проект\n" + "x" * 130, encoding="utf-8")
    elif defect_name == "cyrillic_in_subdoc":
        (tmp_path / "docs/subdoc.md").write_text(
            "# Subdoc\nПроверка кириллицы.\n", encoding="utf-8"
        )
    elif defect_name == "missing_risk_section":
        (tmp_path / "docs/ARCHITECTURE.md").write_text(
            "# Architecture\n```mermaid\nflowchart TD\nA-->B\n```\n" + "x" * 120, encoding="utf-8"
        )
    elif defect_name == "todo_placeholder":
        (tmp_path / "README.md").write_text(
            "# Project\nTODO: fill later.\n" + "x" * 120, encoding="utf-8"
        )
    elif defect_name == "unclosed_mermaid":
        (tmp_path / "docs/ARCHITECTURE.md").write_text(
            "# Architecture\n## 3. Risk & Control Matrix\n```mermaid\nflowchart TD\n" + "x" * 120,
            encoding="utf-8",
        )
    elif defect_name == "broken_link":
        (tmp_path / "README.md").write_text(
            "# Project\nSee [doc](docs/missing.md) Z3 [https://github.com/spanskikh/spanskikh](https://github.com/spanskikh/spanskikh)\n"
            + "x" * 120,
            encoding="utf-8",
        )
    elif defect_name == "hype_without_proofs":
        (tmp_path / "README.md").write_text(
            "# Project\nOur revolutionary AI is game-changing [https://github.com/spanskikh/spanskikh](https://github.com/spanskikh/spanskikh)\n"
            + "x" * 120,
            encoding="utf-8",
        )
    elif defect_name == "missing_engineering_profile":
        (tmp_path / "docs/ENGINEERING_PROFILE.md").unlink()
    elif defect_name == "missing_profile_section":
        (tmp_path / "docs/ENGINEERING_PROFILE.md").write_text(
            "# Profile\n" + "x" * 130, encoding="utf-8"
        )
    elif defect_name == "cluster_doc_duplicate":
        (tmp_path / "DEVPROCESS.md").write_text("# Duplicate\n" + "x" * 130, encoding="utf-8")

    report = audit_documentation(tmp_path)
    assert not report.passed
    assert expected_code in {v.code for v in report.violations}


def _judge_doc_with_ollama(model: str, markdown: str) -> DocRubricScore:
    prompt = (
        "Score this repository documentation for a Senior AI QA / SDET / Test Architect role. "
        "Return strict JSON matching keys: completeness (1-5), style_consistency (1-5), "
        "interviewer_market_value (1-5), rationale (string). "
        "Penalize generic hype without proofs.\n\n"
        f"{markdown[:4000]}"
    )
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "format": "json", "stream": False},
        timeout=60.0,
    )
    resp.raise_for_status()
    return DocRubricScore.model_validate(json.loads(resp.json()["response"]))


@pytest.mark.integration
def test_live_ollama_doc_rubric_and_counterexample() -> None:
    tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0).json().get("models", [])
    model_names = [m["name"] for m in tags if "embed" not in m["name"]]
    assert model_names, "No generative Ollama model available on hippo"
    model = model_names[0]

    real_bundle = (
        (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        + "\n\n"
        + (REPO_ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    )
    real_score = _judge_doc_with_ollama(model, real_bundle)
    assert real_score.completeness >= 4, f"Low completeness: {real_score}"
    assert real_score.style_consistency >= 4, f"Low style consistency: {real_score}"
    assert real_score.interviewer_market_value >= 4, f"Low market value: {real_score}"

    weak_counterexample = (
        "# My Project\nWe built a cool AI app that uses prompts to answer questions fast."
    )
    weak_score = _judge_doc_with_ollama(model, weak_counterexample)
    assert weak_score.interviewer_market_value <= 2, (
        f"LLM judge failed to penalize low-value counterexample: {weak_score}"
    )
