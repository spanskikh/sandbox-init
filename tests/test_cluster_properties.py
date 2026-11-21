from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from sandbox_init.contracts import ClusterPlanProposal, NodeAllocation
from sandbox_init.verifier import HIPPO_MAX_RAM_GB, RHINO_MAX_RAM_GB, verify_cluster_plan


def _reference_oracle(plan: ClusterPlanProposal) -> bool:
    """Независимый булев оракул для проверки эквивалентности Z3-модели."""
    h, r = plan.hippo, plan.rhino
    h_used = h.llm_ram_gb + h.db_ram_gb + h.reserve_gb
    r_used = r.llm_ram_gb + r.db_ram_gb + r.reserve_gb
    if h.reserve_gb < 4 or h_used > HIPPO_MAX_RAM_GB:
        return False
    if r.reserve_gb < 3 or r_used > RHINO_MAX_RAM_GB:
        return False
    if (h.llm_ram_gb + r.llm_ram_gb) < 4 or (h.db_ram_gb + r.db_ram_gb) < 2:
        return False
    if r.llm_ram_gb > 6 and r.db_ram_gb > 4:
        return False
    if (HIPPO_MAX_RAM_GB - h_used) < 4 and (RHINO_MAX_RAM_GB - r_used) < 4:
        return False
    return True


@settings(max_examples=150, deadline=None)
@given(
    h_llm=st.integers(min_value=0, max_value=20),
    h_db=st.integers(min_value=0, max_value=12),
    h_res=st.integers(min_value=2, max_value=8),
    r_llm=st.integers(min_value=0, max_value=14),
    r_db=st.integers(min_value=0, max_value=10),
    r_res=st.integers(min_value=2, max_value=8),
)
def test_z3_matches_oracle_across_random_cluster_plans(
    h_llm: int,
    h_db: int,
    h_res: int,
    r_llm: int,
    r_db: int,
    r_res: int,
) -> None:
    plan = ClusterPlanProposal(
        hippo=NodeAllocation(llm_ram_gb=h_llm, db_ram_gb=h_db, reserve_gb=h_res),
        rhino=NodeAllocation(llm_ram_gb=r_llm, db_ram_gb=r_db, reserve_gb=r_res),
    )
    verdict = verify_cluster_plan(plan)
    expected_sat = _reference_oracle(plan)

    assert (verdict.status == "SAT") is expected_sat
    if expected_sat:
        assert verdict.violations == []
        assert verdict.hippo_slack_gb is not None and verdict.hippo_slack_gb >= 0
        assert verdict.rhino_slack_gb is not None and verdict.rhino_slack_gb >= 0
    else:
        assert len(verdict.violations) >= 1
