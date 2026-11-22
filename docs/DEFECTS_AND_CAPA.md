# Cluster Defect Log & Process Improvements (CAPA Registry)

This register tracks real defects discovered during verification across the `hippo` + `rhino` neuro-symbolic cluster (`sandbox-init`, `abstract-ops`, `interview-ops`, `hostel-ops`), their root causes, regression tests, and systemic Corrective & Preventive Actions (`CAPA`).

## Summary Matrix

| Defect ID | Repo / CR | Severity | Summary | Root Cause | Process Improvement |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BUG-001** | `hostel-ops` (`CR-007`) | High (Data Integrity / TOCTOU) | Overlapping bookings (`[10, 14)` vs `[12, 16)`) both committed on live `rhino` PostgreSQL under barrier concurrency. | `CREATE TABLE IF NOT EXISTS` silently skipped adding `bookings_no_overlap_excl` (`EXCLUDE USING gist`) to pre-existing `v0.1.0` table; unit tests checked DDL strings rather than live catalog state. | **CAPA-001** |

---

## Detailed Records

### BUG-001: Silent DDL Schema Drift on `CREATE TABLE IF NOT EXISTS` (`hostel-ops`, CR-007)
- **Symptom:** Running `test_concurrent_overlapping_bookings_enforced_by_rhino_gist` against `rhino` (`127.0.0.1:15432`) produced `2` committed bookings instead of `1` commit + `1` `psycopg.errors.ExclusionViolation` (`23P01`).
- **Root Cause:** In `CR-004` (`v0.2.0`), `CONSTRAINT bookings_no_overlap_excl` was placed inside `CREATE TABLE IF NOT EXISTS bookings`. On stateful `rhino`, `bookings` already existed from `v0.1.0`, so PostgreSQL ignored the new constraint definition without error.
- **Fix:** Added an idempotent `DO $$ ... IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bookings_no_overlap_excl') THEN ALTER TABLE bookings ADD CONSTRAINT ... $$` block in `src/hostel_ops/storage.py`.
- **Regression Evidence:** `tests/test_live_gist_concurrency.py` (`@pytest.mark.integration`) — verified `1 passed` against live `rhino` PostgreSQL.

### CAPA-001: Idempotent DDL Evolution & Stateful Integration Gate
- **Scope:** All PostgreSQL / DuckDB persistence layers (`hostel-ops`, `interview-ops`, `sandbox-init`).
- **Preventive Rule 1 (DDL):** Never rely on `CREATE TABLE IF NOT EXISTS` to add constraints, columns, or indexes to existing tables. Every schema invariant must be enforced by an idempotent catalog check (`pg_constraint`, `pg_indexes`, `CREATE INDEX IF NOT EXISTS`).
- **Preventive Rule 2 (Verification):** DDL and concurrency invariants require `@pytest.mark.integration` execution against stateful cluster databases on `rhino`, complementing mocked/in-memory unit tests.
