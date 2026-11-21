from __future__ import annotations

import json

import httpx

from sandbox_init.cegis import run_cegis_loop


async def test_cegis_converges_after_z3_counterexample() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        calls.append(body)
        if len(calls) == 1:
            # Шаг 1: LLM нарушает бюджет rhino (10 + 4 + 4 > 16)
            proposal = {
                "node": "rhino",
                "llm_ram_gb": 10,
                "db_ram_gb": 4,
                "total_budget_gb": 16,
                "reserve_gb": 4,
            }
        else:
            # Шаг 2: после получения counterexample от Z3 LLM снижает llm_ram_gb до 8
            user_msg = body["messages"][-1]["content"]
            assert "Budget exceeded by 2 GiB" in user_msg
            proposal = {
                "node": "rhino",
                "llm_ram_gb": 8,
                "db_ram_gb": 4,
                "total_budget_gb": 16,
                "reserve_gb": 4,
            }
        return httpx.Response(200, json={"message": {"content": json.dumps(proposal)}})

    transport = httpx.MockTransport(handler)
    result = await run_cegis_loop(
        goal="Allocate RAM on rhino",
        db_path=":memory:",
        max_iters=4,
        transport=transport,
    )

    assert result.converged is True
    assert result.iterations == 2
    assert len(result.history) == 2
    assert result.history[0].status == "UNSAT"
    assert result.history[1].status == "SAT"
    assert result.final_verdict is not None
    assert result.final_verdict.slack_gb == 0
