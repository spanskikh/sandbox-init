from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AllocationProposal(BaseModel):
    """Структурированное предложение от LLM по распределению памяти/слотов."""
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
