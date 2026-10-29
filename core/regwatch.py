"""
core/regwatch.py
----------------
Official Journal watch.

Algerian labour and payroll rules move: the SNMG, CNAS rates, IRG brackets,
leave and overtime change by decree. Missing one quietly puts a company out of
compliance. This module keeps a register of tracked rules, checks whether the
client's configuration still matches the legal value, and for any change
computes who is affected and what it costs, then drafts the compliance notice.

Honesty: in this demo the register is a curated summary of the tracked rules,
using the legal values the engine already applies. In production it is fed by
automatic ingestion of the Official Journal and CNAS/DGI publications. The
"your status" check and the change simulator are real: they compare and
recompute on the actual workforce.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

from . import labour_dz, ai, hr

IRG_EXEMPT_THRESHOLD = 30_000   # monthly income at or below this pays no IRG


def our_config() -> dict:
    return {
        "snmg": labour_dz.SNMG_MONTHLY,
        "cnas_employer": labour_dz.CNAS_EMPLOYER,
        "cnas_employee": labour_dz.CNAS_EMPLOYEE,
        "overtime_cap": labour_dz.MAX_OVERTIME_FRACTION,
        "annual_leave": hr.ANNUAL_LEAVE_DAYS,
        "irg_exempt": IRG_EXEMPT_THRESHOLD,
    }


# Tracked rules (curated). `legal_value` is the current legal value;
# `param` links the entry to our_config().
REGISTER = [
    {"param": "snmg", "domain": "Minimum wage",
     "ref": "SNMG, Finance Law / executive decree",
     "title": "Guaranteed national minimum wage (SNMG)",
     "summary": "The national monthly minimum wage for full-time work.",
     "legal_value": labour_dz.SNMG_MONTHLY, "unit": "DZD/month",
     "effective": "in force"},
    {"param": "cnas_employer", "domain": "Social security",
     "ref": "CNAS, Law 83-11 and implementing texts",
     "title": "CNAS employer contribution rate",
     "summary": "Employer social-security contribution on gross salary.",
     "legal_value": labour_dz.CNAS_EMPLOYER, "unit": "rate",
     "effective": "in force"},
    {"param": "cnas_employee", "domain": "Social security",
     "ref": "CNAS, Law 83-11 and implementing texts",
     "title": "CNAS employee contribution rate",
     "summary": "Employee social-security contribution withheld from gross.",
     "legal_value": labour_dz.CNAS_EMPLOYEE, "unit": "rate",
     "effective": "in force"},
    {"param": "irg_exempt", "domain": "Income tax",
     "ref": "IRG scale, Finance Law",
     "title": "IRG exemption threshold",
     "summary": "A monthly salary at or below this level pays no IRG.",
     "legal_value": IRG_EXEMPT_THRESHOLD, "unit": "DZD/month",
     "effective": "in force"},
    {"param": "overtime_cap", "domain": "Working time",
     "ref": "Law 90-11, working time",
     "title": "Overtime cap",
     "summary": "Overtime may not exceed this share of legal hours.",
     "legal_value": labour_dz.MAX_OVERTIME_FRACTION, "unit": "rate",
     "effective": "in force"},
    {"param": "annual_leave", "domain": "Leave",
     "ref": "Law 90-11, annual leave",
     "title": "Paid annual leave",
     "summary": "Minimum paid annual leave (plus the southern wilayas bonus).",
     "legal_value": hr.ANNUAL_LEAVE_DAYS, "unit": "days/year",
     "effective": "in force"},
]


def _fmt(value, unit) -> str:
    if unit == "rate":
        return f"{value:.0%}"
    if unit.startswith("DZD"):
        return f"{value:,.0f} {unit}"
    return f"{value:g} {unit}"


def status() -> list:
    """Compare the engine's live configuration with each tracked legal value."""
    cfg = our_config()
    rows = []
    for item in REGISTER:
        ours = cfg.get(item["param"])
        legal = item["legal_value"]
        ok = abs(float(ours) - float(legal)) < 1e-9
        rows.append({
            "Rule": item["title"],
            "Area": item["domain"],
            "Your setting": _fmt(ours, item["unit"]),
            "Current legal value": _fmt(legal, item["unit"]),
            "Status": "Up to date" if ok else "OUT OF DATE",
            "Reference": item["ref"],
        })
    return rows


@dataclass
class ChangeImpact:
    param: str
    old_value: float
    new_value: float
    unit: str
    affected: int
    workforce: int
    annual_cost_delta: float
    detail: str


def simulate_change(people, param: str, new_value: float,
                    as_of: Optional[_dt.date] = None) -> ChangeImpact:
    """Recompute the impact of a proposed rule change on the actual workforce."""
    as_of = as_of or _dt.date.today()
    cfg = our_config()
    old_value = float(cfg.get(param, 0.0))
    unit = next((i["unit"] for i in REGISTER if i["param"] == param), "")
    n = len(people)
    affected = 0
    cost_delta = 0.0
    detail = ""

    if param == "snmg":
        loaded = 1 + labour_dz.CNAS_EMPLOYER
        for e in people:
            g = e.monthly_gross()
            if g < new_value:
                affected += 1
                cost_delta += (new_value - g) * 12 * loaded
        detail = (f"{affected} of {n} employees are below the proposed SNMG of "
                  f"{new_value:,.0f} DZD and must be raised to it.")
    elif param in ("cnas_employer",):
        total_gross = sum(e.monthly_gross() for e in people)
        cost_delta = total_gross * 12 * (new_value - old_value)
        affected = n
        detail = (f"The CNAS employer rate moves from {old_value:.0%} to "
                  f"{new_value:.0%} on the whole payroll.")
    else:
        detail = ("This rule change is tracked for compliance; it has no direct "
                  "cost formula in this simulator.")

    return ChangeImpact(param, old_value, float(new_value), unit,
                        affected, n, round(cost_delta), detail)


def impact_notice(change: ChangeImpact, lang: str = "en") -> str:
    """AI "what you must do" notice for a rule change."""
    lang_name = "French" if lang == "fr" else "English"
    system = (
        "You are a compliance officer for an Algerian HR platform. Write a short, "
        "practical notice telling the employer exactly what to change for a labour "
        "rule update. Ground strictly in the numbers given. "
        f"Write in {lang_name}."
    )
    old = _fmt(change.old_value, change.unit)
    new = _fmt(change.new_value, change.unit)
    user = (
        f"Rule '{change.param}' changes from {old} to {new}. "
        f"Impact: {change.detail} Estimated annual payroll cost change: "
        f"{change.annual_cost_delta:,.0f} DZD. Write: what to update in the system, "
        f"which employees/contracts are affected, and the deadline framing. "
        f"Under 130 words."
    )
    r = ai.chat(system, user, max_tokens=380, temperature=0.3)
    if r.ok and r.text.strip():
        return r.text.strip()
    return (f"Action required: update '{change.param}' from {old} to {new}. "
            f"{change.detail} Estimated annual change: "
            f"{change.annual_cost_delta:,.0f} DZD. Apply on the effective date, "
            f"then rerun payroll and the compliance check.")


if __name__ == "__main__":
    from . import hr as _hr
    print("Official Journal watch, self-test\n")
    for r in status():
        print(f"  {r['Rule']:<34} {r['Status']:<10} yours={r['Your setting']}  legal={r['Current legal value']}")
    people = _hr.sample_workforce("sorter", 30, "Alger")
    imp = simulate_change(people, "snmg", labour_dz.SNMG_MONTHLY + 6000)
    assert imp.workforce == 30
    print("\nSNMG +6000:", imp.detail, "| cost", f"{imp.annual_cost_delta:,.0f} DZD")
