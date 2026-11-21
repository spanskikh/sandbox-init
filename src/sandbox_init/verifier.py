from __future__ import annotations

import z3

from sandbox_init.contracts import AllocationProposal, VerificationVerdict


def verify_allocation(prop: AllocationProposal) -> VerificationVerdict:
    """Проверяет инварианты распределения RAM через Z3 SMT Solver."""
    solver = z3.Solver()
    llm = z3.Int("llm_ram")
    db = z3.Int("db_ram")
    reserve = z3.Int("reserve")

    # Жёсткие инварианты кластера
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
