# Changelog

All notable changes and formal Change Requests (CRs) for `sandbox-init` are documented in this file.

## [0.9.1] - 2026-11-23 — BUG-005: Hosted CI Python Interpreter Fallback in `run_integration.sh`
### Objective & Risk Mitigated
- **Closed Residual Risk:** Fixed GitHub Actions CI failure (run `45188880471`, `BUG-005`) where `scripts/run_integration.sh` hardcoded `.venv/bin/python` and `tests/test_topology.py::test_run_integration_script_dry_run` stripped the active interpreter directory from `PATH` on hosted runners without a local `.venv`.
- **Traceability:** Defect fix `BUG-005` (`CR-024` follow-up) in `sandbox-init` (`scripts/run_integration.sh`, `tests/test_topology.py`, `CHANGELOG.md`).

### Added & Changed
- `scripts/run_integration.sh` (`BUG-005` / `CR-024`): Replaced hardcoded `TOPOLOGY_PY` with `PYTHON_BIN` resolution preferring `.venv/bin/python` when executable and falling back cleanly to `PYTHON_BIN` override, `python3`, or `python`, failing fast if topology export fails.
- `tests/test_topology.py` (`BUG-005` / `CR-024`): Updated `test_run_integration_script_dry_run` to pass `PYTHON_BIN=sys.executable` and include `Path(sys.executable).resolve().parent` in `PATH` so `--dry-run` succeeds both inside local `.venv` and on hosted CI runners.

### Verification Evidence
- `./scripts/run_logged.sh bug005_verify -- bash -c '.venv/bin/ruff check src tests && .venv/bin/mypy src tests --strict && .venv/bin/pytest -v -m "not integration"'`: `All checks passed!`, `Success: no issues found in 23 source files`, `53 passed, 3 deselected`.
- `PYTHON_BIN=.venv/bin/python3 ./scripts/run_integration.sh --dry-run`: Verified topology `--dry-run` override without hardcoded `.venv/bin/python`.

## [0.9.0] - 2026-11-23 — CR-026: Shared `CycloneDX` PEP 610 `file://` Sanitizer CLI
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated duplicated inline PEP 610 `file://` SBOM sanitization one-liners across CI workflows and test suites (`BUG-004` / `CAPA-007`), centralizing deterministic `CycloneDX` `externalReferences` scrubbing and `/home/` / `/Users/` host-path hygiene enforcement into a single reusable module and CLI.
- **Traceability:** Change Request `CR-026` implemented in `sandbox-init` (`src/sandbox_init/sbom.py`, `scripts/sanitize_sbom.sh`, `tests/test_sbom_sanitizer.py`, `tests/test_sbom_and_contracts.py`, `.github/workflows/ci.yml`, `docs/dev-log/20261123-135200_cr-026_cyclonedx-sbom-sanitizer.py`).

### Added & Changed
- `src/sandbox_init/sbom.py` (`CR-026` / `CAPA-007`): Added `SbomSanitizeReport` (`Pydantic v2`), `sanitize_cyclonedx_bom`, `verify_sanitized_bom`, `sanitize_sbom_file`, `generate_and_sanitize_sbom`, and `python -m sandbox_init.sbom` CLI (`--input`, `--output`, `--generate`, `--verify`, `--require-pkg`, `--format json|summary`) stripping PEP 610 `file://` URIs across top-level, metadata, and nested components.
- `scripts/sanitize_sbom.sh`, `.github/workflows/ci.yml`, `tests/test_sbom_and_contracts.py`, & `tests/test_sbom_sanitizer.py` (`CR-026` / `CAPA-003`): Added executable multi-repo SBOM sanitizer runner (`--dry-run`, `--all-repos`, `PAGER=cat`, `<= 15` summary lines via `./scripts/run_logged.sh`), wired CI and reproducibility gates to `sandbox_init.sbom`, and added 5 unit/CLI/idempotency tests.

### Verification Evidence
- `./scripts/run_logged.sh cr026_ruff -- .venv/bin/ruff check src tests`: `All checks passed!` (`0` errors).
- `./scripts/run_logged.sh cr026_mypy -- .venv/bin/mypy src tests --strict`: `Success: no issues found in 23 source files`.
- `./scripts/run_logged.sh cr026_pytest -- .venv/bin/pytest -v -m "not integration"`: `53 passed, 3 deselected`.
- `./scripts/sanitize_sbom.sh --dry-run` & `./scripts/sanitize_sbom.sh --all-repos`: `4/4` cluster repositories sanitized into `~/projects/tmp/*.sbom.cdx.json` with `verified=True` and `0` `file://` or host-path leaks.

## [0.9.0] - 2026-11-23 — CR-025: Cross-Repo `FastMCP` `stdio` Supervisor/Worker Orchestrator
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated unverified multi-agent handoff gaps across the 4-repository neuro-symbolic cluster by introducing a single-command `FastMCP` `stdio` Supervisor/Worker orchestrator (`sandbox-init -> abstract-ops -> interview-ops -> hostel-ops`) with deterministic Z3 `SAT`/`UNSAT` gating at every inter-agent hop and zero `stdout` banner pollution.
- **Traceability:** Change Request `CR-025` implemented in `sandbox-init` (`src/sandbox_init/orchestrator.py`, `scripts/run_supervisor_chain.sh`, `tests/test_orchestrator.py`, `docs/dev-log/20261123-133300_cr-025_supervisor-worker-orchestrator.py`).

### Added & Changed
- `src/sandbox_init/orchestrator.py` (`CR-025` / `CAPA-002`): Added `WorkerHopResult` and `OrchestrationReport` (`Pydantic v2`), `build_default_sat_payloads`, `build_unsat_payloads`, `run_supervisor_chain`, and `--scenario sat|unsat-*|all` CLI orchestrating `check_cluster_plan`, `audit_policy_ruleset`, `audit_cv_proposal`, and `audit_hostel_checkin` over `FastMCP` `stdio` while preserving 12-tool namespace disjointness.
- `scripts/run_supervisor_chain.sh` & `tests/test_orchestrator.py` (`CR-025` / `CAPA-003`): Added executable single-command Supervisor/Worker chain runner (`--dry-run`, `PAGER=cat`, `<= 15` summary lines via `./scripts/run_logged.sh`) and 8 offline contract test executions covering `SAT` nominal progression, per-hop `UNSAT` counterexample short-circuiting, `--no-short-circuit` aggregation, and isolated single-repo fallback.

### Verification Evidence
- `./scripts/run_logged.sh cr025_ruff -- .venv/bin/ruff check src tests`: `All checks passed!` (`0` errors).
- `./scripts/run_logged.sh cr025_mypy -- .venv/bin/mypy src tests --strict`: `Success: no issues found in 21 source files`.
- `./scripts/run_logged.sh cr025_pytest -- .venv/bin/pytest -v -m "not integration"`: `48 passed, 3 deselected`.
- `./scripts/run_supervisor_chain.sh --scenario all --format summary`: `5/5` (`1` full 4-hop `SAT` + `4` per-hop `UNSAT` short-circuit proofs) verified over `FastMCP` `stdio`.

## [0.9.0] - 2026-11-23 — CR-024: Host/Docker Topology-Aware Integration Runner
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated host vs. Docker network and filesystem topology mismatches (`http://ollama:11434`, `host.docker.internal:15432`, `/app/data/*.duckdb`) that required manual `.env` overrides when running live `@pytest.mark.integration` verification across `hippo` and `rhino`.
- **Traceability:** Change Request `CR-024` implemented in `sandbox-init` (`src/sandbox_init/topology.py`, `scripts/run_integration.sh`, `tests/test_topology.py`, `docs/dev-log/20261123-125200_cr-024_topology-integration-runner.py`).

### Added & Changed
- `src/sandbox_init/topology.py` (`CR-024`): Added `TopologyConfig` (`Pydantic v2`), `detect_runtime_topology`, `resolve_topology_config`, `build_topology_env`, and `--format env|json` CLI rewriting container endpoints (`ollama`, `host.docker.internal`, `/app/data/*`) to host-reachable `127.0.0.1` and `<repo_root>/data/*` while preserving explicit non-container overrides.
- `src/sandbox_init/server.py`, `src/sandbox_init/cegis.py`, `tests/test_cluster_live_smoke.py`, `tests/test_docs_quality.py` (`CR-024` / `CAPA-002`): Wired default `DB_PATH`, `OLLAMA_URL`, `PG_HOST`, and `PG_PORT` through `resolve_topology_config()` while preserving the 4-tool FastMCP contract and English-only docstrings.
- `scripts/run_integration.sh` & `tests/test_topology.py` (`CR-024` / `CAPA-003`): Added executable topology-aware integration runner (`--dry-run`, `--all-repos`, `PAGER=cat`, `<= 15` summary lines via `./scripts/run_logged.sh`) and 6 unit/CLI tests.

### Verification Evidence
- `./scripts/run_logged.sh cr024_ruff -- .venv/bin/ruff check src tests`: `All checks passed!` (`0` errors).
- `./scripts/run_logged.sh cr024_mypy -- .venv/bin/mypy src tests --strict`: `Success: no issues found in 19 source files`.
- `./scripts/run_logged.sh cr024_pytest_offline -- .venv/bin/pytest -v -m "not integration"`: `40 passed, 3 deselected`.
- `./scripts/run_integration.sh --dry-run` & `./scripts/run_integration.sh`: `3 passed` against live `hippo` Ollama and `rhino` PostgreSQL (`127.0.0.1:15432`).

## [0.8.0] - 2026-11-23 — CR-022 & CR-023: Cross-Cluster Z3 Contract, SBOM Gate & Rubric Sign-Off
### Objective & Risk Mitigated
- **Closed Residual Risk:** Enforced cross-cluster Z3 RAM budget invariants (`hippo` 24 GiB / `rhino` 16 GiB), 12-tool FastMCP namespace disjointness, deterministic `CycloneDX` SBOM reproducibility, and grammar-constrained live Ollama documentation rubric evaluation (`>= 4/5`).
- **Traceability:** Change Requests `CR-022` and `CR-023` (`BUG-003` / `CAPA-006`) merged via `--no-ff`; release `v0.8.0`.

### Added & Changed
- `pyproject.toml` & `.github/workflows/ci.yml` (`CR-022`): Bump version to `0.8.0`, add `cyclonedx-bom>=7.2.0`, and verify two-run `CycloneDX` SBOM determinism and path hygiene in CI.
- `tests/test_sbom_and_contracts.py` (`CR-022`): Cross-cluster Z3 SAT/UNSAT budget solver, 12-tool FastMCP namespace disjointness check, and `CycloneDX` SBOM reproducibility gate.
- `tests/test_docs_quality.py` (`CR-023` / `BUG-003` / `CAPA-006`): Upgraded `_judge_doc_with_ollama` to JSON Schema grammar-constrained decoding (`DocRubricScore.model_json_schema()`, `temperature=0.0`, `timeout=180.0`).

### Verification Evidence
- `ruff check src tests` & `mypy src tests --strict`: `0` issues across all source and test modules.
- `pytest -m "not integration"`: `34 passed` (including `CR-022` Z3 cluster and `CycloneDX` SBOM gates).
- `pytest -v -m integration`: `3 passed` against live `hippo` Ollama (`qwen2.5-coder:7b`) and `rhino` PostgreSQL.

## [0.7.0] - 2026-11-23 — CR-017..CR-021: Engineering Profiles, SSoT Governance & Auditor Fix
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated cross-repository inconsistency in how theoretical foundations, library versions, workstation environment, SDLC/QA processes, and empirical benchmark metrics are presented to technical reviewers; enforced structural compliance via automated AST/regex quality gates.
- **Traceability:** Change Request `CR-017` implemented across `sandbox-init` (`docs/ENGINEERING_PROFILE.md`, `README.md`, `tests/test_docs_quality.py`, `RELEASES.md`).

### Added
- `docs/ENGINEERING_PROFILE.md`: Standardized 5-section engineering dossier (`1. Concepts and Theories`, `2. Frameworks and Libraries`, `3. Dev Tools and Environment`, `4. Processes and Procedures`, `5. Test Approach, Tools, Environment & Metrics`).
- `README.md`: Added direct navigation link to `docs/ENGINEERING_PROFILE.md`.
- `tests/test_docs_quality.py`: Added mandatory file, 5-heading structural assertions, signal density checks, and `2` new seeded defect counterexamples (`missing_engineering_profile`, `missing_profile_section`).

- `DEVPROCESS.md` & `tests/test_docs_quality.py` (`CR-019` / `CAPA-003`): Enforced `<= 1.5 KiB` PTY paste cap and `logs/` summary cap.

- `README.md` & SSoT Migration (`CR-020` / `CAPA-004`): Consolidated shared governance docs (`DEVPROCESS.md`, `RELEASES.md`, `docs/DEFECTS_AND_CAPA.md`, `docs/releases/*`) into `spanskikh/spanskikh` and linked canonical URLs.
- `tests/test_docs_quality.py` (`CR-021` / `BUG-002` / `CAPA-005`): Fixed Markdown auditor to scan all tracked `*.md` files recursively for Cyrillic/placeholders and enforce `CLUSTER_DOC_DUPLICATE`.

### Verification Evidence
- `ruff check .` & `mypy --strict`: `0` issues across all source and test modules.
- `pytest -m "not integration"`: All unit, contract, hygiene, and documentation quality tests green (`+2` new counterexample cases).

## [0.6.0] - 2026-11-22 — CR-014, CR-015 & CR-016: Pre-Public Hygiene Gate, Portfolio Sync & Public CI / CycloneDX Activation
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated secret, PII, workstation path, and runtime artifact leakage risks prior to making repositories public, synchronized showcase documentation with verified `v0.5.0` metrics, and activated GitHub Actions CI + `CycloneDX` SBOM generation.
- **Traceability:** Branches `feat/cr-014-release-hygiene-gate` (`bcb0c80`), `feat/cr-015-portfolio-landing-sync` (`fd3c506`), and `CR-016` CI promotion merged via `--no-ff`; releases `v0.6.0`.

### Added
- `tests/test_release_hygiene.py`: Tracked-file scanner blocking secrets, tokens, private keys, real phone numbers, `/home/<user>/` paths, and `.duckdb`/`.log`/`.env` files, plus staged CI and `publish_to_github.sh` verification.
- `docs/ci/ci.yml` -> `.github/workflows/ci.yml` & `scripts/publish_to_github.sh`: Deterministic GitHub Actions pipeline (`ruff`, `mypy --strict`, `pytest -m "not integration"`, `cyclonedx-py` SBOM artifact upload).
- `README.md` & `docs/ARCHITECTURE.md`: Synchronized cluster-wide QA benchmarks and risk controls for public release.

### Verification Evidence
- `./scripts/run_logged.sh cr015_ruff`: `All checks passed!`
- `./scripts/run_logged.sh cr015_mypy`: `Success: no issues found in 16 source files`
- `./scripts/run_logged.sh cr015_pytest`: `30 passed, 3 deselected`

## [0.6.0] - 2026-11-22 — CR-014, CR-015 & CR-016: Pre-Public Hygiene Gate, Portfolio Sync & Public CI / CycloneDX Activation
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated secret, PII, workstation path, and runtime artifact leakage risks prior to making repositories public, synchronized showcase documentation with verified `v0.5.0` metrics, and activated GitHub Actions CI + `CycloneDX` SBOM generation.
- **Traceability:** Branches `feat/cr-014-release-hygiene-gate` (`bcb0c80`), `feat/cr-015-portfolio-landing-sync` (`fd3c506`), and `CR-016` CI promotion merged via `--no-ff`; releases `v0.6.0`.

### Added
- `tests/test_release_hygiene.py`: Tracked-file scanner blocking secrets, tokens, private keys, real phone numbers, `/home/<user>/` paths, and `.duckdb`/`.log`/`.env` files, plus staged CI and `publish_to_github.sh` verification.
- `docs/ci/ci.yml` -> `.github/workflows/ci.yml` & `scripts/publish_to_github.sh`: Deterministic GitHub Actions pipeline (`ruff`, `mypy --strict`, `pytest -m "not integration"`, `cyclonedx-py` SBOM artifact upload).
- `README.md` & `docs/ARCHITECTURE.md`: Synchronized cluster-wide QA benchmarks and risk controls for public release.

### Verification Evidence
- `./scripts/run_logged.sh cr015_ruff`: `All checks passed!`
- `./scripts/run_logged.sh cr015_mypy`: `Success: no issues found in 16 source files`
- `./scripts/run_logged.sh cr015_pytest`: `30 passed, 3 deselected`

## [0.6.0] - 2026-11-22 — CR-014, CR-015 & CR-016: Pre-Public Hygiene Gate, Portfolio Sync & Public CI / CycloneDX Activation
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated secret, PII, workstation path, and runtime artifact leakage risks prior to making repositories public, synchronized showcase documentation with verified `v0.5.0` metrics, and activated GitHub Actions CI + `CycloneDX` SBOM generation.
- **Traceability:** Branches `feat/cr-014-release-hygiene-gate` (`bcb0c80`), `feat/cr-015-portfolio-landing-sync` (`fd3c506`), and `CR-016` CI promotion merged via `--no-ff`; releases `v0.6.0`.

### Added
- `tests/test_release_hygiene.py`: Tracked-file scanner blocking secrets, tokens, private keys, real phone numbers, `/home/<user>/` paths, and `.duckdb`/`.log`/`.env` files, plus staged CI and `publish_to_github.sh` verification.
- `docs/ci/ci.yml` -> `.github/workflows/ci.yml` & `scripts/publish_to_github.sh`: Deterministic GitHub Actions pipeline (`ruff`, `mypy --strict`, `pytest -m "not integration"`, `cyclonedx-py` SBOM artifact upload).
- `README.md` & `docs/ARCHITECTURE.md`: Synchronized cluster-wide QA benchmarks and risk controls for public release.

### Verification Evidence
- `./scripts/run_logged.sh cr015_ruff`: `All checks passed!`
- `./scripts/run_logged.sh cr015_mypy`: `Success: no issues found in 16 source files`
- `./scripts/run_logged.sh cr015_pytest`: `30 passed, 3 deselected`

## [0.6.0] - 2026-11-22 — CR-014, CR-015 & CR-016: Pre-Public Hygiene Gate, Portfolio Sync & Public CI / CycloneDX Activation
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated secret, PII, workstation path, and runtime artifact leakage risks prior to making repositories public, synchronized showcase documentation with verified `v0.5.0` metrics, and activated GitHub Actions CI + `CycloneDX` SBOM generation.
- **Traceability:** Branches `feat/cr-014-release-hygiene-gate` (`bcb0c80`), `feat/cr-015-portfolio-landing-sync` (`fd3c506`), and `CR-016` CI promotion merged via `--no-ff`; releases `v0.6.0`.

### Added
- `tests/test_release_hygiene.py`: Tracked-file scanner blocking secrets, tokens, private keys, real phone numbers, `/home/<user>/` paths, and `.duckdb`/`.log`/`.env` files, plus staged CI and `publish_to_github.sh` verification.
- `docs/ci/ci.yml` -> `.github/workflows/ci.yml` & `scripts/publish_to_github.sh`: Deterministic GitHub Actions pipeline (`ruff`, `mypy --strict`, `pytest -m "not integration"`, `cyclonedx-py` SBOM artifact upload).
- `README.md` & `docs/ARCHITECTURE.md`: Synchronized cluster-wide QA benchmarks and risk controls for public release.

### Verification Evidence
- `./scripts/run_logged.sh cr015_ruff`: `All checks passed!`
- `./scripts/run_logged.sh cr015_mypy`: `Success: no issues found in 16 source files`
- `./scripts/run_logged.sh cr015_pytest`: `30 passed, 3 deselected`

## [0.5.0] - 2026-11-22 — CR-010, CR-011 & CR-013: FastMCP `stdio` Contract Harness, RAG DuckDB Telemetry & `DEVPROCESS.md`
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated unverified JSON-RPC `stdio` tool boundary drift, cross-session process/schema guesswork (`CAPA-002`), and missing cross-repo IR benchmark telemetry storage in `DuckDB`.
- **Traceability:** Branches `feat/cr-010-mcp-stdio-contracts` (`6166600`), `feat/cr-011-rag-benchmark-telemetry` (`f1716c7`), and `CR-013` (`DEVPROCESS.md` + `CAPA-002`) merged via `--no-ff`; releases `v0.5.0`.

### Added
- `tests/test_mcp_contracts.py`: Real `mcp.client.stdio` JSON-RPC discovery (`list_tools()`), input JSON schema verification, `SAT`/`UNSAT` Z3 verdicts, and Pydantic `ValidationError` rejection across all 4 exposed `FastMCP` tools (`check_cluster_allocation`, `check_cluster_plan`, `synthesize_valid_allocation`, `record_node_memory_telemetry`).
- `src/sandbox_init/contracts.py` & `src/sandbox_init/store.py`: Added `RagBenchmarkTelemetry` Pydantic v2 contract and `rag_benchmarks` append-only telemetry table (`record_rag_benchmark`, `count_rag_benchmarks`) in `AuditStore` (`DuckDB`).
- `DEVPROCESS.md` & `docs/DEFECTS_AND_CAPA.md` (`CAPA-002`): Codified normative Scrum release gates, zero-orphan CR traceability, English-only Git policy, and `.venv/bin/` + `./scripts/run_logged.sh` standards.

### Verification Evidence
- `./scripts/run_logged.sh cr011_ruff` (`logs/20261122-154815_cr011_ruff.log`): `All checks passed!`
- `./scripts/run_logged.sh cr011_mypy` (`logs/20261122-154815_cr011_mypy.log`): `Success: no issues found in 15 source files`
- `./scripts/run_logged.sh cr011_pytest` (`logs/20261122-154816_cr011_pytest.log`): `22 passed, 3 deselected`

## [0.4.0] - 2026-11-22 — CR-009: Dev-Process Auditability, Execution Logging & Release Retrospectives
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated loss of iterative engineering history, unlogged local execution runs, and missing post-release retrospectives across `sandbox-init` by introducing deterministic `.stdout`/`.stderr`/`.log` capture, versioned `docs/dev-log/` artifacts, and mandatory release retrospectives enforced by automated mutation tests.
- **Traceability:** Branch `feat/cr-009-dev-process-auditability` merged via `--no-ff`; releases `v0.4.0`.

### Added
- `scripts/run_logged.sh` & `tests/test_run_logged.py`: POSIX execution wrapper capturing ISO-8601 start/end timestamps, duration, exit codes, and split `.stdout`, `.stderr`, and `.log` artifacts in gitignored `logs/`.
- `docs/dev-log/`: Versioned raw patch/script artifact history (`20261122-130500_cr-009_install-run-logged.sh`, `20261122-130800_cr-009_enforce-release-retrospectives.py`).
- `docs/releases/v0.3.0-retrospective.md` & `tests/test_docs_quality.py`: Post-release retrospective capturing Lessons Learned, Rejected Ideas, Unlucky Probe-Runs, and Release Chat Digest, enforced by an 8th seeded mutation counterexample (`missing_retrospective_section`).

### Verification Evidence
- `./scripts/run_logged.sh cr009_final_gate`: `ruff check src tests` (`All checks passed!`), `mypy src tests --strict` (`Success: no issues found`), `pytest -v -m "not integration"` (`18 passed, 3 deselected`).

## [0.3.0] - 2026-11-22 — CR-008: Documentation Quality Gates, Mutation Counterexamples & Live Rubric Evaluation
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated documentation drift, broken relative links, unclosed Mermaid diagrams, unresolved placeholders, and hollow marketing claims across `sandbox-init` through deterministic structural/style/market-value checks, 7 seeded negative mutation counterexamples, and live `Ollama` rubric grading.
- **Traceability:** Branch `feat/cr-008-docs-quality-tests` merged via `--no-ff`; releases `v0.3.0`.

### Added
- `tests/test_docs_quality.py`: `DocQualityAuditor` (`Pydantic v2`), 7 parametrized negative mutation counterexamples (`MISSING_REQUIRED_FILE`, `LANGUAGE_DRIFT_CYRILLIC`, `MISSING_REQUIRED_SECTION`, `PLACEHOLDER_LEAK`, `BROKEN_MERMAID_BLOCK`, `BROKEN_RELATIVE_LINK`, `LOW_MARKET_SIGNAL_OR_HYPE`), and `@pytest.mark.integration` live `Ollama` rubric test (`num_ctx=2048`, `num_predict=160`, `timeout=180.0` tuned for CPU inference on `hippo`).
- `pyproject.toml`: Standardized version `0.3.0`, `[project.optional-dependencies] dev`, `pythonpath = ["src"]`, and `@pytest.mark.integration` marker.

### Verification Evidence
- `ruff check src tests`: `All checks passed!`
- `mypy src tests --strict`: `Success: no issues found`
- `pytest -v -m "not integration"`: `16 passed, 3 deselected` (including all 7 seeded mutation counterexamples)
- `pytest -v -m "integration"`: `3 passed, 16 deselected` (live `Ollama` rubric >= 4/5 on real docs and <= 2/5 on weak counterexample)

### Planned Next (`v0.4.0` Backlog)
- **CR-009 (Dev-Process Auditability & Execution Logging):** Timestamped downloadable patch/script artifacts for raw engineering history alongside `scripts/run_logged.sh` capturing `.stdout`, `.stderr`, and combined `.log` with start/end ISO-8601 timestamps.

## [0.3.0-cr006] - 2026-11-22 — CR-006: Offline GitHub Actions CI & CycloneDX SBOM Blueprints
### Objective & Risk Mitigated
- **Closed Residual Risk:** Standardized pre-release verification (`ruff`, `mypy --strict`, `pytest -m "not integration"`) and supply-chain `CycloneDX` SBOM generation across `sandbox-init` without triggering premature CI runs while the repository remains private.
- **Traceability:** Branch `feat/cr-006-ci-blueprints` merged via `--no-ff`.

### Added
- `docs/ci/ci.yml`: Staged GitHub Actions workflow (`uv`, `ruff`, `mypy --strict`, `pytest`, `cyclonedx-py` SBOM artifact upload).
- `scripts/publish_to_github.sh`: Deterministic pre-flight and promotion script (`git mv docs/ci/ci.yml .github/workflows/ci.yml` + `gh repo edit --visibility public`).

### Verification Evidence
- `docs/ci/ci.yml` YAML indentation validated and staged cleanly; `.github/workflows/` kept absent until public release.

## [0.3.0] - 2026-11-22 — CR-005: OpenRC Persistent PG Tunnel & Live Cluster Smoke Suite
### Objective & Risk Mitigated
- **Closed Residual Risk:** Eliminated manual SSH port-forwarding fragility between `hippo` (`127.0.0.1:15432`) and `rhino` (`127.0.0.1:5432`) and established deterministic live E2E verification across PostgreSQL wire reachability, `Ollama` API, `/proc/meminfo` headroom, and `DuckDB` persistence.
- **Traceability:** OpenRC `supervise-daemon` unit `pg-tunnel-rhino` + branch `feat/cr-005-cluster-smoke-and-tunnel` merged via `--no-ff`.

### Added
- `pyproject.toml`: Bumped package version to `0.3.0`, added `pythonpath = ["src"]`, and registered `@pytest.mark.integration` marker.
- `tests/test_cluster_live_smoke.py`: Live cluster smoke checks (`test_rhino_pg_tunnel_reachable`, `test_hippo_ollama_headroom_and_duckdb_audit`).

### Verification Evidence
- `ruff check src tests`: `All checks passed!`
- `mypy src tests --strict`: `Success: no issues found in 12 source files`
- `pytest -v -m "not integration"`: `8 passed, 2 deselected`
- `pytest -v -m "integration"`: `2 passed, 8 deselected` (against live `pg-tunnel-rhino` + `Ollama`)

## [0.2.0] - 2026-11-21 — CR-001: Live Host Memory Telemetry & Headroom Guard
### Objective & Risk Mitigated
* **Closed Residual Risk:** Eliminated blind spots between static Z3 RAM budget proofs and empirical host memory pressure (`OOM` risk on 24 GiB / 16 GiB CPU nodes).
* **Traceability:** Branch `feat/cr-001-live-memory-telemetry` merged via `--no-ff` (`63eb6c4`).

### Added
* `src/sandbox_init/telemetry.py`: Deterministic `/proc/meminfo` parser (`MemTotal`, `MemAvailable` -> GiB) and headroom evaluator (`available_gb >= min_headroom_gb`).
* `src/sandbox_init/contracts.py`: `NodeMemorySnapshot` Pydantic v2 contract.
* `src/sandbox_init/store.py`: `node_memory_snapshots` table in `DuckDB` for empirical telemetry persistence.
* `src/sandbox_init/server.py`: `record_node_memory_telemetry` FastMCP tool.
* `tests/test_telemetry.py`: Unit and `Hypothesis` property tests (50 randomized host memory profiles).

### Verification Evidence
* `ruff check src tests`: `All checks passed!`
* `mypy src tests` (`--strict`): `0` issues across `11` source files.
* `pytest -v`: `8 passed` (`200` total `Hypothesis` property examples).

## [0.1.0] - 2026-11-21 — Cluster Verification Baseline
* Initial Z3 SMT single-node and cross-node (`hippo` + `rhino`) memory budget verifier, CEGIS synthesis loop (`Ollama`), `DuckDB` audit log, and Level-2 `docs/ARCHITECTURE.md`.
