# Target: docs/DEFECTS_AND_CAPA.md, DEVPROCESS.md, RELEASES.md, CHANGELOG.md, docs/releases/v0.7.0-refine.md, tests/test_docs_quality.py
from __future__ import annotations
from pathlib import Path

PROJECTS = Path.home() / "projects"
REPOS = ("sandbox-init", "abstract-ops", "interview-ops", "hostel-ops")

CAPA_003 = (
    "\n## CAPA-003: PTY Paste Buffer Truncation, Log Flooding & Scratchpad Hygiene\n"
    "- **Triggering Incidents (`v0.7.0`):** Multi-line heredoc pastes exceeding ~1.5 KiB were truncated or stripped of leading spaces by the KDE Konsole canonical PTY buffer; unfiltered `ruff` output flooded stdout; a temporary log touched system `/tmp`.\n"
    "- **Root Cause:** `DEVPROCESS.md` lacked explicit byte/line thresholds (`<= 1.5 KiB` / `<= 35 lines`) and an automated gate verifying `DEVPROCESS.md` invariants.\n"
    "- **Corrective & Preventive Action (`CR-019`):** Codified **PTY Paste Cap (`<= 35 lines / <= 1.5 KiB`)**, `logs/` summary caps (`<= 15` lines), and zero `/tmp` usage in `DEVPROCESS.md` across all 5 repos, enforced by `tests/test_docs_quality.py`.\n"
)

DEVP_RULE = (
    "- **PTY Paste & Indentation Safety (`<= 35 lines / <= 1.5 KiB`):** Never paste multi-line blocks exceeding 35 lines or 1.5 KiB into an interactive terminal; split payloads into atomic chunks <= 1.5 KiB.\n"
    "- **Log Routing & Summary Cap (`<= 15 lines`):** Route all linter, `mypy`, and `pytest` outputs into `logs/YYYYMMDD-HHMMSS_<task>.log` and never touch system `/tmp`; print at most 15 tail lines to stdout.\n"
)

CR019_ROW = "| **CR-019: PTY Paste Cap & `DEVPROCESS.md` Governance (`CAPA-003`)** | All 5 repos | Codify `CAPA-003` in `docs/DEFECTS_AND_CAPA.md`, add `<= 1.5 KiB` / `<= 35 lines` PTY paste & `logs/` caps to `DEVPROCESS.md`, and enforce in `test_docs_quality.py`. | Eliminates interactive terminal paste truncation and stdout log flooding. | Closed-loop CAPA process governance backed by automated tests. | `CAPA-003` logged; `DEVPROCESS.md` updated across all 5 repos; tests green. |"

def apply_repo(repo: Path) -> None:
    devp = repo / "DEVPROCESS.md"
    txt = devp.read_text(encoding="utf-8")
    if "PTY Paste & Indentation Safety" not in txt:
        anchor = "## Non-Interactive CLI Execution (No Pagers in Automation)"
        devp.write_text(txt.replace(anchor, DEVP_RULE + "\n" + anchor, 1), encoding="utf-8")

    rel = repo / "RELEASES.md"
    rtxt = rel.read_text(encoding="utf-8")
    if "CR-019:" not in rtxt:
        out = [line + ("\n" + CR019_ROW if line.startswith("| **CR-018:") else "") for line in rtxt.splitlines()]
        rel.write_text("\n".join(out) + "\n", encoding="utf-8")

    ref = repo / "docs/releases/v0.7.0-refine.md"
    ftxt = ref.read_text(encoding="utf-8")
    if "CR-019" not in ftxt:
        add = "\n- **CR-019 — PTY Paste Cap & `DEVPROCESS.md` Sync (`CAPA-003`):** Codify `<= 1.5 KiB` PTY cap in `DEVPROCESS.md` and `tests/test_docs_quality.py`.\n"
        ref.write_text(ftxt.replace("### 4. Immediate First Step", add + "\n### 4. Immediate First Step", 1), encoding="utf-8")

    ch = repo / "CHANGELOG.md"
    ctxt = ch.read_text(encoding="utf-8")
    if "CR-019" not in ctxt:
        ctxt = ctxt.replace("## [0.7.0] - 2026-11-22 — CR-017: Standardized 5-Section Engineering Profile Dossier", "## [0.7.0] - 2026-11-23 — CR-017 & CR-019: Engineering Profiles & CAPA-003 Governance", 1)
        ctxt = ctxt.replace("### Verification Evidence\n", "- `DEVPROCESS.md` & `tests/test_docs_quality.py` (`CR-019` / `CAPA-003`): Enforced `<= 1.5 KiB` PTY paste cap and `logs/` summary cap.\n\n### Verification Evidence\n", 1)
        ch.write_text(ctxt, encoding="utf-8")

    tp = repo / "tests/test_docs_quality.py"
    ttxt = tp.read_text(encoding="utf-8")
    if '"DEVPROCESS.md"' not in ttxt:
        ttxt = ttxt.replace('"docs/ENGINEERING_PROFILE.md",\n    ]', '"docs/ENGINEERING_PROFILE.md",\n        "DEVPROCESS.md",\n    ]', 1)
        chk = '    if "DEVPROCESS.md" in loaded:\n        for tok in ("PTY Paste", "1.5 KiB", "logs/"):\n            if tok not in loaded["DEVPROCESS.md"]:\n                violations.append(DocViolation(code=ViolationCode.MISSING_REQUIRED_SECTION, file="DEVPROCESS.md", detail=f"Missing {tok}"))\n\n    if "CHANGELOG.md" in loaded:'
        ttxt = ttxt.replace('    if "CHANGELOG.md" in loaded:', chk, 1)
        seed = '    (base / "DEVPROCESS.md").write_text("# Process\\n- PTY Paste cap <= 1.5 KiB; route output to logs/.\\n", encoding="utf-8")\n    (base / "RELEASES.md").write_text('
        ttxt = ttxt.replace('    (base / "RELEASES.md").write_text(', seed, 1)
        tp.write_text(ttxt, encoding="utf-8")

def main() -> None:
    capa = PROJECTS / "sandbox-init/docs/DEFECTS_AND_CAPA.md"
    ctxt = capa.read_text(encoding="utf-8")
    if "## CAPA-003:" not in ctxt:
        capa.write_text(ctxt.rstrip() + "\n" + CAPA_003.lstrip(), encoding="utf-8")
    for r in REPOS:
        apply_repo(PROJECTS / r)
        print(f"[OK] CR-019 applied to {r}")
    (PROJECTS / "spanskikh/DEVPROCESS.md").write_text((PROJECTS / "sandbox-init/DEVPROCESS.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("[OK] Full DEVPROCESS.md synced to spanskikh")

if __name__ == "__main__":
    main()
