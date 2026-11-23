from __future__ import annotations

import ast
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest
import z3

REPO_ROOT = Path(__file__).resolve().parents[1]
HIPPO_BUDGET_GB = 24
RHINO_BUDGET_GB = 16


@dataclass(frozen=True)
class ServiceContract:
    name: str
    node: str
    llm_ram_gb: int
    db_ram_gb: int
    reserve_gb: int
    tools: tuple[str, ...]


CLUSTER_CONTRACTS: tuple[ServiceContract, ...] = (
    ServiceContract(
        name="sandbox-init",
        node="hippo",
        llm_ram_gb=8,
        db_ram_gb=2,
        reserve_gb=4,
        tools=(
            "check_cluster_allocation",
            "check_cluster_plan",
            "synthesize_valid_allocation",
            "record_node_memory_telemetry",
        ),
    ),
    ServiceContract(
        name="abstract-ops",
        node="hippo",
        llm_ram_gb=4,
        db_ram_gb=1,
        reserve_gb=4,
        tools=("audit_policy_ruleset", "synthesize_verified_policy"),
    ),
    ServiceContract(
        name="interview-ops",
        node="hippo",
        llm_ram_gb=3,
        db_ram_gb=1,
        reserve_gb=4,
        tools=(
            "hybrid_search_ssot",
            "generate_verified_cv_claims",
            "audit_cv_proposal",
        ),
    ),
    ServiceContract(
        name="hostel-ops",
        node="rhino",
        llm_ram_gb=0,
        db_ram_gb=4,
        reserve_gb=3,
        tools=(
            "audit_hostel_checkin",
            "ingest_operator_checkin_note",
            "mark_bed_cleaned",
        ),
    ),
)


def _verify_cluster_budget_z3(contracts: tuple[ServiceContract, ...]) -> z3.CheckSatResult:
    solver = z3.Solver()
    hippo_svcs = [c for c in contracts if c.node == "hippo"]
    rhino_svcs = [c for c in contracts if c.node == "rhino"]
    hippo_used = sum((c.llm_ram_gb + c.db_ram_gb for c in hippo_svcs), z3.IntVal(0))
    rhino_used = sum((c.llm_ram_gb + c.db_ram_gb for c in rhino_svcs), z3.IntVal(0))
    hippo_res = max((c.reserve_gb for c in hippo_svcs), default=4)
    rhino_res = max((c.reserve_gb for c in rhino_svcs), default=3)
    solver.add(hippo_used + z3.IntVal(hippo_res) <= z3.IntVal(HIPPO_BUDGET_GB))
    solver.add(rhino_used + z3.IntVal(rhino_res) <= z3.IntVal(RHINO_BUDGET_GB))
    return solver.check()


def _extract_expected_tools_from_test(test_file: Path) -> set[str]:
    tree = ast.parse(test_file.read_text(encoding="utf-8"))
    for node in tree.body:
        targets: list[ast.expr] = []
        val: ast.expr | None = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets, val = [node.target], node.value
        elif isinstance(node, ast.Assign):
            targets, val = node.targets, node.value
        if any(isinstance(t, ast.Name) and t.id == "EXPECTED_TOOLS" for t in targets):
            if isinstance(val, ast.Dict):
                return {
                    k.value
                    for k in val.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
    raise AssertionError(f"EXPECTED_TOOLS not found in {test_file}")


def test_cross_cluster_z3_budget_and_namespace_disjointness() -> None:
    assert _verify_cluster_budget_z3(CLUSTER_CONTRACTS) == z3.sat

    overloaded = (
        *CLUSTER_CONTRACTS,
        ServiceContract("overflow-worker", "hippo", 6, 2, 4, ("extra_tool",)),
    )
    assert _verify_cluster_budget_z3(overloaded) == z3.unsat

    all_tools = [tool for svc in CLUSTER_CONTRACTS for tool in svc.tools]
    assert len(all_tools) == len(set(all_tools)) == 12

    for svc in CLUSTER_CONTRACTS:
        candidate = REPO_ROOT.parent / svc.name
        if not candidate.is_dir():
            continue
        meta = tomllib.loads((candidate / "pyproject.toml").read_text(encoding="utf-8"))
        assert meta["project"]["version"] == "0.8.0"
        assert meta["project"]["requires-python"] == ">=3.12"
        actual_tools = _extract_expected_tools_from_test(candidate / "tests/test_mcp_contracts.py")
        assert actual_tools == set(svc.tools)


def test_cyclonedx_sbom_reproducibility_and_hygiene(tmp_path: Path) -> None:
    cdx_bin = Path(sys.executable).parent / "cyclonedx-py"
    if not cdx_bin.is_file():
        pytest.skip("cyclonedx-py not installed in active interpreter")

    normalized: list[list[tuple[str, str, str]]] = []
    for idx in (1, 2):
        out = tmp_path / f"sbom_{idx}.cdx.json"
        subprocess.run([str(cdx_bin), "environment", "-o", str(out)], cwd=REPO_ROOT, check=True)
        raw = out.read_text(encoding="utf-8")
        assert "/home/" not in raw
        bom = json.loads(raw)
        assert bom["bomFormat"] == "CycloneDX"
        comps = sorted(
            (c["name"], c.get("version", ""), c.get("purl", "")) for c in bom["components"]
        )
        names = {c[0] for c in comps}
        assert {"pydantic", "z3-solver", "duckdb", "mcp", "httpx"}.issubset(names)
        normalized.append(comps)

    assert normalized[0] == normalized[1]
