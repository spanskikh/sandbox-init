# Changelog

All notable changes and formal Change Requests (CRs) for `sandbox-init` are documented in this file.

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
