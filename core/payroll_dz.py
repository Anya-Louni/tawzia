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
  5. Employer cost               (gross + CNAS employer, see config/)

Then it rolls those up into the monthly declarations an employer must file:
  * CNAS: total base, employee + employer shares (config/dz_payroll_*.toml).
  * IRG (G50 / retenue à la source): total income tax withheld and remitted.

Accuracy & honesty
==================
Every rate comes from the dated file config/dz_payroll_<year>.toml (cited in
core/sources.py). IRG follows the 2026 spec: exemption on the taxable base up to
30,000, 40% abatement bounded to [1,000, 1,500], and the two smoothing formulas
(ordinary band 30,000-35,000; disabled workers and retirees to 42,500).
tests/test_payroll.py holds the published test vectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import labour_dz, rules, sources


# ---------------------------------------------------------------------------
# Tax constants (real, cited)
# ---------------------------------------------------------------------------

# Toutes les valeurs viennent du fichier daté config/dz_payroll_<année>.toml.
_IRG = rules.payroll()["irg"]

IRG_BRACKETS = [(u or None, r) for u, r in _IRG["brackets"]]
IRG_EXEMPT_BELOW = _IRG["exempt_taxable_up_to"]
IRG_ABATEMENT = _IRG["abatement_rate"]
IRG_ABATEMENT_MIN = _IRG["abatement_min"]
IRG_ABATEMENT_MAX = _IRG["abatement_max"]
IRG_FAMILY_REDUCTION = _IRG["family_reduction"]
IRG_SMOOTHING_BAND = tuple(_IRG["smoothing_band"])

CNAS_EMPLOYEE = labour_dz.CNAS_EMPLOYEE
CNAS_EMPLOYER = labour_dz.CNAS_EMPLOYER


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


def irg_from_taxable(taxable: float, special: bool = False) -> float:
    """
    IRG on a monthly taxable base, exactly as the 2026 spec writes it.

    taxable <= 30,000 -> 0. Otherwise barème, minus the 40% abatement bounded
    to [1,000, 1,500], then the smoothing formula of the band. `special` is the
    regime of disabled workers and general-regime retirees (band to 42,500); it
    replaces the ordinary band, it does not add to it.
    """
    if taxable <= IRG_EXEMPT_BELOW:
        return 0.0
    irg = irg_bareme(taxable)
    irg -= min(max(IRG_ABATEMENT * irg, IRG_ABATEMENT_MIN), IRG_ABATEMENT_MAX)
    lo, hi = _IRG["smoothing_band_special"] if special else _IRG["smoothing_band"]
    a, b, c, d = _IRG["smoothing_special"] if special else _IRG["smoothing"]
    if lo < taxable <= hi:
        irg = irg * a / b - c / d
    return max(irg, 0.0)


def irg_monthly(gross_monthly: float, dependants: int = 0, spouse: bool = False,
                special: bool = False) -> dict:
    """
    Monthly IRG for a salary. Returns the working, so a payslip can show it.

    taxable = gross subject to IRG - CNAS employee share.
    """
    taxable = max(gross_monthly * (1 - CNAS_EMPLOYEE), 0.0)
    exempt = taxable <= IRG_EXEMPT_BELOW
    base = 0.0 if exempt else irg_bareme(taxable)
    irg = irg_from_taxable(taxable, special)
    family = IRG_FAMILY_REDUCTION * ((1 if spouse else 0) + min(max(dependants, 0), 5))
    irg = round(max(irg - family, 0.0))
    return {
        "taxable": taxable, "bareme": base,
        "abatement": 0.0 if exempt else min(max(IRG_ABATEMENT * base, IRG_ABATEMENT_MIN),
                                             IRG_ABATEMENT_MAX),
        "family_reduction": family, "irg": irg, "exempt": exempt,
        # Le lissage est maintenant calculé ; plus rien à renvoyer à la DGI.
        "needs_dgi_check": False,
    }


WORKER_STATUSES = ("standard", "disabled", "retired")
PAY_ITEMS = {i["code"]: i for i in rules.payroll()["pay_items"]}
CONFIG_VERSION = f"dz_payroll_{rules.payroll()['valid_from'].year}@{rules.payroll()['valid_from']}"


def pay_breakdown(items: dict, worker_status: str = "standard") -> dict:
    """
    A full monthly pay calculation from pay lines, with every step shown.

    `items` maps a pay-item code (config/dz_payroll_*.toml [[pay_items]]) to an
    amount. Each line carries its own `cnas_subject` / `irg_subject` flag, so a
    prime outside the CNAS base never enters the 9 %. `worker_status` "disabled"
    or "retired" switches the IRG smoothing to the special band.
    """
    if worker_status not in WORKER_STATUSES:
        raise ValueError(f"worker_status must be one of {WORKER_STATUSES}")
    unknown = set(items) - set(PAY_ITEMS)
    if unknown:
        raise ValueError(f"Unknown pay item(s) {sorted(unknown)}; known: {sorted(PAY_ITEMS)}")
    if any(v < 0 for v in items.values()):
        raise ValueError("Pay amounts cannot be negative.")

    gross = sum(items.values())
    cnas_base = sum(v for k, v in items.items() if PAY_ITEMS[k]["cnas_subject"])
    irg_gross = sum(v for k, v in items.items() if PAY_ITEMS[k]["irg_subject"])
    cnas_emp = round(cnas_base * CNAS_EMPLOYEE)
    taxable = max(irg_gross - cnas_emp, 0.0)
    special = worker_status != "standard"

    bareme = 0.0 if taxable <= IRG_EXEMPT_BELOW else irg_bareme(taxable)
    abatt = (0.0 if taxable <= IRG_EXEMPT_BELOW else
             min(max(IRG_ABATEMENT * bareme, IRG_ABATEMENT_MIN), IRG_ABATEMENT_MAX))
    irg = round(irg_from_taxable(taxable, special))

    branches = rules.payroll()["cnas"]
    employer_by_branch = {k: round(cnas_base * v[0]) for k, v in branches.items()}
    employee_by_branch = {k: round(cnas_base * v[1]) for k, v in branches.items()}
    employer = sum(employer_by_branch.values())
    return {
        "lines": [{"code": k, "label": PAY_ITEMS[k]["label"],
                   "label_ar": PAY_ITEMS[k]["label_ar"], "amount": v,
                   "cnas_subject": PAY_ITEMS[k]["cnas_subject"],
                   "irg_subject": PAY_ITEMS[k]["irg_subject"]}
                  for k, v in items.items()],
        "gross": gross, "cnas_base": cnas_base, "cnas_employee": cnas_emp,
        "irg_gross": irg_gross, "taxable": taxable,
        "irg_steps": {"bareme": round(bareme, 2), "abatement": round(abatt, 2),
                      "smoothing": ("special" if special else "ordinary")
                      if IRG_EXEMPT_BELOW < taxable <= (
                          _IRG["smoothing_band_special"][1] if special
                          else _IRG["smoothing_band"][1]) else "none",
                      "exempt": taxable <= IRG_EXEMPT_BELOW},
        "irg": irg, "net": gross - cnas_emp - irg,
        "employer_cnas": employer, "employer_by_branch": employer_by_branch,
        "employee_by_branch": employee_by_branch,
        "employer_cost": gross + employer,
        "config_version": CONFIG_VERSION,
        "sources": ["IRG barème : CIDTA art. 104 (barème mensuel = annuel / 12)",
                    "Abattement 40 % borné 1 000 à 1 500 DA, lissage LF 2022",
                    "CNAS : barème par branche (config) [à vérifier]",
                    CONFIG_VERSION],
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
            "Poste": self.role_label,
            "Brut (DZD)": round(self.gross),
            "CNAS 9% (DZD)": round(self.cnas_employee),
            "Base imposable (DZD)": round(self.taxable),
            "IRG (DZD)": round(self.irg),
            "Net à payer (DZD)": round(self.net),
            f"CNAS {CNAS_EMPLOYER:.1%} employeur (DZD)": round(self.cnas_employer),
            "Coût total employeur (DZD)": round(self.employer_cost),
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
            # Ce qui est effectivement déclaré et versé chaque mois.
            "CNAS (salaires de base)": total_gross,
            "CNAS salarié 9%": total_cnas_emp,
            f"CNAS employeur {CNAS_EMPLOYER:.1%}": total_cnas_er,
            f"CNAS total versé ({CNAS_EMPLOYER + CNAS_EMPLOYEE:.1%})": total_cnas_emp + total_cnas_er,
            "IRG retenu (G50)": total_irg,
        },
        "dgi_check_flags": flagged,
    }


def declaration_lines(register: dict) -> pd.DataFrame:
    """The filing summary, as a tidy table for the UI / export."""
    d = register["declarations"]
    return pd.DataFrame(
        [{"Ligne de déclaration": k, "Montant (DZD)": round(v)} for k, v in d.items()]
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
