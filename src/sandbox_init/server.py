from __future__ import annotations

import os

from fastmcp import FastMCP

from sandbox_init.cegis import run_cegis_loop
from sandbox_init.contracts import AllocationProposal, VerificationVerdict
from sandbox_init.store import AuditStore
from sandbox_init.verifier import verify_allocation

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
    """Валидирует гипотезу распределения RAM через Pydantic v2 + Z3 и пишет аудит в DuckDB."""
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
async def synthesize_valid_allocation(goal: str, max_iters: int = 5) -> dict[str, object]:
    """Запускает цикл CEGIS с локальной LLM (Ollama) до получения SAT-конфигурации от Z3."""
    result = await run_cegis_loop(goal=goal, db_path=DB_PATH, max_iters=max_iters)
    return {
        "converged": result.converged,
        "iterations": result.iterations,
        "final_verdict": result.final_verdict.model_dump() if result.final_verdict else None,
        "history": [v.model_dump() for v in result.history],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
