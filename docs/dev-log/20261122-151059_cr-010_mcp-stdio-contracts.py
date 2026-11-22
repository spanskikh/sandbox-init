# Target: tests/test_mcp_contracts.py
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS: dict[str, set[str]] = {
    "check_cluster_allocation": {"node", "llm_ram_gb", "db_ram_gb", "total_budget_gb"},
    "check_cluster_plan": {"hippo_llm_gb", "hippo_db_gb", "rhino_llm_gb", "rhino_db_gb"},
    "synthesize_valid_allocation": {"goal"},
    "record_node_memory_telemetry": set(),
}

HARNESS_ENTRYPOINT = textwrap.dedent(
    """
    from unittest.mock import AsyncMock, patch
    from sandbox_init import server
    from sandbox_init.cegis import CegisResult
    from sandbox_init.contracts import (
        AllocationProposal,
        NodeMemorySnapshot,
        VerificationVerdict,
    )

    async def _fake_cegis(goal: str, db_path: str, max_iters: int = 5) -> CegisResult:
        prop = AllocationProposal(
            node="hippo",
            llm_ram_gb=12,
            db_ram_gb=4,
            total_budget_gb=24,
            reserve_gb=4,
        )
        verdict = VerificationVerdict(
            status="SAT",
            proposal=prop,
            slack_gb=4,
            counterexample=None,
        )
        return CegisResult(
            converged=True,
            iterations=1,
            final_verdict=verdict,
            history=[verdict],
        )

    def _fake_meminfo(node: str = "hippo", min_headroom_gb: float = 4.0) -> NodeMemorySnapshot:
        return NodeMemorySnapshot(
            node=node,  # type: ignore[arg-type]
            total_gb=24.0,
            available_gb=14.0,
            used_gb=10.0,
            min_headroom_gb=min_headroom_gb,
            within_budget=14.0 >= min_headroom_gb,
        )

    with (
        patch.object(server, "run_cegis_loop", new=AsyncMock(side_effect=_fake_cegis)),
        patch.object(server, "collect_memory_snapshot", side_effect=_fake_meminfo),
    ):
        server.mcp.run(transport="stdio")
    """
).strip()


def _extract_payload(result: CallToolResult) -> dict[str, Any]:
    assert not result.is_error, f"Unexpected MCP tool error: {result.content}"
    if isinstance(result.structured_content, dict):
        return result.structured_content
    first = result.content[0]
    assert isinstance(first, TextContent)
    parsed = json.loads(first.text)
    assert isinstance(parsed, dict)
    return parsed


def _server_params(tmp_path: Path) -> StdioServerParameters:
    db_file = tmp_path / "sandbox_contract_audit.duckdb"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["AUDIT_DB_PATH"] = str(db_file)
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", HARNESS_ENTRYPOINT],
        env=env,
    )


@pytest.mark.asyncio
async def test_stdio_tool_discovery_and_schemas(tmp_path: Path) -> None:
    async with stdio_client(_server_params(tmp_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()

    tools_by_name = {tool.name: tool for tool in listed.tools}
    assert set(tools_by_name) == set(EXPECTED_TOOLS)

    for name, expected_required in EXPECTED_TOOLS.items():
        schema = tools_by_name[name].input_schema
        assert schema.get("type") == "object"
        required = set(schema.get("required", []))
        assert expected_required.issubset(required)


@pytest.mark.asyncio
async def test_stdio_z3_sat_and_unsat_paths(tmp_path: Path) -> None:
    async with stdio_client(_server_params(tmp_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            sat_res = await session.call_tool(
                "check_cluster_allocation",
                {
                    "node": "hippo",
                    "llm_ram_gb": 12,
                    "db_ram_gb": 4,
                    "total_budget_gb": 24,
                    "reserve_gb": 4,
                },
            )
            sat_data = _extract_payload(sat_res)
            assert sat_data["status"] == "SAT"
            assert sat_data["slack_gb"] == 4

            unsat_res = await session.call_tool(
                "check_cluster_allocation",
                {
                    "node": "rhino",
                    "llm_ram_gb": 12,
                    "db_ram_gb": 4,
                    "total_budget_gb": 16,
                    "reserve_gb": 3,
                },
            )
            unsat_data = _extract_payload(unsat_res)
            assert unsat_data["status"] == "UNSAT"
            assert unsat_data["counterexample"]

            plan_unsat = await session.call_tool(
                "check_cluster_plan",
                {
                    "hippo_llm_gb": 14,
                    "hippo_db_gb": 6,
                    "rhino_llm_gb": 12,
                    "rhino_db_gb": 4,
                    "hippo_reserve_gb": 4,
                    "rhino_reserve_gb": 3,
                },
            )
            plan_data = _extract_payload(plan_unsat)
            assert plan_data["status"] == "UNSAT"
            assert len(plan_data["violations"]) >= 1

            cegis_res = await session.call_tool(
                "synthesize_valid_allocation",
                {"goal": "Run 8B model on hippo with 4GB DuckDB", "max_iters": 2},
            )
            cegis_data = _extract_payload(cegis_res)
            assert cegis_data["converged"] is True
            assert cegis_data["final_verdict"]["status"] == "SAT"

            tel_res = await session.call_tool(
                "record_node_memory_telemetry",
                {"node": "hippo", "min_headroom_gb": 4.0},
            )
            tel_data = _extract_payload(tel_res)
            assert tel_data["node"] == "hippo"
            assert tel_data["within_budget"] is True


@pytest.mark.asyncio
async def test_stdio_pydantic_validation_rejection(tmp_path: Path) -> None:
    async with stdio_client(_server_params(tmp_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            bad_node = await session.call_tool(
                "check_cluster_allocation",
                {
                    "node": "invalid_node",
                    "llm_ram_gb": 8,
                    "db_ram_gb": 4,
                    "total_budget_gb": 24,
                },
            )
            assert bad_node.is_error is True

            bad_type = await session.call_tool(
                "check_cluster_plan",
                {
                    "hippo_llm_gb": "not_an_int",
                    "hippo_db_gb": 4,
                    "rhino_llm_gb": 8,
                    "rhino_db_gb": 2,
                },
            )
            assert bad_type.is_error is True
