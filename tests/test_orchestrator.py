from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sandbox_init.orchestrator import (
    HopRepo,
    build_default_sat_payloads,
    build_unsat_payloads,
    main,
    run_supervisor_chain,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "run_supervisor_chain.sh"


@pytest.mark.asyncio
async def test_supervisor_chain_end_to_end_sat(tmp_path: Path) -> None:
    report = await run_supervisor_chain(
        scenario="sat",
        payloads=build_default_sat_payloads(),
        scratch_dir=tmp_path,
        short_circuit=True,
    )
    assert report.overall_status == "SAT"
    assert report.short_circuited is False
    assert report.completed_hops == 4
    assert report.total_tools_discovered == 12
    assert report.disjoint_tool_namespace is True

    expected_order = [
        ("sandbox-init", "check_cluster_plan"),
        ("abstract-ops", "audit_policy_ruleset"),
        ("interview-ops", "audit_cv_proposal"),
        ("hostel-ops", "audit_hostel_checkin"),
    ]
    actual_order = [(h.repo, h.tool_name) for h in report.hops]
    assert actual_order == expected_order
    for hop in report.hops:
        assert hop.status == "SAT"
        assert hop.violations == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failing_hop", "expected_completed", "expected_tools_count"),
    [
        ("sandbox-init", 1, 4),
        ("abstract-ops", 2, 6),
        ("interview-ops", 3, 9),
        ("hostel-ops", 4, 12),
    ],
)
async def test_supervisor_chain_short_circuits_on_each_unsat_hop(
    tmp_path: Path,
    failing_hop: HopRepo,
    expected_completed: int,
    expected_tools_count: int,
) -> None:
    report = await run_supervisor_chain(
        scenario=f"unsat-{failing_hop}",
        payloads=build_unsat_payloads(failing_hop),
        scratch_dir=tmp_path,
        short_circuit=True,
    )
    assert report.overall_status == "UNSAT"
    assert report.short_circuited is True
    assert report.completed_hops == expected_completed
    assert report.total_tools_discovered == expected_tools_count
    assert report.disjoint_tool_namespace is True

    for hop in report.hops[:-1]:
        assert hop.status == "SAT"
        assert hop.violations == []

    last_hop = report.hops[-1]
    assert last_hop.repo == failing_hop
    assert last_hop.status == "UNSAT"
    assert len(last_hop.violations) >= 1


@pytest.mark.asyncio
async def test_supervisor_chain_no_short_circuit_collects_all_verdicts(
    tmp_path: Path,
) -> None:
    report = await run_supervisor_chain(
        scenario="unsat-abstract-full",
        payloads=build_unsat_payloads("abstract-ops"),
        scratch_dir=tmp_path,
        short_circuit=False,
    )
    assert report.overall_status == "UNSAT"
    assert report.short_circuited is False
    assert report.completed_hops == 4
    assert report.total_tools_discovered == 12
    assert [h.status for h in report.hops] == ["SAT", "UNSAT", "SAT", "SAT"]
    assert len(report.hops[1].violations) >= 1


@pytest.mark.asyncio
async def test_supervisor_chain_fallback_when_siblings_missing(
    tmp_path: Path,
) -> None:
    isolated_root = tmp_path / "isolated_workspace"
    isolated_root.mkdir(parents=True, exist_ok=True)
    report = await run_supervisor_chain(
        scenario="sat-isolated",
        projects_root=isolated_root,
        scratch_dir=tmp_path / "scratch",
        short_circuit=True,
    )
    assert report.overall_status == "SAT"
    assert report.completed_hops == 4
    assert report.total_tools_discovered == 12
    assert report.disjoint_tool_namespace is True


def test_orchestrator_cli_and_runner_script_dry_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc_summary = main(["--scenario", "sat", "--format", "summary"])
    assert rc_summary == 0
    out_summary = capsys.readouterr().out.strip().splitlines()
    assert len(out_summary) == 1
    assert "[sat] overall=SAT hops=4/4 tools=12 disjoint=True" in out_summary[0]

    rc_json = main(["--scenario", "unsat-sandbox", "--format", "json"])
    assert rc_json == 0
    out_json = json.loads(capsys.readouterr().out)
    assert out_json["overall_status"] == "UNSAT"
    assert out_json["completed_hops"] == 1
    assert out_json["short_circuited"] is True

    assert RUNNER_SCRIPT.is_file(), "Missing scripts/run_supervisor_chain.sh"
    proc = subprocess.run(
        ["bash", str(RUNNER_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Dry-run failed: {proc.stderr}"
    assert "=== DRY-RUN SUPERVISOR CHAIN (CR-025) ===" in proc.stdout
    assert (
        "CHAIN=sandbox-init -> abstract-ops -> interview-ops -> hostel-ops"
        in proc.stdout
    )
