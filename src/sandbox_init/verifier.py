from __future__ import annotations

import z3

from sandbox_init.contracts import (
    AllocationProposal,
    ClusterPlanProposal,
    ClusterVerdict,
    VerificationVerdict,
)

HIPPO_MAX_RAM_GB = 24
RHINO_MAX_RAM_GB = 16


def verify_allocation(prop: AllocationProposal) -> VerificationVerdict:
    """Проверяет инварианты распределения RAM одного узла через Z3 SMT Solver."""
    solver = z3.Solver()
    llm = z3.Int("llm_ram")
    db = z3.Int("db_ram")
    reserve = z3.Int("reserve")

    solver.add(llm == prop.llm_ram_gb)
    solver.add(db == prop.db_ram_gb)
    solver.add(reserve == prop.reserve_gb)
    solver.add(llm + db + reserve <= prop.total_budget_gb)
    solver.add(llm >= 1, db >= 1)

    if solver.check() == z3.sat:
        slack = prop.total_budget_gb - (prop.llm_ram_gb + prop.db_ram_gb + prop.reserve_gb)
        return VerificationVerdict(status="SAT", proposal=prop, slack_gb=slack)

    overflow = (prop.llm_ram_gb + prop.db_ram_gb + prop.reserve_gb) - prop.total_budget_gb
    reason = f"Budget exceeded by {overflow} GiB (limit={prop.total_budget_gb} GiB)"
    return VerificationVerdict(status="UNSAT", proposal=prop, counterexample=reason)


def verify_cluster_plan(plan: ClusterPlanProposal) -> ClusterVerdict:
    """Проверяет кросс-узловые инварианты hippo (24 GiB) + rhino (16 GiB) через Z3."""
    solver = z3.Solver()

    h_llm, h_db, h_res = z3.Ints("h_llm h_db h_res")
    r_llm, r_db, r_res = z3.Ints("r_llm r_db r_res")

    solver.add(
        h_llm == plan.hippo.llm_ram_gb,
        h_db == plan.hippo.db_ram_gb,
        h_res == plan.hippo.reserve_gb,
        r_llm == plan.rhino.llm_ram_gb,
        r_db == plan.rhino.db_ram_gb,
        r_res == plan.rhino.reserve_gb,
    )

    c_hippo_budget = z3.And(h_res >= 4, h_llm + h_db + h_res <= HIPPO_MAX_RAM_GB)
    c_rhino_budget = z3.And(r_res >= 3, r_llm + r_db + r_res <= RHINO_MAX_RAM_GB)
    c_services_alive = z3.And(h_llm + r_llm >= 4, h_db + r_db >= 2)
    c_rhino_anti_affinity = z3.Implies(r_llm > 6, r_db <= 4)

    h_slack_expr = HIPPO_MAX_RAM_GB - (h_llm + h_db + h_res)
    r_slack_expr = RHINO_MAX_RAM_GB - (r_llm + r_db + r_res)
    c_dev_headroom = z3.Or(h_slack_expr >= 4, r_slack_expr >= 4)

    solver.add(
        c_hippo_budget,
        c_rhino_budget,
        c_services_alive,
        c_rhino_anti_affinity,
        c_dev_headroom,
    )

    if solver.check() == z3.sat:
        h_slack = HIPPO_MAX_RAM_GB - (
            plan.hippo.llm_ram_gb + plan.hippo.db_ram_gb + plan.hippo.reserve_gb
        )
        r_slack = RHINO_MAX_RAM_GB - (
            plan.rhino.llm_ram_gb + plan.rhino.db_ram_gb + plan.rhino.reserve_gb
        )
        return ClusterVerdict(
            status="SAT",
            plan=plan,
            hippo_slack_gb=h_slack,
            rhino_slack_gb=r_slack,
        )

    violations: list[str] = []
    if plan.hippo.reserve_gb < 4:
        violations.append("hippo reserve_gb must be >= 4 GiB")
    h_used = plan.hippo.llm_ram_gb + plan.hippo.db_ram_gb + plan.hippo.reserve_gb
    if h_used > HIPPO_MAX_RAM_GB:
        violations.append(f"hippo RAM overflow: {h_used} > {HIPPO_MAX_RAM_GB} GiB")

    if plan.rhino.reserve_gb < 3:
        violations.append("rhino reserve_gb must be >= 3 GiB")
    r_used = plan.rhino.llm_ram_gb + plan.rhino.db_ram_gb + plan.rhino.reserve_gb
    if r_used > RHINO_MAX_RAM_GB:
        violations.append(f"rhino RAM overflow: {r_used} > {RHINO_MAX_RAM_GB} GiB")

    if (plan.hippo.llm_ram_gb + plan.rhino.llm_ram_gb) < 4:
        violations.append("cluster total LLM RAM must be >= 4 GiB")
    if (plan.hippo.db_ram_gb + plan.rhino.db_ram_gb) < 2:
        violations.append("cluster total DB RAM must be >= 2 GiB")
    if plan.rhino.llm_ram_gb > 6 and plan.rhino.db_ram_gb > 4:
        violations.append("rhino anti-affinity violated: llm_ram_gb > 6 and db_ram_gb > 4")

    if (HIPPO_MAX_RAM_GB - h_used) < 4 and (RHINO_MAX_RAM_GB - r_used) < 4:
        violations.append("insufficient dev headroom: at least one node needs >= 4 GiB free")

    return ClusterVerdict(status="UNSAT", plan=plan, violations=violations)
