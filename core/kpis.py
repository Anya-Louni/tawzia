"""
core/kpis.py
------------
Tableau de KPI RH — the numbers a manager and a CFO actually track.

One function, `compute()`, turns the company's people + attendance + attrition
into the standard HR/payroll KPIs, each with a value, a unit, a plain-French
help line, and a health band (bon / à surveiller / critique) so the dashboard can
colour it. Every figure is derived from the real Algerian cost stack
(core/labour_dz, core/payroll_dz) and the company's own data via
core/company_data, so the same KPI reads on the imported file or the labelled
demo.

What is real vs modelled is inherited from the layers below: the wage/CNAS/IRG
figures are the cited statutory stack; the operational headcount is the company's
own (imported) or clearly-labelled simulated demo. Nothing here is invented on
top — a KPI is only ever an aggregation of those.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from . import attendance as att_mod, attrition as attr_mod, labour_dz, payroll_dz


@dataclass
class KPI:
    key: str
    label: str
    value: float
    display: str
    unit: str
    help: str
    band: str          # "bon" | "surveiller" | "critique" | "neutre"
    group: str         # "Headcount" | "Cost" | "Attendance" | "Risk"


def _band(value, good_below=None, warn_below=None, good_above=None,
          warn_above=None) -> str:
    """Simple threshold banding; direction depends on which args are given."""
    if good_below is not None:
        if value <= good_below:
            return "bon"
        if warn_below is not None and value <= warn_below:
            return "surveiller"
        return "critique"
    if good_above is not None:
        if value >= good_above:
            return "bon"
        if warn_above is not None and value >= warn_above:
            return "surveiller"
        return "critique"
    return "neutre"


def compute(people: list, records: list, as_of: Optional[_dt.date] = None) -> dict:
    """Compute the full KPI set. Returns {kpis: [KPI...], extras: {...}}."""
    as_of = as_of or _dt.date.today()
    n = len(people)
    kpis: list = []

    if n == 0:
        return {"kpis": [], "extras": {}}

    # --- Headcount ----------------------------------------------------------
    cdd = sum(1 for e in people if e.contract == "CDD")
    cdd_pct = cdd / n * 100
    seniority = [e.seniority_years(as_of) for e in people]
    avg_sen = float(np.mean(seniority))
    first_year = sum(1 for e in people if e.months_of_service(as_of) < 12)
    first_year_pct = first_year / n * 100

    kpis.append(KPI("headcount", "Headcount", n, f"{n}", "employees",
                    "Number of employees in scope.", "neutre", "Headcount"))
    kpis.append(KPI("cdd_pct", "CDD share", cdd_pct, f"{cdd_pct:.0f}%", "%",
                    "Share of fixed-term contracts: above 25%, insecurity weighs "
                    "on retention.",
                    _band(cdd_pct, good_below=15, warn_below=25), "Headcount"))
    kpis.append(KPI("avg_seniority", "Average seniority", avg_sen,
                    f"{avg_sen:.1f}", "years",
                    "Average team seniority.",
                    _band(avg_sen, good_above=3, warn_above=1.5), "Headcount"))
    kpis.append(KPI("first_year_pct", "Staff under 1 year", first_year_pct,
                    f"{first_year_pct:.0f}%", "%",
                    "Share of first-year employees: where turnover is highest.",
                    _band(first_year_pct, good_below=20, warn_below=35), "Headcount"))

    # --- Cost (payroll on the real SNMG + CNAS + IRG stack) -------------------
    slips = [payroll_dz.payslip(e.monthly_gross(), e.role_key, e.dependants, e.spouse)
             for e in people]
    gross = sum(s.gross for s in slips)
    employer_cost = sum(s.employer_cost for s in slips)
    cnas_total = sum(s.cnas_employee + s.cnas_employer for s in slips)
    irg_total = sum(s.irg for s in slips)
    net_total = sum(s.net for s in slips)
    load_pct = (employer_cost / gross - 1) * 100 if gross else 0

    kpis.append(KPI("wage_bill", "Wage bill (gross)", gross,
                    _dzd(gross), "DZD/month",
                    "Total monthly gross salaries.", "neutre", "Cost"))
    kpis.append(KPI("employer_cost", "Total employer cost", employer_cost,
                    _dzd(employer_cost), "DZD/month",
                    f"Gross + CNAS employer share ({labour_dz.CNAS_EMPLOYER:.1%}). The real monthly cost.",
                    "neutre", "Cost"))
    kpis.append(KPI("charges_load", "Employer contributions", load_pct,
                    f"+{load_pct:.0f}%", "%",
                    "Employer contributions on top of gross.",
                    "neutre", "Cost"))
    kpis.append(KPI("cnas_due", "CNAS due", cnas_total,
                    _dzd(cnas_total), "DZD/month",
                    f"CNAS contributions, employee {labour_dz.CNAS_EMPLOYEE:.0%} + employer {labour_dz.CNAS_EMPLOYER:.1%}.",
                    "neutre", "Cost"))
    kpis.append(KPI("irg_due", "IRG withheld (G50)", irg_total,
                    _dzd(irg_total), "DZD/month",
                    "Income tax withheld at source, to pay over.",
                    "neutre", "Cost"))

    # --- Attendance ----------------------------------------------------------
    summ = att_mod.lateness_summary(records)
    if not summ.empty:
        absent = float(summ["Absent %"].mean())
        late = float(summ["Late %"].mean())
        # absenteeism cost: absent shifts priced at the loaded daily cost + temp backfill
        role_keys = {e.emp_id: e.role_key for e in people}
        abs_cost = _absence_cost(records, role_keys)
    else:
        absent = late = abs_cost = 0.0

    kpis.append(KPI("absenteeism", "Absenteeism", absent,
                    f"{absent:.1f}%", "%",
                    "Share of shifts missed. Above 8%, service and backfill cost "
                    "break down.",
                    _band(absent, good_below=5, warn_below=8), "Attendance"))
    kpis.append(KPI("lateness", "Lateness", late,
                    f"{late:.1f}%", "%",
                    "Share of shifts started late.",
                    _band(late, good_below=10, warn_below=20), "Attendance"))
    kpis.append(KPI("absence_cost", "Monthly cost of absence", abs_cost,
                    _dzd(abs_cost), "DZD/month",
                    "Missed shifts at loaded cost, temp backfill included.", "neutre", "Attendance"))

    # --- Risk (attrition + leave liability) --------------------------------
    risk_df = attr_mod.score_workforce(people, records, as_of)
    risk = attr_mod.summary(risk_df)
    leave_liab = _leave_liability(people, as_of)

    kpis.append(KPI("attrition_risk", "Average leaving risk", risk["avg_risk"],
                    f"{risk['avg_risk']:.0f}%", "%",
                    "Average 6-month leaving probability (attrition model).",
                    _band(risk["avg_risk"], good_below=15, warn_below=25), "Risk"))
    kpis.append(KPI("high_risk", "High-risk employees", risk["high"],
                    f"{risk['high']}", "employees",
                    "Employees in the high-risk band, to handle first.",
                    _band(risk["high"], good_below=max(1, n * 0.05),
                          warn_below=max(2, n * 0.12)), "Risk"))
    kpis.append(KPI("cost_at_risk", "Turnover cost at risk", risk["cost_at_risk"],
                    _dzd(risk["cost_at_risk"]), "DZD",
                    "Replacement cost weighted by leaving risk.",
                    "neutre", "Risk"))
    kpis.append(KPI("leave_liability", "Leave liability (accrued balance)", leave_liab,
                    _dzd(leave_liab), "DZD",
                    "Value of accrued, untaken leave: a balance-sheet liability.",
                    "neutre", "Risk"))

    return {
        "kpis": kpis,
        "extras": {
            "risk_frame": risk_df,
            "attendance_summary": summ,
            "net_total": net_total,
            "as_of": as_of,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dzd(n: float) -> str:
    if abs(n) >= 1e6:
        return f"{n / 1e6:,.2f} M DZD"
    if abs(n) >= 1e3:
        return f"{n / 1e3:,.0f} k DZD"
    return f"{n:,.0f} DZD"


def _absence_cost(records: list, role_keys: dict) -> float:
    """Monthly-equivalent cost of absent shifts, backfilled at temp rates."""
    if not records:
        return 0.0
    days = len({r.date for r in records}) or 1
    absent = [r for r in records if r.flag == "absent"]
    total = 0.0
    for r in absent:
        role = labour_dz.ROLES.get(role_keys.get(r.emp_id, "sorter"))
        if role is None:
            continue
        hours = labour_dz.SHIFTS["morning"].hours
        # cost of the lost shift plus a temp backfill at the agency markup
        total += role.hour_cost(temp=True) * hours
    # scale the observed window up to a ~22-working-day month
    return total / days * 22


def _leave_liability(people: list, as_of: _dt.date) -> float:
    """DZD value of accrued-but-unused annual leave across the workforce."""
    total = 0.0
    for e in people:
        daily = e.monthly_gross() / payroll_dz.SHIFTS_PER_FT_MONTH
        total += e.accrued_leave(as_of) * daily
    return total


def kpi_frame(kpis: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "Group": k.group, "Indicator": k.label, "Value": k.display,
        "Status": k.band,
    } for k in kpis])


if __name__ == "__main__":
    from . import hr

    print("KPI board, self check\n")
    people = hr.sample_workforce("sorter", 60, "Alger")
    records = att_mod.sample_attendance(people, days=20)
    res = compute(people, records)
    for g in ["Headcount", "Cost", "Attendance", "Risk"]:
        print(f"— {g} —")
        for k in res["kpis"]:
            if k.group == g:
                tag = {"bon": "OK", "surveiller": "!", "critique": "X"}.get(k.band, "-")
                print(f"  [{tag}] {k.label:<32} {k.display}")
        print()
