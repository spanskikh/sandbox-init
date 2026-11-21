from __future__ import annotations

from collections.abc import Generator

import pytest
from pydantic import ValidationError

from sandbox_init.contracts import AllocationProposal
from sandbox_init.store import AuditStore
from sandbox_init.verifier import verify_allocation


@pytest.fixture
def memory_store() -> Generator[AuditStore, None, None]:
    store = AuditStore(":memory:")
    yield store
    store.close()


@pytest.mark.parametrize(
    ("node", "llm_gb", "db_gb", "budget_gb", "expected_status", "expected_slack"),
    [
        ("hippo", 8, 2, 24, "SAT", 10),
        ("rhino", 4, 4, 16, "SAT", 4),
        ("rhino", 10, 4, 16, "UNSAT", None),
    ],
)
def test_z3_allocation_invariants(
    memory_store: AuditStore,
    node: str,
    llm_gb: int,
    db_gb: int,
    budget_gb: int,
    expected_status: str,
    expected_slack: int | None,
) -> None:
    prop = AllocationProposal(
        node=node,  # type: ignore[arg-type]
        llm_ram_gb=llm_gb,
        db_ram_gb=db_gb,
        total_budget_gb=budget_gb,
    )
    verdict = verify_allocation(prop)
    memory_store.record(verdict)

    assert verdict.status == expected_status
    assert verdict.slack_gb == expected_slack
    assert memory_store.count_by_status()[expected_status] == 1


def test_pydantic_rejects_negative_ram() -> None:
    with pytest.raises(ValidationError):
        AllocationProposal(node="hippo", llm_ram_gb=-1, db_ram_gb=2, total_budget_gb=24)
