"""
core/scenarios.py
-----------------
Scenario simulator: the costed "what if?".

A manager's real questions are conditional: *what if we raise pay 8%? hire five
more? cut absenteeism to 4%? if the SNMG rises again? if we lean on overtime
instead of temps?* Each one moves the wage bill, the CNAS/IRG the employer
remits, the coverage of demand, and the attrition risk — and they interact. This
module recomputes the whole picture under a set of levers, deterministically, off
the company's own baseline (core/company_data via the caller), so the answer is a
number the CFO can act on, not a hunch.

Every lever maps to a real mechanism already modelled elsewhere:
  * wage_increase_pct / snmg_change_pct -> re-price on core/labour_dz + payroll_dz
  * headcount_change                    -> add/remove staff at the role's loaded cost
  * absenteeism_target_pct              -> value the recovered absence via core/kpis
  * overtime_vs_temp_shift              -> swap temp-agency markup for overtime premium
  * attrition drivers (pay, absence)    -> re-score risk via core/attrition

The baseline and every scenario are shown side by side with the delta, so there
is no black box: the user sees exactly which lever moved which line.
"""

from __future__ import annotations

import copy
import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import attendance as att_mod, attrition as attr_mod, labour_dz, payroll_dz


@dataclass
class Levers:
    """The knobs a user turns. All default to 'no change'."""
    wage_increase_pct: float = 0.0        # +% on every gross salary
    snmg_change_pct: float = 0.0          # +% on the national minimum (re-floors pay)
    headcount_change: int = 0             # +/- permanent employees (at role cost)
    absenteeism_target_pct: Optional[float] = None   # drive absence toward this %
    overtime_share: float = 0.0           # fraction of temp cover moved to overtime
    new_role_key: str = "sorter"          # role used for added headcount

    def is_baseline(self) -> bool:
        return (self.wage_increase_pct == 0 and self.snmg_change_pct == 0
                and self.headcount_change == 0 and self.absenteeism_target_pct is None
                and self.overtime_share == 0)


@dataclass
class Outcome:
    label: str
    headcount: int
    wage_bill: float          # gross monthly
    employer_cost: float      # gross + CNAS employer
    cnas_due: float
    irg_due: float
    absence_cost: float
    attrition_risk: float     # avg %
    cost_at_risk: float
    total_monthly: float      # employer_cost + absence_cost (the money that leaves)

    def row(self) -> dict:
        return {
            "Scenario": self.label,
            "Headcount": self.headcount,
            "Wage bill": self.wage_bill,
            "Employer cost": self.employer_cost,
            "CNAS": self.cnas_due,
            "IRG (G50)": self.irg_due,
            "Absence cost": self.absence_cost,
            "Leaving risk %": round(self.attrition_risk, 1),
            "Total cost/month": self.total_monthly,
        }


def _effective_gross(emp, levers: Levers) -> float:
    """Gross after wage and SNMG levers, starting from the actual current pay."""
    # Actual gross (imported salary if present, else role + seniority).
    base = emp.monthly_gross()
    if levers.snmg_change_pct:
        # a SNMG rise lifts the whole coefficient-indexed stack proportionally
        base *= (1 + levers.snmg_change_pct / 100.0)
    gross = base * (1 + levers.wage_increase_pct / 100.0)
    # never below the (possibly raised) legal floor
    floor = labour_dz.SNMG_MONTHLY * (1 + levers.snmg_change_pct / 100.0)
    return max(gross, floor)


def _added_people(people: list, levers: Levers) -> list:
    """Clone template employees for a positive headcount change."""
    if levers.headcount_change <= 0 or not people:
        return []
    from . import hr
    template = next((e for e in people if e.role_key == levers.new_role_key), people[0])
    added = []
    for i in range(levers.headcount_change):
        e = copy.copy(template)
        e.emp_id = f"NEW{i+1}"
        e.name = f"New hire {i+1}"
        e.hire_date = _dt.date.today()
        e.leave_taken_ytd = 0.0
        e.role_key = levers.new_role_key
        added.append(e)
    return added


def _evaluate(people: list, records: list, levers: Levers, label: str,
              as_of: _dt.date) -> Outcome:
    # Apply headcount change
    roster = list(people)
    if levers.headcount_change > 0:
        roster = roster + _added_people(people, levers)
    elif levers.headcount_change < 0:
        # remove the newest hires first (last-in-first-out, common in practice)
        roster = sorted(roster, key=lambda e: e.hire_date)[:max(0, len(roster) + levers.headcount_change)]
    n = len(roster)

    # Payroll under the levers
    gross = employer_cost = cnas = irg = 0.0
    for e in roster:
        g = _effective_gross(e, levers)
        slip = payroll_dz.payslip(g, e.role_key, e.dependants, e.spouse)
        gross += slip.gross
        employer_cost += slip.employer_cost
        cnas += slip.cnas_employee + slip.cnas_employer
        irg += slip.irg

    # Absence cost, optionally reduced toward a target
    role_keys = {e.emp_id: e.role_key for e in roster}
    abs_cost = _absence_cost(records, role_keys, levers)

    # Attrition risk under pay + absence levers (re-score on adjusted inputs)
    risk_avg, cost_at_risk = _attrition_under(roster, records, levers, as_of)

    return Outcome(
        label=label, headcount=n, wage_bill=gross, employer_cost=employer_cost,
        cnas_due=cnas, irg_due=irg, absence_cost=abs_cost,
        attrition_risk=risk_avg, cost_at_risk=cost_at_risk,
        total_monthly=employer_cost + abs_cost,
    )


def _absence_cost(records: list, role_keys: dict, levers: Levers) -> float:
    if not records:
        return 0.0
    days = len({r.date for r in records}) or 1
    absent = [r for r in records if r.flag == "absent"]
    total_shifts = len({(r.emp_id, r.date) for r in records}) or 1
    base_rate = len(absent) / total_shifts
    # if a target is set and it's below the current rate, scale the absences down
    keep = 1.0
    if levers.absenteeism_target_pct is not None and base_rate > 0:
        target = levers.absenteeism_target_pct / 100.0
        keep = min(1.0, target / base_rate)
    total = 0.0
    hours = labour_dz.SHIFTS["morning"].hours
    for r in absent:
        role = labour_dz.ROLES.get(role_keys.get(r.emp_id, "sorter"))
        if role is None:
            continue
        # backfill via temp, or via overtime for the overtime_share fraction
        temp_cost = role.hour_cost(temp=True) * hours
        ot_cost = role.hour_cost(overtime=True) * hours
        blended = (1 - levers.overtime_share) * temp_cost + levers.overtime_share * ot_cost
        total += blended
    return total * keep / days * 22


def _attrition_under(people: list, records: list, levers: Levers,
                     as_of: _dt.date) -> tuple:
    """Re-score attrition after nudging the pay and absence signals."""
    summ = att_mod.lateness_summary(records)
    att_by_id = {r["ID"]: dict(r) for r in summ.to_dict("records")} if not summ.empty else {}
    # apply absence target proportionally to each worker's absence
    if levers.absenteeism_target_pct is not None and not summ.empty:
        cur = summ["Absent %"].mean()
        if cur > 0:
            factor = min(1.0, levers.absenteeism_target_pct / cur)
            for k in att_by_id:
                att_by_id[k]["Absent %"] = att_by_id[k]["Absent %"] * factor

    rows = []
    for e in people:
        # temporarily reflect the wage lever in the pay-driven risk feature
        e2 = copy.copy(e)
        s = attr_mod.score_employee(e2, att_by_id.get(e.emp_id), as_of)
        # pay rise reduces the low-pay flight risk: shrink probability modestly
        p = s.probability
        if levers.wage_increase_pct or levers.snmg_change_pct:
            bump = (levers.wage_increase_pct + levers.snmg_change_pct) / 100.0
            p = max(0.01, p * (1 - min(0.5, bump * 1.5)))
        rows.append((p, s.replacement_cost))
    if not rows:
        return 0.0, 0.0
    avg = float(np.mean([p for p, _ in rows]) * 100)
    cost = float(sum(p * c for p, c in rows))
    return avg, cost


def simulate(people: list, records: list, levers: Levers,
             as_of: Optional[_dt.date] = None) -> dict:
    """Baseline vs scenario, with the delta on every line."""
    as_of = as_of or _dt.date.today()
    base = _evaluate(people, records, Levers(), "Baseline", as_of)
    scen = _evaluate(people, records, levers, "Scenario", as_of)

    deltas = {}
    for k in ("headcount", "wage_bill", "employer_cost", "cnas_due", "irg_due",
              "absence_cost", "attrition_risk", "cost_at_risk", "total_monthly"):
        deltas[k] = getattr(scen, k) - getattr(base, k)

    return {"baseline": base, "scenario": scen, "deltas": deltas,
            "levers": levers, "as_of": as_of}


def compare_frame(result: dict) -> pd.DataFrame:
    base, scen = result["baseline"], result["scenario"]
    df = pd.DataFrame([base.row(), scen.row()])
    return df


PRESETS = {
    "Pay rise +8%": Levers(wage_increase_pct=8.0),
    "SNMG rise +10%": Levers(snmg_change_pct=10.0),
    "Hire 5 permanent staff": Levers(headcount_change=5),
    "Cut absenteeism to 4%": Levers(absenteeism_target_pct=4.0),
    "Overtime instead of temps": Levers(overtime_share=0.7),
    "Growth: +10 staff, +5% pay": Levers(headcount_change=10, wage_increase_pct=5.0),
}


if __name__ == "__main__":
    from . import hr

    print("Scenario simulator, self check\n")
    people = hr.sample_workforce("sorter", 60, "Alger")
    records = att_mod.sample_attendance(people, days=20)

    for name, lev in PRESETS.items():
        r = simulate(people, records, lev)
        d = r["deltas"]
        print(f"— {name}")
        print(f"    employer cost {d['employer_cost']:+,.0f} DZD/month | "
              f"absence {d['absence_cost']:+,.0f} | "
              f"leaving risk {d['attrition_risk']:+.1f} pts | "
              f"total {d['total_monthly']:+,.0f} DZD/month")
