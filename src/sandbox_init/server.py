from __future__ import annotations

import os

from fastmcp import FastMCP

from sandbox_init.cegis import run_cegis_loop
from sandbox_init.contracts import (
    AllocationProposal,
    ClusterPlanProposal,
    NodeAllocation,
    VerificationVerdict,
)
from sandbox_init.store import AuditStore
from sandbox_init.telemetry import collect_memory_snapshot
from sandbox_init.verifier import verify_allocation, verify_cluster_plan

mcp = FastMCP("neuro-symbolic-verifier")
DB_PATH = os.getenv("AUDIT_DB_PATH", "/app/data/audit.duckdb")


@mcp.tool()
def check_cluster_allocation(
    node: str,
    llm_ram_gb: int,
    db_ram_gb: int,
    total_budget_gb: int,
    reserve_gb: int = 4,
) -> dict[str, object]:
    """Валидирует гипотезу распределения RAM одного узла через Pydantic v2 + Z3 + DuckDB."""
    proposal = AllocationProposal(
        node=node,  # type: ignore[arg-type]
        llm_ram_gb=llm_ram_gb,
        db_ram_gb=db_ram_gb,
        total_budget_gb=total_budget_gb,
        reserve_gb=reserve_gb,
    )
    verdict: VerificationVerdict = verify_allocation(proposal)
    store = AuditStore(DB_PATH)
    try:
        store.record(verdict)
    finally:
        store.close()
    return verdict.model_dump()


@mcp.tool()
def check_cluster_plan(
    hippo_llm_gb: int,
    hippo_db_gb: int,
    rhino_llm_gb: int,
    rhino_db_gb: int,
    hippo_reserve_gb: int = 4,
    rhino_reserve_gb: int = 3,
) -> dict[str, object]:
    """Проверяет кросс-узловой план размещения (hippo 24G + rhino 16G) через Z3."""
    plan = ClusterPlanProposal(
        hippo=NodeAllocation(
            llm_ram_gb=hippo_llm_gb,
            db_ram_gb=hippo_db_gb,
            reserve_gb=hippo_reserve_gb,
        ),
        rhino=NodeAllocation(
            llm_ram_gb=rhino_llm_gb,
            db_ram_gb=rhino_db_gb,
            reserve_gb=rhino_reserve_gb,
        ),
    )
    return verify_cluster_plan(plan).model_dump()


@mcp.tool()
async def synthesize_valid_allocation(goal: str, max_iters: int = 5) -> dict[str, object]:
    """Запускает цикл CEGIS с локальной LLM (Ollama) до получения SAT-конфигурации от Z3."""
    result = await run_cegis_loop(goal=goal, db_path=DB_PATH, max_iters=max_iters)
    return {
        "converged": result.converged,
        "iterations": result.iterations,
        "final_verdict": result.final_verdict.model_dump() if result.final_verdict else None,
        "history": [v.model_dump() for v in result.history],
    }


@mcp.tool()
def record_node_memory_telemetry(
    node: str = "hippo",
    min_headroom_gb: float = 4.0,
) -> dict[str, object]:
    """Collect live /proc/meminfo telemetry, check headroom, and persist to DuckDB."""
    snap = collect_memory_snapshot(node=node, min_headroom_gb=min_headroom_gb)  # type: ignore[arg-type]
    store = AuditStore(DB_PATH)
    try:
        store.record_snapshot(snap)
    finally:
        store.close()
    return snap.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")
