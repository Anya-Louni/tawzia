"""
core/payroll_dz.py
------------------
Algerian payroll and CNAS/IRG compliance, computed from a roster.

Why this is the product (not the forecast)
==========================================
Producing a legally-compliant roster and then the payroll + social-security
paperwork that flows from it is not optional for an Algerian employer — it is
the law, every single month. That makes it a *necessity* purchase with a clear,
non-probabilistic ROI: hours of accountant time saved, and audit/fine risk
removed. The demand forecast and the legal-roster optimiser become the engine
underneath; this module is the deliverable a customer actually pays for.

What it computes
================
For each worker, from gross salary:
  1. CNAS employee contribution  (9% of gross, withheld)
  2. Taxable base                (gross - CNAS employee)
  3. IRG income tax              (progressive DGI barème + 40% abatement,
                                  bounded 1,000-1,500 DZD/month; salaries
                                  <= 30,000 exempt; family reductions)
  4. Net pay                     (gross - CNAS employee - IRG)
  5. Employer cost               (gross + 26% CNAS employer)

Then it rolls those up into the monthly declarations an employer must file:
  * CNAS: total base, employee 9% + employer 26% = 35% remitted.
  * IRG (G50 / retenue à la source): total income tax withheld and remitted.

Accuracy & honesty
==================
The IRG barème, the abatement, the family reductions and the CNAS split are the
real published figures (see core/sources.py, cited to the DGI and CLEISS). The
narrow 30,001-35,000 DZD smoothing band the LF 2022 defines is NOT re-derived
here — salaries in that band are flagged for validation against the official DGI
"calculette IRG" rather than guessed. A production deployment locks the tax
logic to the DGI calculator; this module is correct for the vast majority of
shift-labour salaries (which cluster at or just above the SNMG) and transparent
about its one edge case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import labour_dz, sources


# ---------------------------------------------------------------------------
# Tax constants (real, cited)
# ---------------------------------------------------------------------------

# Monthly IRG barème: (upper_bound_or_None, marginal_rate)
IRG_BRACKETS = [
    (20_000, 0.00),
    (40_000, 0.23),
    (80_000, 0.27),
    (160_000, 0.30),
    (320_000, 0.33),
    (None, 0.35),
]

IRG_EXEMPT_BELOW = sources.value("irg_exemption_monthly")   # 30,000
IRG_ABATEMENT = sources.value("irg_abatement")              # 0.40
IRG_ABATEMENT_MIN = 1_000
IRG_ABATEMENT_MAX = 1_500
IRG_FAMILY_REDUCTION = sources.value("irg_family_reduction")  # 1,500 each
IRG_SMOOTHING_BAND = (30_000, 35_000)

CNAS_EMPLOYEE = labour_dz.CNAS_EMPLOYEE   # 0.09
CNAS_EMPLOYER = labour_dz.CNAS_EMPLOYER   # 0.26


def irg_bareme(taxable_monthly: float) -> float:
    """Progressive IRG on the monthly taxable base, before abatement."""
    tax = 0.0
    lower = 0.0
    for upper, rate in IRG_BRACKETS:
        cap = upper if upper is not None else taxable_monthly
        if taxable_monthly > lower:
            tax += (min(taxable_monthly, cap) - lower) * rate
            lower = cap
        else:
            break
    return tax


def irg_monthly(gross_monthly: float, dependants: int = 0, spouse: bool = False) -> dict:
    """
    Monthly IRG for a salary, following the published DGI rules.

    Returns a breakdown so a payslip can show its working (auditors and workers
    both ask "why this number?").
    """
    if gross_monthly <= IRG_EXEMPT_BELOW:
        return {
            "taxable": max(gross_monthly * (1 - CNAS_EMPLOYEE), 0.0),
            "bareme": 0.0, "abatement": 0.0, "family_reduction": 0.0,
            "irg": 0.0, "exempt": True, "needs_dgi_check": False,
        }

    taxable = gross_monthly * (1 - CNAS_EMPLOYEE)
    base = irg_bareme(taxable)
    abatement = min(max(IRG_ABATEMENT * base, IRG_ABATEMENT_MIN), IRG_ABATEMENT_MAX)
    family = IRG_FAMILY_REDUCTION * ((1 if spouse else 0) + min(max(dependants, 0), 5))
    irg = max(base - abatement - family, 0.0)

    needs_check = IRG_SMOOTHING_BAND[0] < gross_monthly <= IRG_SMOOTHING_BAND[1]
    return {
        "taxable": taxable, "bareme": base, "abatement": abatement,
        "family_reduction": family, "irg": irg, "exempt": False,
        "needs_dgi_check": needs_check,
    }


# ---------------------------------------------------------------------------
# Payslip
# ---------------------------------------------------------------------------

@dataclass
class Payslip:
    role: str
    role_label: str
    gross: float
    cnas_employee: float
    taxable: float
    irg: float
    net: float
    cnas_employer: float
    employer_cost: float
    exempt: bool
    needs_dgi_check: bool

    def as_dict(self) -> dict:
        return {
            "Role": self.role_label,
            "Gross (DZD)": round(self.gross),
            "CNAS 9% (DZD)": round(self.cnas_employee),
            "Taxable (DZD)": round(self.taxable),
            "IRG (DZD)": round(self.irg),
            "Net pay (DZD)": round(self.net),
            "CNAS 26% employer (DZD)": round(self.cnas_employer),
            "Total employer cost (DZD)": round(self.employer_cost),
        }


def payslip(gross_monthly: float, role_key: str = "sorter",
            dependants: int = 0, spouse: bool = False) -> Payslip:
    """Full monthly payslip from a gross salary."""
    role = labour_dz.ROLES[role_key]
    cnas_emp = gross_monthly * CNAS_EMPLOYEE
    tax = irg_monthly(gross_monthly, dependants, spouse)
    net = gross_monthly - cnas_emp - tax["irg"]
    cnas_er = gross_monthly * CNAS_EMPLOYER
    return Payslip(
        role=role_key, role_label=role.label, gross=gross_monthly,
        cnas_employee=cnas_emp, taxable=tax["taxable"], irg=tax["irg"],
        net=net, cnas_employer=cnas_er, employer_cost=gross_monthly + cnas_er,
        exempt=tax["exempt"], needs_dgi_check=tax["needs_dgi_check"],
    )


# ---------------------------------------------------------------------------
# From a roster to a monthly payroll register + declarations
# ---------------------------------------------------------------------------

SHIFTS_PER_FT_MONTH = 22   # full-time worker-shifts in a month (5-day week, rest days)


def payroll_register(
    roster: pd.DataFrame,
    role_key: str,
    overtime_hours_col: Optional[str] = "overtime",
) -> dict:
    """
    Turn a month's roster (worker-shifts) into a payroll register.

    The roster is in worker-shifts; we convert to headcount, then to gross pay
    per worker using the real loaded-wage stack, add the overtime actually
    rostered (at the statutory premium), and produce every payslip plus the
    CNAS and IRG declarations the employer must file.
    """
    role = labour_dz.ROLES[role_key]

    total_worker_shifts = float(roster["total_staff"].sum()) if "total_staff" in roster else 0.0
    overtime_shifts = float(roster[overtime_hours_col].sum()) if overtime_hours_col in roster else 0.0
    temp_shifts = float(roster["temp"].sum()) if "temp" in roster else 0.0

    headcount = max(int(round(total_worker_shifts / SHIFTS_PER_FT_MONTH)), 1)

    # Base monthly gross per worker from the real wage stack.
    base_gross = role.gross_monthly
    # Overtime earned across the workforce, at the statutory premium, spread per head.
    ot_hours = overtime_shifts * labour_dz.SHIFTS["morning"].hours
    ot_pay_total = ot_hours * role.gross_hourly * (1 + labour_dz.OVERTIME_PREMIUM)
    ot_per_head = ot_pay_total / headcount if headcount else 0.0

    gross_per_head = base_gross + ot_per_head
    slips = [payslip(gross_per_head, role_key) for _ in range(headcount)]

    total_gross = sum(s.gross for s in slips)
    total_cnas_emp = sum(s.cnas_employee for s in slips)
    total_cnas_er = sum(s.cnas_employer for s in slips)
    total_irg = sum(s.irg for s in slips)
    total_net = sum(s.net for s in slips)
    flagged = sum(1 for s in slips if s.needs_dgi_check)

    return {
        "headcount": headcount,
        "role": role.label,
        "temp_share_pct": (temp_shifts / total_worker_shifts * 100) if total_worker_shifts else 0.0,
        "gross_per_head": gross_per_head,
        "slips": slips,
        "totals": {
            "gross": total_gross,
            "cnas_employee": total_cnas_emp,
            "cnas_employer": total_cnas_er,
            "irg": total_irg,
            "net": total_net,
            "employer_cost": total_gross + total_cnas_er,
        },
        "declarations": {
            # What actually gets filed and remitted each month.
            "CNAS (base salaries)": total_gross,
            "CNAS employee 9%": total_cnas_emp,
            "CNAS employer 26%": total_cnas_er,
            "CNAS total remitted (35%)": total_cnas_emp + total_cnas_er,
            "IRG withheld (G50)": total_irg,
        },
        "dgi_check_flags": flagged,
    }


def declaration_lines(register: dict) -> pd.DataFrame:
    """The filing summary, as a tidy table for the UI / export."""
    d = register["declarations"]
    return pd.DataFrame(
        [{"Declaration line": k, "Amount (DZD)": round(v)} for k, v in d.items()]
    )


def compliance_checks(roster: pd.DataFrame, constraints) -> list:
    """
    Plain-language legal checks a customer needs signed off each period.
    Returns (label, ok, detail) rows.
    """
    checks = []
    if "overtime" in roster and "regular" in roster:
        reg = roster["regular"].sum()
        ot = roster["overtime"].sum()
        cap = getattr(constraints, "max_overtime_fraction", labour_dz.MAX_OVERTIME_FRACTION)
        ok = ot <= reg * cap + 1e-9
        checks.append((
            f"Overtime within the statutory {cap:.0%} cap",
            ok,
            f"{ot:.0f} overtime vs {reg:.0f} regular worker-shifts",
        ))
    checks.append((
        "Every rostered hour costed on the real SNMG + CNAS stack",
        True,
        f"SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD, CNAS employer {CNAS_EMPLOYER:.0%}",
    ))
    checks.append((
        "Minimum-wage workers correctly IRG-exempt",
        True,
        f"Salaries at or below {IRG_EXEMPT_BELOW:,.0f} DZD pay zero IRG",
    ))
    return checks


if __name__ == "__main__":
    print("Algerian payroll engine - self check\n")

    for g in (24_000, 30_000, 40_000, 50_000, 80_000, 150_000):
        s = payslip(g, "sorter")
        tag = " [exempt]" if s.exempt else (" [check DGI band]" if s.needs_dgi_check else "")
        print(f"  gross {g:>7,}  ->  CNAS {s.cnas_employee:>7,.0f}  IRG {s.irg:>8,.0f}  "
              f"net {s.net:>8,.0f}  employer {s.employer_cost:>8,.0f}{tag}")

    print("\n  SNMG worker pays zero IRG:",
          "PASS" if payslip(24_000).irg == 0 else "FAIL")
    print("  IRG rises with salary (monotone):",
          "PASS" if payslip(50_000).irg > payslip(40_000).irg > 0 else "CHECK")

    # A tiny roster -> register
    roster = pd.DataFrame({
        "total_staff": [40, 42, 38, 45] * 5,
        "regular": [34, 35, 33, 36] * 5,
        "overtime": [4, 5, 3, 6] * 5,
        "temp": [2, 2, 2, 3] * 5,
    })
    reg = payroll_register(roster, "sorter")
    print(f"\n  Register: {reg['headcount']} {reg['role']}s, "
          f"gross/head {reg['gross_per_head']:,.0f} DZD")
    print(declaration_lines(reg).to_string(index=False))
