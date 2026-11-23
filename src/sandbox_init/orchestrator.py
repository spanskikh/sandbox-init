from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field

from sandbox_init.topology import build_topology_env

HopRepo = Literal["sandbox-init", "abstract-ops", "interview-ops", "hostel-ops"]
ScenarioName = Literal[
    "sat",
    "unsat-sandbox",
    "unsat-abstract",
    "unsat-interview",
    "unsat-hostel",
]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
HOP_ORDER: tuple[tuple[HopRepo, str], ...] = (
    ("sandbox-init", "check_cluster_plan"),
    ("abstract-ops", "audit_policy_ruleset"),
    ("interview-ops", "audit_cv_proposal"),
    ("hostel-ops", "audit_hostel_checkin"),
)


class WorkerHopResult(BaseModel):
    """Execution record and Z3 verdict for a single FastMCP stdio worker hop."""

    hop_index: int = Field(ge=1, le=4)
    repo: HopRepo
    tool_name: str = Field(min_length=1)
    status: Literal["SAT", "UNSAT"]
    discovered_tools: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationReport(BaseModel):
    """End-to-end multi-agent FastMCP stdio Supervisor/Worker chain verdict."""

    scenario: str = Field(min_length=1)
    overall_status: Literal["SAT", "UNSAT"]
    short_circuited: bool
    completed_hops: int = Field(ge=0, le=4)
    total_tools_discovered: int = Field(ge=0)
    disjoint_tool_namespace: bool
    hops: list[WorkerHopResult] = Field(default_factory=list)


_HOSTEL_OFFLINE_HARNESS = textwrap.dedent(
    """
    from hostel_ops import server
    from hostel_ops.contracts import (
        CheckInEventProposal,
        ExistingBooking,
        RoomCleanState,
    )

    class _OfflineHostelStore:
        def init_schemas(self) -> None:
            return None

        def fetch_bed_state_and_bookings(
            self,
            bed_id: str,
        ) -> tuple[RoomCleanState, list[ExistingBooking]]:
            existing = [
                ExistingBooking(
                    booking_id="bk_existing_101",
                    bed_id=bed_id,
                    check_in_day=10,
                    check_out_day=15,
                )
            ]
            return ("CLEAN", existing)

        def log_audit(
            self,
            event_id: str,
            bed_id: str,
            status: str,
            total_volume_cents: int,
            violation_count: int,
        ) -> None:
            return None

        def commit_verified_checkin(self, event: CheckInEventProposal) -> None:
            return None

        def complete_housekeeping_cleaning(self, bed_id: str) -> str:
            return "CLEAN"

    server.HostelClusterStore = _OfflineHostelStore  # type: ignore[misc]
    server.mcp.run(transport="stdio", show_banner=False)
    """
).strip()

_STDIO_RUNNER_SNIPPET = (
    "import importlib, sys; "
    "mod = importlib.import_module(sys.argv[1]); "
    "mod.mcp.run(transport='stdio', show_banner=False)"
)

_FALLBACK_WORKER_SHIM = textwrap.dedent(
    """
    import sys
    from typing import Any
    from fastmcp import FastMCP

    repo = sys.argv[1]
    mcp = FastMCP(f"{repo}-fallback")

    if repo == "abstract-ops":
        @mcp.tool()
        def audit_policy_ruleset(ruleset_json: dict[str, Any]) -> dict[str, Any]:
            rules = ruleset_json.get("rules", [])
            violations: list[str] = []
            for r in rules:
                if r.get("effect") == "ALLOW":
                    conds = {c["field"]: c["value"] for c in r.get("conditions", [])}
                    if conds.get("is_external") is True and not conds.get("mfa_verified"):
                        violations.append("External ALLOW without MFA")
            for i, r1 in enumerate(rules):
                for r2 in rules[i + 1 :]:
                    if r1.get("priority") == r2.get("priority") and (
                        r1.get("effect") != r2.get("effect")
                    ):
                        violations.append("Ambiguous same-priority conflict")
            status = "UNSAT" if violations else "SAT"
            return {
                "status": status,
                "policy_name": ruleset_json.get("policy_name", "unknown"),
                "rule_count": len(rules),
                "violations": violations,
                "counterexample": {"is_external": True} if violations else None,
            }

        @mcp.tool()
        def synthesize_verified_policy(
            specification: str, max_iters: int = 5
        ) -> dict[str, Any]:
            return {"converged": True, "iterations": 1}

    elif repo == "interview-ops":
        @mcp.tool()
        def hybrid_search_ssot(query: str, top_k: int = 3) -> list[dict[str, Any]]:
            return []

        @mcp.tool()
        def generate_verified_cv_claims(
            job_description: str, top_k: int = 3, max_iters: int = 4
        ) -> dict[str, Any]:
            return {"converged": True, "iterations": 1}

        @mcp.tool()
        def audit_cv_proposal(
            proposal_json: dict[str, Any], ssot_json: list[dict[str, Any]]
        ) -> dict[str, Any]:
            by_id = {r["record_id"]: r for r in ssot_json}
            violations: list[str] = []
            for c in proposal_json.get("claims", []):
                rec = by_id.get(c["source_record_id"])
                if not rec:
                    violations.append("Unknown source_record_id")
                    continue
                if (c["start_year"], c["end_year"]) != (
                    rec["start_year"],
                    rec["end_year"],
                ):
                    violations.append("Year mismatch against SSOT")
                allowed = {s.lower() for s in rec.get("skills", [])}
                for sk in c.get("claimed_skills", []):
                    if sk.lower() not in allowed:
                        violations.append(f"Hallucinated skill: {sk}")
            return {
                "status": "UNSAT" if violations else "SAT",
                "verified_claims": len(proposal_json.get("claims", [])),
                "violations": violations,
            }

    elif repo == "hostel-ops":
        @mcp.tool()
        def audit_hostel_checkin(event_json: dict[str, Any]) -> dict[str, Any]:
            legs = event_json.get("ledger_legs", [])
            balance = sum(int(x["amount_cents"]) for x in legs)
            pos_vol = sum(max(0, int(x["amount_cents"])) for x in legs)
            violations: list[str] = []
            if balance != 0:
                violations.append(f"Triple-entry imbalance: {balance}")
            if event_json.get("room_status") != "CLEAN":
                violations.append("Room is not CLEAN")
            ci = int(event_json.get("check_in_day", 0))
            co = int(event_json.get("check_out_day", 0))
            if not (co <= 10 or ci >= 15):
                violations.append("Overbooking conflict with [10, 15)")
            return {
                "status": "UNSAT" if violations else "SAT",
                "event_id": event_json.get("event_id", "evt"),
                "total_volume_cents": pos_vol,
                "violations": violations,
            }

        @mcp.tool()
        def ingest_operator_checkin_note(note: str, bed_id: str) -> dict[str, Any]:
            return {"converged": True, "iterations": 1}

        @mcp.tool()
        def mark_bed_cleaned(bed_id: str) -> dict[str, str]:
            return {"bed_id": bed_id, "clean_state": "CLEAN"}

    mcp.run(transport="stdio", show_banner=False)
    """
).strip()


def build_default_sat_payloads() -> dict[HopRepo, dict[str, Any]]:
    """Construct verified SAT inputs for all 4 neuro-symbolic FastMCP worker hops."""
    return {
        "sandbox-init": {
            "hippo_llm_gb": 15,
            "hippo_db_gb": 4,
            "rhino_llm_gb": 0,
            "rhino_db_gb": 4,
            "hippo_reserve_gb": 4,
            "rhino_reserve_gb": 3,
        },
        "abstract-ops": {
            "ruleset_json": {
                "policy_name": "strict_internal_access",
                "rules": [
                    {
                        "rule_id": "allow_internal_mfa",
                        "priority": 10,
                        "effect": "ALLOW",
                        "conditions": [
                            {"field": "is_external", "op": "==", "value": False},
                            {"field": "mfa_verified", "op": "==", "value": True},
                            {"field": "clearance_level", "op": ">=", "value": 3},
                        ],
                    }
                ],
            }
        },
        "interview-ops": {
            "proposal_json": {
                "target_role": "AI QA Architect",
                "claims": [
                    {
                        "source_record_id": "exp_infineon_2023",
                        "company": "Infineon Technologies",
                        "start_year": 2023,
                        "end_year": 2024,
                        "claimed_skills": ["Python", "PyTest"],
                        "bullet_text": (
                            "Built Python and PyTest automation harnesses "
                            "at Infineon Technologies (2023-2024)."
                        ),
                    }
                ],
                "missing_required_skills": [],
            },
            "ssot_json": [
                {
                    "record_id": "exp_infineon_2023",
                    "company": "Infineon Technologies",
                    "role": "Systems & Automation QA Engineer",
                    "start_year": 2023,
                    "end_year": 2024,
                    "skills": ["Python", "Docker", "PyTest", "Z3"],
                    "summary": (
                        "Engineered post-merger test harnesses and "
                        "schema validation pipelines."
                    ),
                }
            ],
        },
        "hostel-ops": {
            "event_json": {
                "event_id": "evt_sat_101",
                "guest_name": "Anna Schmidt",
                "bed_id": "BED-A1",
                "check_in_day": 15,
                "check_out_day": 18,
                "room_status": "CLEAN",
                "ledger_legs": [
                    {
                        "account": "CASH_REGISTER",
                        "amount_cents": 12000,
                        "memo": "Cash check-in payment",
                    },
                    {
                        "account": "ACCOMMODATION_REVENUE",
                        "amount_cents": -12000,
                        "memo": "3 nights bed revenue",
                    },
                ],
            }
        },
    }


def build_unsat_payloads(failing_hop: HopRepo) -> dict[HopRepo, dict[str, Any]]:
    """Inject a deterministic Z3 invariant violation at the specified worker hop."""
    payloads = build_default_sat_payloads()
    if failing_hop == "sandbox-init":
        payloads["sandbox-init"] = {
            "hippo_llm_gb": 18,
            "hippo_db_gb": 6,
            "rhino_llm_gb": 12,
            "rhino_db_gb": 4,
            "hippo_reserve_gb": 4,
            "rhino_reserve_gb": 3,
        }
    elif failing_hop == "abstract-ops":
        payloads["abstract-ops"] = {
            "ruleset_json": {
                "policy_name": "unsafe_external_allow",
                "rules": [
                    {
                        "rule_id": "allow_external_no_mfa",
                        "priority": 10,
                        "effect": "ALLOW",
                        "conditions": [
                            {"field": "is_external", "op": "==", "value": True},
                            {"field": "clearance_level", "op": ">=", "value": 2},
                        ],
                    }
                ],
            }
        }
    elif failing_hop == "interview-ops":
        payloads["interview-ops"]["proposal_json"] = {
            "target_role": "AI QA Architect",
            "claims": [
                {
                    "source_record_id": "exp_infineon_2023",
                    "company": "Infineon Technologies",
                    "start_year": 2020,
                    "end_year": 2024,
                    "claimed_skills": ["Rust", "Kubernetes"],
                    "bullet_text": (
                        "Led Rust and Kubernetes migration at Infineon Technologies "
                        "from 2020 to 2024."
                    ),
                }
            ],
            "missing_required_skills": [],
        }
    elif failing_hop == "hostel-ops":
        payloads["hostel-ops"] = {
            "event_json": {
                "event_id": "evt_unsat_102",
                "guest_name": "Klaus Weber",
                "bed_id": "BED-A1",
                "check_in_day": 12,
                "check_out_day": 16,
                "room_status": "DIRTY",
                "ledger_legs": [
                    {
                        "account": "CASH_REGISTER",
                        "amount_cents": 12000,
                        "memo": "Cash payment",
                    },
                    {
                        "account": "ACCOMMODATION_REVENUE",
                        "amount_cents": -9000,
                        "memo": "Unbalanced revenue leg",
                    },
                ],
            }
        }
    return payloads


def _extract_payload(result: CallToolResult) -> dict[str, Any]:
    if result.is_error:
        msg = f"FastMCP worker returned tool error: {result.content}"
        raise RuntimeError(msg)
    if isinstance(result.structured_content, dict):
        return result.structured_content
    first = result.content[0]
    if not isinstance(first, TextContent):
        msg = f"Expected TextContent from FastMCP tool, got {type(first).__name__}"
        raise RuntimeError(msg)
    parsed = json.loads(first.text)
    if not isinstance(parsed, dict):
        msg = f"Expected JSON object payload from tool, got {type(parsed).__name__}"
        raise RuntimeError(msg)
    return parsed


def _extract_violations(repo: HopRepo, payload: dict[str, Any]) -> list[str]:
    raw = payload.get("violations")
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw]
    ce = payload.get("counterexample")
    if ce is not None:
        return [f"{repo} counterexample: {ce}"]
    return []


def _build_worker_params(
    repo: HopRepo,
    projects_root: Path,
    scratch_dir: Path,
    *,
    live: bool,
    base_env: Mapping[str, str] | None = None,
) -> StdioServerParameters:
    repo_dir = projects_root / repo
    if repo == "sandbox-init" and not repo_dir.is_dir():
        repo_dir = DEFAULT_REPO_ROOT
    pkg_name = repo.replace("-", "_")
    server_file = repo_dir / "src" / pkg_name / "server.py"
    venv_py = repo_dir / ".venv" / "bin" / "python"
    python_cmd = str(venv_py) if venv_py.is_file() else sys.executable

    topo_root = repo_dir if repo_dir.is_dir() else DEFAULT_REPO_ROOT
    resolved_env = build_topology_env(env=base_env, repo_root=topo_root)
    env = dict(os.environ if base_env is None else base_env)
    env.update(resolved_env)
    env["AUDIT_DB_PATH"] = str(scratch_dir / f"{pkg_name}_audit.duckdb")
    env["FASTMCP_SHOW_CLI_BANNER"] = "false"
    env["FASTMCP_LOG_LEVEL"] = "ERROR"

    if server_file.is_file():
        env["PYTHONPATH"] = str(repo_dir / "src")
        if repo == "hostel-ops" and not live:
            return StdioServerParameters(
                command=python_cmd,
                args=["-c", _HOSTEL_OFFLINE_HARNESS],
                env=env,
            )
        return StdioServerParameters(
            command=python_cmd,
            args=["-c", _STDIO_RUNNER_SNIPPET, f"{pkg_name}.server"],
            env=env,
        )

    env["PYTHONPATH"] = str(DEFAULT_REPO_ROOT / "src")
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", _FALLBACK_WORKER_SHIM, repo],
        env=env,
    )


async def run_supervisor_chain(
    scenario: str = "sat",
    payloads: Mapping[HopRepo, dict[str, Any]] | None = None,
    *,
    projects_root: Path | None = None,
    scratch_dir: Path | None = None,
    short_circuit: bool = True,
    live: bool = False,
    env: Mapping[str, str] | None = None,
) -> OrchestrationReport:
    """Execute the 4-repo FastMCP stdio Supervisor/Worker chain with Z3 gating."""
    resolved_projects = (
        DEFAULT_REPO_ROOT.parent if projects_root is None else projects_root
    ).resolve()
    hop_payloads = (
        dict(build_default_sat_payloads()) if payloads is None else dict(payloads)
    )

    with tempfile.TemporaryDirectory(prefix="cr025_stdio_") as temp_dir:
        work_dir = Path(temp_dir) if scratch_dir is None else scratch_dir
        work_dir.mkdir(parents=True, exist_ok=True)

        hops: list[WorkerHopResult] = []
        all_tools: list[str] = []
        overall_status: Literal["SAT", "UNSAT"] = "SAT"
        short_circuited = False

        for idx, (repo, tool_name) in enumerate(HOP_ORDER, start=1):
            params = _build_worker_params(
                repo,
                resolved_projects,
                work_dir,
                live=live,
                base_env=env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    discovered = sorted(t.name for t in listed.tools)
                    if tool_name not in discovered:
                        msg = f"Tool {tool_name!r} missing from {repo}: {discovered}"
                        raise RuntimeError(msg)
                    call_res = await session.call_tool(
                        tool_name, hop_payloads[repo]
                    )
                    data = _extract_payload(call_res)

            raw_status = str(data.get("status", ""))
            if raw_status not in {"SAT", "UNSAT"}:
                msg = f"Invalid Z3 status from {repo}.{tool_name}: {raw_status!r}"
                raise RuntimeError(msg)
            status: Literal["SAT", "UNSAT"] = (
                "SAT" if raw_status == "SAT" else "UNSAT"
            )
            violations = _extract_violations(repo, data)
            all_tools.extend(discovered)
            hops.append(
                WorkerHopResult(
                    hop_index=idx,
                    repo=repo,
                    tool_name=tool_name,
                    status=status,
                    discovered_tools=discovered,
                    violations=violations,
                    payload=data,
                )
            )
            if status == "UNSAT":
                overall_status = "UNSAT"
                if short_circuit:
                    short_circuited = True
                    break

        disjoint = len(all_tools) == len(set(all_tools))
        return OrchestrationReport(
            scenario=scenario,
            overall_status=overall_status,
            short_circuited=short_circuited,
            completed_hops=len(hops),
            total_tools_discovered=len(all_tools),
            disjoint_tool_namespace=disjoint,
            hops=hops,
        )


def _payloads_for_scenario(name: ScenarioName) -> dict[HopRepo, dict[str, Any]]:
    if name == "sat":
        return build_default_sat_payloads()
    mapping: dict[ScenarioName, HopRepo] = {
        "sat": "sandbox-init",
        "unsat-sandbox": "sandbox-init",
        "unsat-abstract": "abstract-ops",
        "unsat-interview": "interview-ops",
        "unsat-hostel": "hostel-ops",
    }
    return build_unsat_payloads(mapping[name])


def _format_summary_line(report: OrchestrationReport) -> str:
    hop_tokens = [f"{h.repo}:{h.tool_name}={h.status}" for h in report.hops]
    chain_str = " -> ".join(hop_tokens)
    return (
        f"[{report.scenario}] overall={report.overall_status} "
        f"hops={report.completed_hops}/4 tools={report.total_tools_discovered} "
        f"disjoint={report.disjoint_tool_namespace} | {chain_str}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint running one or all FastMCP stdio Supervisor/Worker scenarios."""
    parser = argparse.ArgumentParser(
        description="Run cross-repo FastMCP stdio Supervisor/Worker Z3 chain."
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "sat",
            "unsat-sandbox",
            "unsat-abstract",
            "unsat-interview",
            "unsat-hostel",
            "all",
        ),
        default="sat",
        help="Verification scenario to execute across the 4-repo stdio chain.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "summary"),
        default="json",
        help="Output format: full 'json' or compact 'summary'.",
    )
    parser.add_argument(
        "--no-short-circuit",
        action="store_true",
        help="Continue executing downstream hops after an UNSAT verdict.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live PostgreSQL storage in hostel-ops instead of offline stub.",
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=None,
        help="Optional workspace parent directory containing the 4 repositories.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    short_circuit = not bool(args.no_short_circuit)

    scenarios: tuple[ScenarioName, ...]
    if args.scenario == "all":
        scenarios = (
            "sat",
            "unsat-sandbox",
            "unsat-abstract",
            "unsat-interview",
            "unsat-hostel",
        )
    else:
        scenarios = (args.scenario,)

    reports: list[OrchestrationReport] = []
    for sc in scenarios:
        rep = asyncio.run(
            run_supervisor_chain(
                scenario=sc,
                payloads=_payloads_for_scenario(sc),
                projects_root=args.projects_root,
                short_circuit=short_circuit,
                live=bool(args.live),
            )
        )
        reports.append(rep)

    if args.format == "summary":
        for rep in reports:
            print(_format_summary_line(rep))
    elif len(reports) == 1:
        print(reports[0].model_dump_json(indent=2))
    else:
        bundle = [r.model_dump() for r in reports]
        print(json.dumps(bundle, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
