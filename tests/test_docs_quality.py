from __future__ import annotations

import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Literal

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
    violations: list[DocViolation] = []
    required_files = [
        "README.md",
        "CHANGELOG.md",
        "RELEASES.md",
        "docs/ARCHITECTURE.md",
        "docs/ENGINEERING_PROFILE.md",
    ]
    if require_capa_registry:
        required_files.append("docs/DEFECTS_AND_CAPA.md")

    loaded: dict[str, str] = {}
    for rel in required_files:
        target = root / rel
        if not target.is_file() or target.stat().st_size < 120:
            violations.append(
                DocViolation(
                    code=ViolationCode.MISSING_REQUIRED_FILE,
                    file=rel,
                    detail="Required documentation file is missing or stubbed (<120 bytes).",
                )
            )
        else:
            loaded[rel] = target.read_text(encoding="utf-8")

    for rel, text in loaded.items():
        if re.search(r"[А-Яа-яЁё]", text):
            violations.append(
                DocViolation(
                    code=ViolationCode.LANGUAGE_DRIFT_CYRILLIC,
                    file=rel,
                    detail="Cyrillic characters detected in public English documentation.",
                )
            )
        for pat in PLACEHOLDER_PATTERNS:
            if pat.search(text):
                violations.append(
                    DocViolation(
                        code=ViolationCode.PLACEHOLDER_LEAK,
                        file=rel,
                        detail=f"Unresolved placeholder matched: {pat.pattern}",
                    )
                )
        for pat in HYPE_PATTERNS:
            if pat.search(text):
                violations.append(
                    DocViolation(
                        code=ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE,
                        file=rel,
                        detail=f"Marketing hype phrase detected: {pat.pattern}",
                    )
                )

        doc_dir = (root / rel).parent
        for match in LINK_RE.finditer(text):
            href = match.group(1)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (doc_dir / href).resolve()
            if not resolved.exists():
                violations.append(
                    DocViolation(
                        code=ViolationCode.BROKEN_RELATIVE_LINK,
                        file=rel,
                        detail=f"Broken relative link target: {href}",
                    )
                )

    for rel in ("README.md", "docs/ARCHITECTURE.md"):
        if rel not in loaded:
            continue
        text = loaded[rel]
        headings = [line for line in text.splitlines() if line.startswith("#")]
        if len(headings) < 4:
            violations.append(
                DocViolation(
                    code=ViolationCode.MISSING_REQUIRED_SECTION,
                    file=rel,
                    detail=f"Expected >= 4 Markdown headings, found {len(headings)}.",
                )
            )
        mermaid_starts = text.count("```mermaid")
        total_fences = text.count("```")
        has_directive = any(d in text for d in MERMAID_DIRECTIVES)
        if mermaid_starts < 1 or total_fences % 2 != 0 or not has_directive:
            violations.append(
                DocViolation(
                    code=ViolationCode.BROKEN_MERMAID_BLOCK,
                    file=rel,
                    detail="Missing, unclosed, or invalid Mermaid diagram block.",
                )
            )
        signal_hits = sum(1 for tok in ENGINEERING_SIGNAL_TOKENS if tok in text)
        if signal_hits < 3:
            violations.append(
                DocViolation(
                    code=ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE,
                    file=rel,
                    detail=f"Insufficient concrete engineering evidence tokens ({signal_hits}/3).",
                )
            )

    if "docs/ARCHITECTURE.md" in loaded:
        arch = loaded["docs/ARCHITECTURE.md"]
        if "Risk" not in arch or "ADR" not in arch:
            violations.append(
                DocViolation(
                    code=ViolationCode.MISSING_REQUIRED_SECTION,
                    file="docs/ARCHITECTURE.md",
                    detail="ARCHITECTURE.md must include ADR and Risk sections.",
                )
            )

    if "docs/ENGINEERING_PROFILE.md" in loaded:
        prof = loaded["docs/ENGINEERING_PROFILE.md"]
        required_profile_headings = (
            "## 1. Concepts and Theories",
            "## 2. Frameworks and Libraries",
            "## 3. Dev Tools and Environment",
            "## 4. Processes and Procedures",
            "## 5. Test Approach, Tools, Environment & Metrics",
        )
        for heading in required_profile_headings:
            if heading not in prof:
                violations.append(
                    DocViolation(
                        code=ViolationCode.MISSING_REQUIRED_SECTION,
                        file="docs/ENGINEERING_PROFILE.md",
                        detail=f"ENGINEERING_PROFILE.md missing required section: {heading}",
                    )
                )
        signal_hits = sum(1 for tok in ENGINEERING_SIGNAL_TOKENS if tok in prof)
        if signal_hits < 3:
            violations.append(
                DocViolation(
                    code=ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE,
                    file="docs/ENGINEERING_PROFILE.md",
                    detail=f"Insufficient concrete engineering evidence tokens ({signal_hits}/3).",
                )
            )

    if "CHANGELOG.md" in loaded:
        ch = loaded["CHANGELOG.md"]
        if "Objective & Risk Mitigated" not in ch or "Verification Evidence" not in ch:
            violations.append(
                DocViolation(
                    code=ViolationCode.CHANGELOG_TRACEABILITY_GAP,
                    file="CHANGELOG.md",
                    detail="CHANGELOG.md missing Objective or Verification Evidence.",
                )
            )
        if not re.search(r"CR-\d{3}", ch):
            violations.append(
                DocViolation(
                    code=ViolationCode.CHANGELOG_TRACEABILITY_GAP,
                    file="CHANGELOG.md",
                    detail="CHANGELOG.md missing formal CR-XXX traceability identifiers.",
                )
            )

    if require_capa_registry and "docs/DEFECTS_AND_CAPA.md" in loaded:
        capa = loaded["docs/DEFECTS_AND_CAPA.md"]
        if "BUG-001" not in capa or "CAPA-001" not in capa:
            violations.append(
                DocViolation(
                    code=ViolationCode.CHANGELOG_TRACEABILITY_GAP,
                    file="docs/DEFECTS_AND_CAPA.md",
                    detail="DEFECTS_AND_CAPA.md missing BUG-001 or CAPA-001 records.",
                )
            )


    rel_dir = root / "docs/releases"
    retro_files = sorted(rel_dir.glob("v*-retrospective.md")) if rel_dir.is_dir() else []
    if not retro_files:
        violations.append(
            DocViolation(
                code=ViolationCode.MISSING_REQUIRED_FILE,
                file="docs/releases/",
                detail="At least one release retrospective (vX.Y.Z-retrospective.md) is required.",
            )
        )
    else:
        latest_retro = retro_files[-1]
        retro_txt = latest_retro.read_text(encoding="utf-8")
        required_secs = (
            "Lessons Learned",
            "Rejected Ideas",
            "Unlucky Probe-Runs",
            "Release Chat Digest",
        )
        for sec in required_secs:
            if sec not in retro_txt:
                violations.append(
                    DocViolation(
                        code=ViolationCode.MISSING_REQUIRED_SECTION,
                        file=f"docs/releases/{latest_retro.name}",
                        detail=f"Release retrospective missing required section: {sec}",
                    )
                )


    if "RELEASES.md" in loaded:
        rel_doc = loaded["RELEASES.md"]
        has_goal = "Business Goal:" in rel_doc
        has_contrib = "Contribution to Release Business Goal" in rel_doc
        if not has_goal or not has_contrib:
            violations.append(
                DocViolation(
                    code=ViolationCode.CHANGELOG_TRACEABILITY_GAP,
                    file="RELEASES.md",
                    detail="RELEASES.md must define Business Goal and CR contribution tables.",
                )
            )

    return DocAuditReport(passed=len(violations) == 0, violations=violations)


def _seed_clean_repo(base: Path) -> None:
    (base / "docs/releases").mkdir(parents=True, exist_ok=True)
    (base / "docs/releases/v0.1.0-retrospective.md").write_text(
        "# Retro\n## Lessons Learned\n- Ok\n## Rejected Ideas\n- None\n"
        "## Unlucky Probe-Runs\n- None\n## Release Chat Digest\n- Done\n",
        encoding="utf-8",
    )
    (base / "README.md").write_text(
        "# demo-ops — Formal Neuro-Symbolic Verifier\n\n"
        "Deterministic Z3 SMT and Pydantic v2 verification harness with PyTest and Hypothesis.\n\n"
        "## Architecture\n```mermaid\nflowchart LR\n    LLM --> Z3\n```\n\n"
        "## Invariants\n- Enforces SAT / UNSAT formal proofs.\n\n"
        "## Quickstart\nSee [Architecture](docs/ARCHITECTURE.md).\n",
        encoding="utf-8",
    )
    (base / "docs/ENGINEERING_PROFILE.md").write_text(
        "# Engineering Profile — demo-ops\n\n"
        "## 1. Concepts and Theories\n- Formal Z3 SMT verification and Pydantic contracts.\n\n"
        "## 2. Frameworks and Libraries\n- Uses z3-solver, Pydantic v2, DuckDB, and PyTest.\n\n"
        "## 3. Dev Tools and Environment\n- Linux workstation with Python 3.12 and Hypothesis.\n\n"
        "## 4. Processes and Procedures\n- Traceable CR workflow and hygiene gates.\n\n"
        "## 5. Test Approach, Tools, Environment & Metrics\n"
        "- 100% SAT/UNSAT invariant pass rate.\n",
        encoding="utf-8",
    )
    (base / "docs/ARCHITECTURE.md").write_text(
        "# Architecture\n\n## 1. Topology\n```mermaid\nflowchart TD\n    A --> B\n```\n\n"
        "## 2. ADR-001\nUses Z3 SMT, Pydantic v2, and DuckDB for SAT/UNSAT proofs.\n\n"
        "## 3. Risk & Control Matrix\nMitigates drift via PyTest and Hypothesis.\n",
        encoding="utf-8",
    )
    (base / "RELEASES.md").write_text(
        "# Releases\n## Release v0.1.0\n- **Business Goal:** Baseline.\n"
        "| CR # | Contribution to Release Business Goal |\n| --- | --- |\n",
        encoding="utf-8",
    )
    (base / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-11-22 — CR-001: Baseline\n"
        "### Objective & Risk Mitigated\n- Closed drift risk.\n"
        "### Verification Evidence\n- `pytest -v`: `4 passed`.\n",
        encoding="utf-8",
    )


def test_repository_documentation_passes_quality_gate() -> None:
    is_root_cluster = REPO_ROOT.name == "sandbox-init"
    report = audit_documentation(REPO_ROOT, require_capa_registry=is_root_cluster)
    assert report.passed, f"Documentation audit failed: {report.model_dump_json(indent=2)}"


@pytest.mark.parametrize(
    ("defect_name", "expected_code"),
    [
        ("missing_arch", ViolationCode.MISSING_REQUIRED_FILE),
        ("cyrillic_leak", ViolationCode.LANGUAGE_DRIFT_CYRILLIC),
        ("missing_risk_section", ViolationCode.MISSING_REQUIRED_SECTION),
        ("todo_placeholder", ViolationCode.PLACEHOLDER_LEAK),
        ("unclosed_mermaid", ViolationCode.BROKEN_MERMAID_BLOCK),
        ("broken_link", ViolationCode.BROKEN_RELATIVE_LINK),
        ("hype_without_proofs", ViolationCode.LOW_MARKET_SIGNAL_OR_HYPE),
        ("missing_retrospective_section", ViolationCode.MISSING_REQUIRED_SECTION),
        ("missing_releases_doc", ViolationCode.MISSING_REQUIRED_FILE),
        ("missing_engineering_profile", ViolationCode.MISSING_REQUIRED_FILE),
        ("missing_profile_section", ViolationCode.MISSING_REQUIRED_SECTION),
    ],
)
def test_doc_auditor_catches_seeded_counterexamples(
    tmp_path: Path,
    defect_name: Literal[
        "missing_arch",
        "cyrillic_leak",
        "missing_risk_section",
        "todo_placeholder",
        "unclosed_mermaid",
        "broken_link",
        "hype_without_proofs",
        "missing_retrospective_section",
        "missing_releases_doc",
        "missing_engineering_profile",
        "missing_profile_section",
    ],
    expected_code: ViolationCode,
) -> None:
    _seed_clean_repo(tmp_path)
    assert audit_documentation(tmp_path).passed

    if defect_name == "missing_arch":
        (tmp_path / "docs/ARCHITECTURE.md").unlink()
    elif defect_name == "cyrillic_leak":
        readme = tmp_path / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\nЧерновик описания.\n", encoding="utf-8"
        )
    elif defect_name == "missing_risk_section":
        arch = tmp_path / "docs/ARCHITECTURE.md"
        arch.write_text(
            arch.read_text(encoding="utf-8").replace("## 3. Risk & Control Matrix", "## 3. Notes"),
            encoding="utf-8",
        )
    elif defect_name == "todo_placeholder":
        arch = tmp_path / "docs/ARCHITECTURE.md"
        arch.write_text(
            arch.read_text(encoding="utf-8") + "\nTODO: add benchmarks.\n", encoding="utf-8"
        )
    elif defect_name == "unclosed_mermaid":
        readme = tmp_path / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\n```mermaid\nflowchart LR\n    X --> Y\n",
            encoding="utf-8",
        )
    elif defect_name == "broken_link":
        readme = tmp_path / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\nSee [Missing](docs/DOES_NOT_EXIST.md).\n",
            encoding="utf-8",
        )
    elif defect_name == "hype_without_proofs":
        (tmp_path / "README.md").write_text(
            "# app\n## One\n## Two\n## Three\n"
            "```mermaid\nflowchart LR\n    A --> B\n```\n"
            "This is a game-changing seamless AI magic platform.\n",
            encoding="utf-8",
        )

    elif defect_name == "missing_retrospective_section":
        retro = tmp_path / "docs/releases/v0.1.0-retrospective.md"
        retro.write_text(
            retro.read_text(encoding="utf-8").replace("## Rejected Ideas", "## Other"),
            encoding="utf-8",
        )

    elif defect_name == "missing_releases_doc":
        (tmp_path / "RELEASES.md").unlink()

    elif defect_name == "missing_engineering_profile":
        (tmp_path / "docs/ENGINEERING_PROFILE.md").unlink()

    elif defect_name == "missing_profile_section":
        prof = tmp_path / "docs/ENGINEERING_PROFILE.md"
        prof.write_text(
            prof.read_text(encoding="utf-8").replace(
                "## 5. Test Approach, Tools, Environment & Metrics", "## 5. Summary"
            ),
            encoding="utf-8",
        )

    mutated = audit_documentation(tmp_path)
    assert not mutated.passed, f"Oracle failed to catch seeded counterexample: {defect_name}"
    codes = {v.code for v in mutated.violations}
    assert expected_code in codes, f"Expected {expected_code}, got {codes}"


def _judge_doc_with_ollama(model: str, doc_bundle: str) -> DocRubricScore:
    prompt = (
        "You are a Staff AI QA & Systems Architect interviewer evaluating a GitHub repository's "
        "technical documentation. Score strictly from 1 to 5 on:\n"
        "- completeness: covers problem, architecture, formal invariants, and verification.\n"
        "- style_consistency: crisp senior engineering prose, consistent terminology, no fluff.\n"
        "- interviewer_market_value: demonstrates high-signal AI QA / formal verification rigor.\n"
        "Return ONLY valid JSON matching the schema.\n\n"
        f"DOCUMENTATION:\n{doc_bundle[:2800]}"
    )
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "format": DocRubricScore.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0.0, "seed": 42, "num_ctx": 2048, "num_predict": 160},
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    raw = json.loads(resp.json()["response"])
    return DocRubricScore.model_validate(raw)


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
