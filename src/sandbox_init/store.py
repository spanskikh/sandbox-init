from __future__ import annotations

from pathlib import Path

import duckdb

from sandbox_init.contracts import VerificationVerdict


class AuditStore:
    """Локальный append-only журнал верификаций в DuckDB."""

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
