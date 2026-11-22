from __future__ import annotations

from pathlib import Path

import duckdb

from sandbox_init.contracts import (
    NodeMemorySnapshot,
    RagBenchmarkTelemetry,
    VerificationVerdict,
)


class AuditStore:
    """Local append-only verification and telemetry log in DuckDB."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = duckdb.connect(str(db_path))
        self._conn.execute("SET memory_limit='512MB'; SET threads=2;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verdicts (
                ts TIMESTAMP DEFAULT current_timestamp,
                node VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                llm_ram_gb INTEGER NOT NULL,
                db_ram_gb INTEGER NOT NULL,
                total_budget_gb INTEGER NOT NULL,
                slack_gb INTEGER,
                counterexample VARCHAR
            )
            """
        )

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_memory_snapshots (
                ts TIMESTAMP DEFAULT current_timestamp,
                node VARCHAR NOT NULL,
                total_gb DOUBLE NOT NULL,
                available_gb DOUBLE NOT NULL,
                used_gb DOUBLE NOT NULL,
                min_headroom_gb DOUBLE NOT NULL,
                within_budget BOOLEAN NOT NULL
            )
            """
        )

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_benchmarks (
                ts TIMESTAMP DEFAULT current_timestamp,
                suite_name VARCHAR NOT NULL,
                mode VARCHAR NOT NULL,
                query_count INTEGER NOT NULL,
                recall_at_k DOUBLE NOT NULL,
                mrr DOUBLE NOT NULL,
                p95_latency_ms DOUBLE NOT NULL,
                passed_gate BOOLEAN NOT NULL
            )
            """
        )

    def record_snapshot(self, snap: NodeMemorySnapshot) -> None:
        self._conn.execute(
            """
            INSERT INTO node_memory_snapshots (
                node, total_gb, available_gb, used_gb, min_headroom_gb, within_budget
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                snap.node,
                snap.total_gb,
                snap.available_gb,
                snap.used_gb,
                snap.min_headroom_gb,
                snap.within_budget,
            ],
        )

    def count_snapshots(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM node_memory_snapshots").fetchone()
        return int(row[0]) if row else 0

    def record_rag_benchmark(self, bench: RagBenchmarkTelemetry) -> None:
        self._conn.execute(
            """
            INSERT INTO rag_benchmarks (
                suite_name, mode, query_count, recall_at_k, mrr, p95_latency_ms, passed_gate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                bench.suite_name,
                bench.mode,
                bench.query_count,
                bench.recall_at_k,
                bench.mrr,
                bench.p95_latency_ms,
                bench.passed_gate,
            ],
        )

    def count_rag_benchmarks(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM rag_benchmarks").fetchone()
        return int(row[0]) if row else 0

    def record(self, verdict: VerificationVerdict) -> None:
        p = verdict.proposal
        self._conn.execute(
            """
            INSERT INTO verdicts (
                node, status, llm_ram_gb, db_ram_gb, total_budget_gb, slack_gb, counterexample
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                p.node,
                verdict.status,
                p.llm_ram_gb,
                p.db_ram_gb,
                p.total_budget_gb,
                verdict.slack_gb,
                verdict.counterexample,
            ],
        )

    def count_by_status(self) -> dict[str, int]:
        query = "SELECT status, COUNT(*) FROM verdicts GROUP BY status"
        rows = self._conn.execute(query).fetchall()
        return {str(status): int(cnt) for status, cnt in rows}

    def close(self) -> None:
        self._conn.close()
