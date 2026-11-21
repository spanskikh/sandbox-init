# Changelog

All notable changes and formal Change Requests (CRs) for `sandbox-init` are documented in this file.

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
