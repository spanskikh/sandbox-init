from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AllocationProposal(BaseModel):
    """Структурированное предложение от LLM по распределению памяти одного узла."""

    node: Literal["hippo", "rhino"]
    llm_ram_gb: int = Field(ge=0, le=64)
    db_ram_gb: int = Field(ge=0, le=64)
    total_budget_gb: int = Field(gt=0, le=64)
    reserve_gb: int = Field(ge=2, default=4)


class VerificationVerdict(BaseModel):
    """Детерминированный вердикт Z3 + диагностика для CEGIS-цикла."""

    status: Literal["SAT", "UNSAT"]
    proposal: AllocationProposal
    slack_gb: int | None = None
    counterexample: str | None = None


class NodeAllocation(BaseModel):
    """Профиль распределения ресурсов на конкретном узле кластера."""

    llm_ram_gb: int = Field(ge=0, le=24)
    db_ram_gb: int = Field(ge=0, le=24)
    reserve_gb: int = Field(ge=2, le=12, default=4)


class ClusterPlanProposal(BaseModel):
    """Кросс-узловой план размещения сервисов на hippo (24 GiB) и rhino (16 GiB)."""

    hippo: NodeAllocation
    rhino: NodeAllocation


class ClusterVerdict(BaseModel):
    """Вердикт Z3 для двух-узлового кластера с диагностикой нарушенных инвариантов."""

    status: Literal["SAT", "UNSAT"]
    plan: ClusterPlanProposal
    hippo_slack_gb: int | None = None
    rhino_slack_gb: int | None = None
    violations: list[str] = Field(default_factory=list)
