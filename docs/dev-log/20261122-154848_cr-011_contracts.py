# Target: src/sandbox_init/contracts.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AllocationProposal(BaseModel):
    """Structured LLM proposal for single-node RAM allocation."""

    node: Literal["hippo", "rhino"]
    llm_ram_gb: int = Field(ge=0, le=64)
    db_ram_gb: int = Field(ge=0, le=64)
    total_budget_gb: int = Field(gt=0, le=64)
    reserve_gb: int = Field(ge=2, default=4)


class VerificationVerdict(BaseModel):
    """Deterministic Z3 verdict and diagnostics for the CEGIS loop."""

    status: Literal["SAT", "UNSAT"]
    proposal: AllocationProposal
    slack_gb: int | None = None
    counterexample: str | None = None


class NodeAllocation(BaseModel):
    """Resource allocation profile for a specific cluster node."""

    llm_ram_gb: int = Field(ge=0, le=24)
    db_ram_gb: int = Field(ge=0, le=24)
    reserve_gb: int = Field(ge=2, le=12, default=4)


class ClusterPlanProposal(BaseModel):
    """Cross-node service placement plan across hippo (24 GiB) and rhino (16 GiB)."""

    hippo: NodeAllocation
    rhino: NodeAllocation


class ClusterVerdict(BaseModel):
    """Z3 verdict for the two-node cluster with violated invariant diagnostics."""

    status: Literal["SAT", "UNSAT"]
    plan: ClusterPlanProposal
    hippo_slack_gb: int | None = None
    rhino_slack_gb: int | None = None
    violations: list[str] = Field(default_factory=list)


class NodeMemorySnapshot(BaseModel):
    """Empirical host memory telemetry snapshot parsed from /proc/meminfo."""

    node: Literal["hippo", "rhino"]
    total_gb: float = Field(gt=0)
    available_gb: float = Field(ge=0)
    used_gb: float = Field(ge=0)
    min_headroom_gb: float = Field(ge=0, default=4.0)
    within_budget: bool


class RagBenchmarkTelemetry(BaseModel):
    """IR benchmark telemetry record persisted from interview-ops RRF evaluations."""

    suite_name: str = Field(min_length=1, max_length=64)
    mode: Literal["dense", "lexical", "hybrid_rrf"]
    query_count: int = Field(gt=0)
    recall_at_k: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    p95_latency_ms: float = Field(ge=0.0)
    passed_gate: bool
