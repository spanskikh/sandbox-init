from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from sandbox_init.contracts import AllocationProposal, VerificationVerdict
from sandbox_init.store import AuditStore
from sandbox_init.verifier import verify_allocation

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


@dataclass(frozen=True)
class CegisResult:
    converged: bool
    iterations: int
    final_verdict: VerificationVerdict | None
    history: list[VerificationVerdict]


async def _propose_from_llm(
    client: httpx.AsyncClient,
    ollama_url: str,
    model: str,
    goal: str,
    feedback: list[str],
    seed: int = 42,
) -> AllocationProposal:
    """Запрашивает у локальной LLM JSON-предложение, ограниченное JSON-схемой Pydantic."""
    system_prompt = (
        "You are a cluster resource planner. Return ONLY a JSON object matching the schema. "
        "Allocate integer GiB for llm_ram_gb, db_ram_gb, total_budget_gb, and reserve_gb."
    )
    user_prompt = f"Goal: {goal}\n"
    if feedback:
        joined = "\n".join(f"- Iteration {i + 1} failed: {msg}" for i, msg in enumerate(feedback))
        user_prompt += f"\nPrevious Z3 counterexamples (fix these constraints):\n{joined}\n"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": AllocationProposal.model_json_schema(),
        "options": {
            "temperature": 0.0,
            "seed": seed,
            "num_ctx": 4096,
        },
    }

    resp = await client.post(f"{ollama_url}/api/chat", json=payload, timeout=120.0)
    resp.raise_for_status()
    raw_content = resp.json()["message"]["content"]
    return AllocationProposal.model_validate_json(raw_content)


async def run_cegis_loop(
    goal: str,
    db_path: str = ":memory:",
    max_iters: int = 5,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CegisResult:
    """Замкнутый цикл CEGIS: LLM -> Pydantic -> Z3 -> Counterexample -> DuckDB."""
    feedback: list[str] = []
    history: list[VerificationVerdict] = []
    store = AuditStore(db_path)

    try:
        async with httpx.AsyncClient(transport=transport) as client:
            for step in range(max_iters):
                try:
                    proposal = await _propose_from_llm(
                        client=client,
                        ollama_url=ollama_url,
                        model=model,
                        goal=goal,
                        feedback=feedback,
                        seed=42 + step,
                    )
                except (ValidationError, json.JSONDecodeError, KeyError) as exc:
                    feedback.append(f"Schema/JSON error: {exc}")
                    continue

                verdict = verify_allocation(proposal)
                store.record(verdict)
                history.append(verdict)

                if verdict.status == "SAT":
                    return CegisResult(
                        converged=True,
                        iterations=step + 1,
                        final_verdict=verdict,
                        history=history,
                    )

                feedback.append(verdict.counterexample or "UNSAT constraint violation")

        return CegisResult(
            converged=False,
            iterations=max_iters,
            final_verdict=history[-1] if history else None,
            history=history,
        )
    finally:
        store.close()


def main() -> None:
    """CLI smoke-test: провоцируем первоначальный UNSAT, чтобы увидеть работу контрпримера Z3."""
    goal = (
        "Configure node 'rhino' (total_budget_gb=16, reserve_gb=4). "
        "Try allocating llm_ram_gb=10 and db_ram_gb=4 first; if rejected, reduce llm_ram_gb to fit."
    )
    res = asyncio.run(run_cegis_loop(goal=goal, db_path="/app/data/audit.duckdb", max_iters=4))
    print(f"Converged: {res.converged} in {res.iterations} iteration(s)")
    for idx, v in enumerate(res.history, 1):
        print(
            f"  Iter {idx}: status={v.status} llm={v.proposal.llm_ram_gb}G "
            f"db={v.proposal.db_ram_gb}G slack={v.slack_gb} ce={v.counterexample}"
        )


if __name__ == "__main__":
    main()
