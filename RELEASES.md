# Product Releases & Business Value Traceability (`RELEASES.md`)

Official release roadmap and business-value traceability matrix across the local neuro-symbolic verification cluster (`sandbox-init`, `abstract-ops`, `interview-ops`, `hostel-ops`).

---

## Release `v0.5.0` (In Progress — Planned Scope)
- **Business Goal:** Prove end-to-end protocol reliability, retrieval precision, and adversarial resilience of the neuro-symbolic agentic cluster under automated, reproducible QA harnesses—demonstrating production-grade AI Quality Assurance readiness without cloud dependencies.
- **Refinement Record:** [`docs/releases/v0.5.0-refine.md`](docs/releases/v0.5.0-refine.md)

| CR # & Short Name | Repository | Short Task Description | Contribution to Release Business Goal | Architecture Learning Value | Formal Invariant / DoD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CR-010: FastMCP `stdio` Contract & Z3 Rejection Harness** | `sandbox-init`, `abstract-ops`, `interview-ops`, `hostel-ops` | Automated JSON-RPC / `stdio` contract tests invoking all exposed `FastMCP` tools via official MCP client sessions (`SAT` happy-path + `UNSAT` rejection). | Guarantees agent-facing MCP tool boundaries never leak malformed payloads or bypass Z3 invariant gates. | Protocol-level testing of Model Context Protocol (`FastMCP`) servers and error-contract verification. | `tests/test_mcp_contracts.py` green across 100% of MCP tools (`SAT` + `UNSAT` rejection). |
| **CR-011: Hybrid RRF Benchmark & Recall@K / MRR Gate** | `interview-ops` (+ `sandbox-init` DuckDB telemetry) | Golden Dataset (15+ queries against SSOT) measuring `Recall@3`, `MRR`, and p95 latency across `pgvector`, `tsvector`, and `RRF (k=60)`, logged to `DuckDB`. | Quantifies anti-hallucination retrieval quality with objective IR metrics before LLM synthesis. | Information Retrieval evaluation (`Recall@K`, `MRR`) and hybrid search trade-offs over SSH-tunneled `PostgreSQL + pgvector`. | `Recall@3 >= 0.90`, `MRR >= 0.85`, p95 `< 150 ms`; metrics persisted to `DuckDB`. |
| **CR-012: Adversarial Policy Fuzzing & CEGIS Convergence Gate** | `abstract-ops` | Property-based and adversarial spec generator (`Hypothesis` + synthetic edge cases) benchmarking CEGIS repair convergence. | Proves the formal policy auditor catches 100% of subtle security/logic flaws within bounded CPU budgets. | Neuro-symbolic CEGIS convergence guarantees and adversarial robustness testing (`ISO/IEC 24029`). | 0 false `SAT` verdicts across `>= 50` adversarial specs; convergence in `<= 3` iterations. |

---

## Release `v0.4.0` (Released — 2026-11-22)
- **Business Goal:** Establish forensic engineering auditability, reproducible execution logging, and structured post-release retrospectives so every verification claim is backed by timestamped artifacts.
- **Retrospective:** [`docs/releases/v0.4.0-retrospective.md`](docs/releases/v0.4.0-retrospective.md)

| CR # & Short Name | Repository | Short Task Description | Contribution to Release Business Goal | Architecture Learning Value | Formal Invariant / DoD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CR-009: Dev-Process Auditability & Release Retrospectives** | All 4 repositories | POSIX `scripts/run_logged.sh` wrapper (`.stdout`, `.stderr`, `.log` + ISO-8601 timestamps), `docs/dev-log/` artifacts, and release retrospective gate. | Eliminates unlogged test runs and preserves full engineering decision history for technical due diligence. | Reproducible test harness instrumentation and automated documentation-as-code governance. | `test_run_logged.py` + 8th mutation counterexample (`missing_retrospective_section`) green. |

---

## Release `v0.3.0` (Released — 2026-11-22)
- **Business Goal:** Eliminate stateful database race conditions, schema drift defects, and documentation quality gaps across all cluster repositories.
- **Retrospective:** [`docs/releases/v0.3.0-retrospective.md`](docs/releases/v0.3.0-retrospective.md)

| CR # & Short Name | Repository | Short Task Description | Contribution to Release Business Goal | Architecture Learning Value | Formal Invariant / DoD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CR-005 & CR-006: Live Cluster Smoke & `CHANGELOG` Traceability** | All 4 repositories | Live `hippo <-> rhino` integration smoke tests and structured `CHANGELOG.md` with CR-to-risk traceability. | Proves real cross-node operational readiness and transparent change management. | Live infrastructure verification (`SSH` tunnel, `Ollama`, `DuckDB`, `PostgreSQL`). | `@pytest.mark.integration` smoke tests green; `CHANGELOG.md` validated. |
| **CR-007 & BUG-001 / CAPA-001: Concurrent Booking Race & Idempotent DDL** | `hostel-ops`, `sandbox-init` | Barrier-synchronized `asyncio` concurrency race test (`btree_gist`), idempotent `pg_constraint` migration, and CAPA defect registry. | Prevents double-booking TOCTOU races and silent DDL drift on stateful databases. | Storage-engine `EXCLUDE USING gist` invariants and formal CAPA root-cause closure. | `23P01` `ExclusionViolation` verified live on `rhino`; `DEFECTS_AND_CAPA.md` published. |
| **CR-008: Architecture Docs & Mutation-Tested Quality Gate** | All 4 repositories | Level-2 `docs/ARCHITECTURE.md` across all repos + `tests/test_docs_quality.py` with 7 seeded mutation counterexamples and live Ollama rubric. | Ensures interview-ready architectural clarity with zero broken links, placeholders, or hollow claims. | Mutation testing of test oracles and hybrid deterministic + LLM-as-a-Judge doc auditing. | 100% of seeded defects rejected; live Ollama rubric `>= 4/5`. |

---

## Release `v0.2.0` (Released — 2026-11-22)
- **Business Goal:** Harden symbolic invariants against subtle semantic bypasses (free-text skill sneak-in, shadowed rules, dirty-room transitions) and add live RAM telemetry.

| CR # & Short Name | Repository | Short Task Description | Contribution to Release Business Goal | Architecture Learning Value | Formal Invariant / DoD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CR-001: Node RAM Telemetry Collector** | `sandbox-init` | `/proc/meminfo` headroom telemetry collector persisted to `DuckDB` with `Hypothesis` property tests. | Prevents OOM crashes during local CPU LLM inference on `hippo` (`24 GiB` RAM). | Deterministic resource telemetry and property-based invariant verification. | `test_telemetry.py` green; headroom `>= 4 GiB` verified. |
| **CR-002: Rule Subsumption & Shadowing Detector** | `abstract-ops` | Z3 formal proof (`UNSAT(e2 and not e1)`) detecting shadowed/redundant policy rules. | Eliminates dead or masked compliance rules in underwriting and RBAC policies. | Symbolic subsumption checking in SMT solvers over continuous numeric bounds. | `test_detects_shadowed_redundant_rule` green. |
| **CR-003: Free-Text Bullet Entity & Year Guard** | `interview-ops` | Deterministic lexical extractor scanning `bullet_text` for unverified skills and years inside Z3 gate. | Blocks "skill sneak-in" hallucinations in generated CV bullets. | Neuro-symbolic lexical grounding bridging unstructured text and SMT constraints. | `test_bullet_entity_guard.py` green. |
| **CR-004: Anti-Overbooking & Housekeeping State Machine** | `hostel-ops` | Z3 + `btree_gist` disjoint stay intervals and `CLEAN -> DIRTY -> CLEAN` housekeeping transitions. | Guarantees zero overbooking and prevents check-ins into uncleaned rooms. | Formal state-machine invariants coupled with relational range exclusion constraints. | `test_db_gist_and_housekeeping.py` green. |

---

## Release `v0.1.0` (Released — 2026-11-22)
- **Business Goal:** Establish a zero-cloud-cost, two-node neuro-symbolic verification baseline (`hippo` + `rhino`) with Z3 SMT solvers, Pydantic v2 contracts, and FastMCP `stdio` interfaces.

| CR # & Short Name | Repository | Short Task Description | Contribution to Release Business Goal | Architecture Learning Value | Formal Invariant / DoD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CR-000: Cluster & Domain Baseline** | All 4 repositories | Core Z3 verifiers, CEGIS loops, hybrid RRF search, triple-entry ledger, and `FastMCP` `stdio` servers. | Delivers working end-to-end neuro-symbolic prototypes across infrastructure, policy, RAG, and OLTP domains. | Separation of stochastic LLM generation from deterministic SMT proof verification. | `ruff`, `mypy --strict`, and unit `pytest` suites green across all 4 repos. |
