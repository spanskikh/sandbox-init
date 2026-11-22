# Engineering & AI-Assisted Development Process (`DEVPROCESS.md`)

Normative standard governing release lifecycle, traceability, document roles, quality gates, and human-AI collaboration across `sandbox-init`, `abstract-ops`, `interview-ops`, and `hostel-ops`.

---

## 1. Traceability & Zero-Orphan Artifact Rule
- **Mandatory Change Request (`CR-XXX`):** No code, test, or process document may enter `main` without an assigned `CR-XXX` registered in `RELEASES.md` and `docs/releases/vX.Y.Z-refine.md`.
- **Defect & CAPA Rule (`BUG-XXX` / `CAPA-XXX`):** Any discovered defect or recurring process failure halts new feature work until root cause, regression test, and cross-repo preventive rule are logged in `docs/DEFECTS_AND_CAPA.md`.
- **Git Tagging & Branching:** Develop on `feat/cr-XXX-<slug>`, merge via `git merge --no-ff --no-edit`, and tag releases with `git -c tag.gpgSign=false tag -a vX.Y.Z -m "Release vX.Y.Z: CR-AAA..CR-BBB"`.

---

## 2. Release Lifecycle & Scrum Gates (`1 Release = 1 Chat Session`)
1. **Opening Gate (`Retro` + `Refine` + `RELEASES.md`):**
   - Author `docs/releases/v{prev}-retrospective.md` with four required sections: `Lessons Learned`, `Rejected Ideas`, `Unlucky Probe-Runs`, and `Release Chat Digest`.
   - Author `docs/releases/vX.Y.Z-refine.md` decomposing planned `CR-XXX` items, architectural learning value, and formal `Definition of Done (DoD)`.
   - Register release **Business Goal** and CR contribution rows in `RELEASES.md`.
2. **Execution Gate (`CR-XXX`):**
   - Persist incremental scripts/patches in `docs/dev-log/YYYYMMDD-HHMMSS_<cr-id>_<slug>.(sh|py|patch)` with an explicit `# Target: <relative_path>` header.
3. **Verification & Closure Gate:**
   - Execute checks via `./scripts/run_logged.sh <task> -- <cmd>` (`.venv/bin/ruff check src tests`, `.venv/bin/mypy src tests --strict`, `.venv/bin/pytest -v -m "not integration"`).
   - Record verified metrics and log artifact paths in `CHANGELOG.md`, tag `vX.Y.Z`, and push `main` + tags.

---

## 3. Language & Document Role Policy
- **Chat vs. Git Language Split:** Interactive chat discussions with AI collaborators may be conducted in Russian or English, but **all Git-tracked files** (code, docstrings, comments, `README.md`, `RELEASES.md`, `CHANGELOG.md`, `DEVPROCESS.md`, `docs/releases/*`, `docs/dev-log/*`) must be written **strictly in English** (enforced by `LANGUAGE_DRIFT_CYRILLIC` in `tests/test_docs_quality.py`).
- **Public Showcase (`README.md`, `RELEASES.md`, `CHANGELOG.md`, `DEVPROCESS.md`, `docs/ARCHITECTURE.md`, `docs/DEFECTS_AND_CAPA.md`):** Enforced by deterministic AST/Markdown checks + 9 seeded mutation counterexamples + local `Ollama` rubric (`>= 4/5`).
- **Forensic Audit (`docs/releases/*`, `docs/dev-log/*`):** Versioned in Git for engineering due diligence.
- **Ephemeral Execution Logs (`logs/YYYYMMDD-HHMMSS_<task>.{stdout,stderr,log}`):** Gitignored (`logs/`); verified by `tests/test_run_logged.py`.

---

## 4. Tooling, Shell Safety & AI-Collaboration Protocol
- **Local Toolchain & Workspace Scratchpad:** Always use `.venv/bin/ruff`, `.venv/bin/mypy --strict`, and `.venv/bin/pytest` (never `uv` or paid cloud APIs). Place temporary helper scripts in `~/projects/tmp/` rather than system `/tmp`.
- **Interactive Shell Hygiene:** Never paste `set -e` into multi-line interactive `bash` commands (use `|| break` in loops). Keep `core.pager = "less -FRX"` and `GIT_PAGER=cat`.
- **Zero-Guesswork Contract Rule:** Never guess Pydantic field names or `@mcp.tool()` signatures; inspect `models.py` and `server.py` first before writing tests.
- **Compact Exchange Protocol:** Deliver new modules/tests as clean code blocks with `Target: <relative_path>` headers rather than giant shell heredocs, and paste only compact 5–10 line summaries from `logs/*.log` into chat.
