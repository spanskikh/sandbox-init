# Engineering Profile — `sandbox-init`

> **Architectural Role:** Foundational Neuro-Symbolic Verification Harness & Cluster Control Plane (`A1` Maturity Baseline)

## 1. Concepts and Theories
- **Neuro-Symbolic Verification & Bounded Model Checking:** Treats probabilistic LLM outputs as untrusted hypotheses gated by formal SMT (`Z3`) satisfiability (`SAT` / `UNSAT`) proofs before state mutation.
- **Design by Contract (DbC) & Type-Driven Invariants:** Enforces strict structural pre-/post-conditions via `Pydantic v2` schemas paired with linear arithmetic and boolean resource constraints (`CPU`, `RAM`, `disk_gb`, timeout budgets).
- **Automated Documentation & Hygiene Governance:** Applies static regex/AST drift detection (`LANGUAGE_DRIFT_CYRILLIC`, `PLACEHOLDER_LEAK`, `BROKEN_MERMAID_BLOCK`, `BROKEN_RELATIVE_LINK`) and an `Ollama` LLM-as-a-Judge rubric (`>= 4/5` across completeness, style consistency, and market signal).
- **Software Supply-Chain Transparency:** Generates deterministic `CycloneDX` Software Bills of Materials (`SBOM`) on every CI run to guarantee reproducible dependency provenance.

## 2. Frameworks and Libraries
| Layer | Technology | Version / Spec | Role in `sandbox-init` |
| :--- | :--- | :--- | :--- |
| **Formal Solver** | `z3-solver` | `>=4.13.0` | Proves hardware/sandbox resource allocation invariants (`SAT` vs `UNSAT` counterexamples). |
| **Data & Contracts** | `pydantic` | `>=2.9.0` (v2) | Strict boundary validation, JSON schema export for structured LLM outputs, audit report models. |
| **Agent Protocol** | `fastmcp` | `>=2.0.0` | Exposes deterministic verification tools over JSON-RPC `stdio` transport. |
| **Analytical Store** | `duckdb` | `>=1.1.0` | Local embedded telemetry and execution audit persistence without external server overhead. |
| **HTTP & Local LLM** | `httpx` | `>=0.28.0` | Synchronous/async client for local `Ollama` structured JSON rubric evaluation. |
| **Test & Static QA** | `pytest`, `hypothesis`, `mypy`, `ruff` | Python `>=3.12` | Unit/contract/property test execution, `--strict` static type checking, lint enforcement. |

## 3. Dev Tools and Environment
- **Operating System & Compute Topology:** Calculate Linux Desktop (KDE, Kernel `6.18+`) running on dual Intel Core i5-9500 (6C/6T, AVX2) workstation nodes (`24 GiB` and `16 GiB` DDR4 RAM) over dedicated Gigabit Ethernet.
- **Local Inference & Storage:** Local `Ollama` daemon (`127.0.0.1:11434`) for offline LLM rubric checks; NVMe/SATA SSD storage with `zram` swap compression.
- **Authoring & Diagramming:** `Emacs` (`org-babel`), `VS Code`, `Mermaid` live-validated architecture diagrams, `git` with branch-per-CR workflow (`--no-ff` merges).
- **CI/CD & Artifact Pipeline:** GitHub Actions (`.github/workflows/ci.yml`) executing `ruff`, `mypy --strict`, `pytest -m "not integration"`, and `cyclonedx-py` SBOM generation.

## 4. Processes and Procedures
- **Change Request (CR) Traceability:** Every feature or invariant change is tracked end-to-end across `RELEASES.md`, `CHANGELOG.md`, `docs/ARCHITECTURE.md`, and `docs/dev-log/YYYYMMDD-HHMMSS_cr-XXX_<slug>.(py|md)`.
- **Private-First Release Gate (`DEVPROCESS.md`):** New repositories and major milestones are validated locally against `tests/test_release_hygiene.py` (blocking secrets, PII, local host paths, and runtime artifacts) prior to public GitHub visibility or CI activation.
- **Corrective & Preventive Action (`CAPA`):** Root-cause defects and defect-escape prevention rules are formally cataloged in `docs/DEFECTS_AND_CAPA.md` (`BUG-XXX` / `CAPA-XXX`).
- **Release Closure Protocol:** Each release closes with a structured retrospective (`docs/releases/vX.Y.Z-retrospective.md`) capturing lessons learned, rejected ideas, and unlucky probe-runs.

## 5. Test Approach, Tools, Environment & Metrics
- **Verification Pyramid:**
  1. *Static & Hygiene Gates:* `ruff check`, `mypy --strict` (`16` source files, `0` issues), `tests/test_release_hygiene.py`.
  2. *Formal & Property Oracles:* `Z3` resource invariant checks + `Hypothesis` property fuzzing + seeded documentation defect counterexamples (`9` parametrized defect classes).
  3. *Protocol & Integration Gates:* `FastMCP` `stdio` JSON-RPC client contract tests + `@pytest.mark.integration` live `Ollama` rubric audit (`>= 4/5` threshold).
- **Empirical Baseline Metrics (`v0.6.0` -> `v0.7.0`):**
  - **Offline Fast Suite:** `30 passed` (`< 3.5 s` on local CPU), `0` type errors across `16` source files.
  - **Defect Detection Precision:** `100%` catch rate on seeded documentation/hygiene counterexamples (`MISSING_REQUIRED_FILE`, `LANGUAGE_DRIFT_CYRILLIC`, `PLACEHOLDER_LEAK`, `BROKEN_MERMAID_BLOCK`, `BROKEN_RELATIVE_LINK`).
  - **Supply Chain:** `100%` CI builds produce a validated `CycloneDX` JSON SBOM artifact.
