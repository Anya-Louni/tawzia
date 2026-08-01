"""
core/attrition.py
-----------------
The quit-seer, with real numbers.

Losing a trained worker is expensive: you re-hire, re-train, and run short-handed
(at temp-agency rates) until the replacement is up to speed. This module scores
every employee's risk of leaving in the next six months and attaches a DZD cost
to that risk, so retention stops being a gut feeling and becomes a budget line.

How the score is built (and its honesty)
=======================================
There is no public dataset of who quit which Algerian shift job, so we do NOT
pretend to have trained a model on real turnover. Instead this is a transparent,
interpretable **expected-risk model**: a logistic function of the drivers that
the HR-analytics literature consistently finds predict turnover, each with a
stated weight you can see and argue with:

    absenteeism   (strongest)   - chronic absence precedes quitting
    lateness                    - disengagement signal
    short tenure                - first-year churn is highest
    low pay                     - pay near the SNMG floor is a flight risk
    precarious contract (CDD)   - fixed-term staff leave more
    unused leave                - never taking leave signals burnout

Every input is real per-employee data (attendance, tenure, pay, contract). The
weights are a modelling choice, exposed here and on the Sources page. On a pilot
these get re-fitted to the customer's own leaver history - which is exactly the
proprietary-data moat that makes the product hard to copy.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import attendance as attendance_mod
from . import labour_dz

# Replacement cost as a multiple of one loaded monthly cost: recruit + train +
# run short-handed. Conservative; a specialised role costs more.
REPLACEMENT_COST_MONTHS = 1.75

# Logistic model weights (documented, override-on-pilot). Intercept sets a low
# baseline so an average worker reads as low risk.
W = {
    "intercept": -2.6,
    "absence": 4.2,       # x absence_rate (0..1)
    "lateness": 1.8,      # x late_rate (0..1)
    "short_tenure": 1.5,  # x short_tenure (0..1, ramps below 12 months)
    "low_pay": 1.6,       # x low_pay (0..1, gap below ~1.4x SNMG)
    "cdd": 0.9,           # + if fixed-term contract
    "unused_leave": 0.7,  # x unused_leave_ratio (0..1)
}

PAY_COMFORT = labour_dz.SNMG_MONTHLY * 1.4   # pay at/above this is not a flight risk


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class RiskScore:
    emp_id: str
    name: str
    probability: float          # 0..1, chance of leaving in 6 months
    band: str                   # low | medium | high
    drivers: list               # [(driver_label, contribution), ...] top first
    replacement_cost: float     # DZD if they leave
    expected_cost: float        # probability * replacement_cost


def _features(emp, att_row: Optional[dict], as_of: _dt.date) -> dict:
    absence = (att_row["Absent %"] / 100.0) if att_row else 0.0
    late = (att_row["Late %"] / 100.0) if att_row else 0.0
    months = emp.months_of_service(as_of)
    short_tenure = max(0.0, (12.0 - months) / 12.0)   # 1 at hire -> 0 at 12mo+
    gross = emp.monthly_gross()
    low_pay = max(0.0, (PAY_COMFORT - gross) / PAY_COMFORT)
    cdd = 1.0 if emp.contract == "CDD" else 0.0
    unused = emp.accrued_leave(as_of) / max(emp.annual_entitlement(), 1)
    return {
        "absence": absence, "lateness": late, "short_tenure": short_tenure,
        "low_pay": low_pay, "cdd": cdd, "unused_leave": min(unused, 1.0),
    }


_DRIVER_LABELS = {
    "absence": "High absenteeism",
    "lateness": "Frequent lateness",
    "short_tenure": "Short tenure (first-year churn)",
    "low_pay": "Pay near the SNMG floor",
    "cdd": "Fixed-term (CDD) contract",
    "unused_leave": "Never taking leave (burnout)",
}


def score_employee(emp, att_row: Optional[dict], as_of: Optional[_dt.date] = None) -> RiskScore:
    as_of = as_of or _dt.date.today()
    f = _features(emp, att_row, as_of)

    contributions = {k: W[k] * f[k] for k in f}
    linear = W["intercept"] + sum(contributions.values())
    p = _logistic(linear)

    band = "high" if p >= 0.45 else ("medium" if p >= 0.20 else "low")
    top = sorted(
        ((k, v) for k, v in contributions.items() if v > 0.05),
        key=lambda kv: kv[1], reverse=True,
    )[:3]
    drivers = [(_DRIVER_LABELS[k], round(v, 2)) for k, v in top]

    role = labour_dz.ROLES[emp.role_key]
    repl = role.loaded_monthly * REPLACEMENT_COST_MONTHS

    return RiskScore(
        emp_id=emp.emp_id, name=emp.name, probability=p, band=band,
        drivers=drivers, replacement_cost=repl, expected_cost=p * repl,
    )


def score_workforce(people: list, records: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """Risk table for the whole workforce, highest risk first."""
    as_of = as_of or _dt.date.today()
    summ = attendance_mod.lateness_summary(records)
    att_by_id = {r["ID"]: r for r in summ.to_dict("records")} if not summ.empty else {}

    rows = []
    for e in people:
        s = score_employee(e, att_by_id.get(e.emp_id), as_of)
        rows.append({
            "ID": s.emp_id, "Name": s.name,
            "Risk %": round(s.probability * 100, 1),
            "Band": s.band,
            "Top driver": s.drivers[0][0] if s.drivers else "-",
            "2nd driver": s.drivers[1][0] if len(s.drivers) > 1 else "",
            "Replacement cost (DZD)": round(s.replacement_cost),
            "Expected cost (DZD)": round(s.expected_cost),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("Risk %", ascending=False).reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"high": 0, "medium": 0, "expected_leavers": 0.0,
                "cost_at_risk": 0.0, "avg_risk": 0.0}
    return {
        "high": int((df["Band"] == "high").sum()),
        "medium": int((df["Band"] == "medium").sum()),
        "expected_leavers": round(df["Risk %"].sum() / 100.0, 1),
        "cost_at_risk": float(df["Expected cost (DZD)"].sum()),
        "avg_risk": float(df["Risk %"].mean()),
    }


def retention_actions(df: pd.DataFrame) -> list:
    """Turn the top risks into concrete, cheap retention moves."""
    actions = []
    if df.empty:
        return actions
    high = df[df["Band"] == "high"]
    if not high.empty:
        top = high.iloc[0]
        actions.append(
            f"Talk to {top['Name']} this week ({top['Risk %']:.0f}% risk, "
            f"{top['Top driver'].lower()}). Replacing them costs "
            f"{top['Replacement cost (DZD)']:,.0f} DZD."
        )
    pay_driven = df[df["Top driver"].str.contains("SNMG", na=False)]
    if len(pay_driven) >= 3:
        actions.append(
            f"{len(pay_driven)} at-risk workers are pay-driven. A small raise "
            f"toward {PAY_COMFORT:,.0f} DZD is cheaper than replacing them."
        )
    absent_driven = df[df["Top driver"].str.contains("absentee", case=False, na=False)]
    if not absent_driven.empty:
        actions.append(
            f"{len(absent_driven)} flagged on absenteeism - a return-to-work "
            f"conversation now beats a resignation later."
        )
    return actions


if __name__ == "__main__":
    from . import hr

    print("Attrition-seer - self check\n")
    people = hr.sample_workforce("sorter", 30, "Alger")
    records = attendance_mod.sample_attendance(people, days=14)
    df = score_workforce(people, records)
    s = summary(df)

    print(f"  avg risk {s['avg_risk']:.1f}%  |  high {s['high']}  medium {s['medium']}")
    print(f"  expected leavers (6mo): {s['expected_leavers']}")
    print(f"  attrition cost at risk : {s['cost_at_risk']:,.0f} DZD\n")
    print(df.head(6).to_string(index=False))
    print("\n  Retention actions:")
    for a in retention_actions(df):
        print(f"   - {a}")
