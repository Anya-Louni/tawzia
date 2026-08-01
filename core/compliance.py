"""
core/compliance.py
------------------
The labour-law guardian - Algeria's version of the "Xiao Fa" risk scanner.

It reads the roster and the workforce and raises ranked alerts before an
inspector does: overtime over the statutory cap, missed weekly rest, pay below
the SNMG, fixed-term (CDD) contracts running too long, negative leave balances,
and thin coverage. Each alert names the rule and what to do, so the finding is
actionable rather than just a red light.

Every threshold is the real statutory one (see core/labour_dz.py and
core/sources.py). This is the feature that turns "nice to have" into "we cannot
be inspected without it" - compliance is not optional, and a fine is a hard
number an operator understands.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import hr, labour_dz

# A CDD (fixed-term contract) is meant to be temporary; well past two years it
# is a strong reclassification-to-permanent risk under Algerian practice.
CDD_MAX_MONTHS = 24
MIN_COVERAGE_RATIO = 0.98   # rostered capacity should meet at least this of need

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Alert:
    severity: str          # critical | warning | info
    category: str
    message: str
    rule: str
    action: str

    def as_dict(self) -> dict:
        return {
            "Severity": self.severity.upper(),
            "Area": self.category,
            "Finding": self.message,
            "Rule": self.rule,
            "What to do": self.action,
        }


def _weekly_overtime_alerts(roster: pd.DataFrame, cap: float) -> list:
    alerts = []
    if not {"date", "regular", "overtime"}.issubset(roster.columns):
        return alerts
    df = roster.copy()
    df["date"] = pd.to_datetime(df["date"])
    iso = df["date"].dt.isocalendar()
    df["week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str)
    wk = df.groupby("week")[["regular", "overtime"]].sum()
    for week, r in wk.iterrows():
        if r["regular"] <= 0:
            continue
        ratio = r["overtime"] / r["regular"]
        if ratio > cap + 1e-9:
            alerts.append(Alert(
                "critical", "Overtime",
                f"Week {week}: overtime is {ratio:.0%} of regular hours, over the "
                f"{cap:.0%} statutory cap.",
                "Loi 90-11 - overtime capped at 20% of legal working time.",
                "Add regular or temp headcount that week, or move demand-heavy "
                "tasks; do not schedule the excess overtime.",
            ))
    return alerts


def _coverage_alerts(roster: pd.DataFrame) -> list:
    alerts = []
    if not {"required_workers", "total_staff", "date", "shift"}.issubset(roster.columns):
        return alerts
    short = roster[roster["total_staff"] < roster["required_workers"] * MIN_COVERAGE_RATIO]
    if not short.empty:
        worst = short.assign(gap=short["required_workers"] - short["total_staff"]).nlargest(1, "gap").iloc[0]
        alerts.append(Alert(
            "warning", "Coverage",
            f"{len(short)} shift(s) rostered below forecast need - worst is "
            f"{worst['shift']} on {pd.to_datetime(worst['date']):%d %b} "
            f"({int(worst['total_staff'])} vs {int(worst['required_workers'])}).",
            "Service-level policy - understaffing risks missed service (in COD "
            "e-commerce, a delivery paid for twice).",
            "Raise the temp ceiling or the service level for those shifts.",
        ))
    return alerts


def _workforce_alerts(people: list, as_of: _dt.date) -> list:
    alerts = []
    # CDD running too long
    long_cdd = []
    for e in people:
        if e.contract == "CDD" and e.months_of_service(as_of) > CDD_MAX_MONTHS:
            long_cdd.append(e.name)
    if long_cdd:
        alerts.append(Alert(
            "critical", "Contracts",
            f"{len(long_cdd)} fixed-term (CDD) contract(s) over {CDD_MAX_MONTHS} "
            f"months (e.g. {long_cdd[0]}).",
            "Algerian labour practice - a long-running CDD risks reclassification "
            "as a permanent (CDI) contract.",
            "Review for conversion to CDI or a documented, lawful renewal.",
        ))

    # Negative / over-drawn leave balances
    overdrawn = [e.name for e in people if e.accrued_leave(as_of) < 0]
    if overdrawn:
        alerts.append(Alert(
            "warning", "Leave",
            f"{len(overdrawn)} employee(s) show a negative leave balance.",
            "Annual leave accrues at 2.5 days/month and cannot be over-drawn.",
            "Correct the ledger or record the excess as unpaid leave.",
        ))

    # Pay below SNMG
    below = [e.name for e in people if e.monthly_gross() < labour_dz.SNMG_MONTHLY - 1]
    if below:
        alerts.append(Alert(
            "critical", "Minimum wage",
            f"{len(below)} employee(s) below the SNMG of "
            f"{labour_dz.SNMG_MONTHLY:,.0f} DZD.",
            "SNMG is a legal floor for full-time monthly pay.",
            "Raise base pay to at least the SNMG immediately.",
        ))
    return alerts


def scan(
    roster: Optional[pd.DataFrame] = None,
    people: Optional[list] = None,
    constraints=None,
    as_of: Optional[_dt.date] = None,
) -> list:
    """Run every check and return alerts, most severe first."""
    as_of = as_of or _dt.date.today()
    cap = getattr(constraints, "max_overtime_fraction", labour_dz.MAX_OVERTIME_FRACTION)

    alerts = []
    if roster is not None and not roster.empty:
        alerts += _weekly_overtime_alerts(roster, cap)
        alerts += _coverage_alerts(roster)
    if people:
        alerts += _workforce_alerts(people, as_of)

    alerts.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 9))
    return alerts


def scorecard(alerts: list) -> dict:
    crit = sum(1 for a in alerts if a.severity == "critical")
    warn = sum(1 for a in alerts if a.severity == "warning")
    if crit:
        status, label = "critical", "Action required"
    elif warn:
        status, label = "warning", "Review recommended"
    else:
        status, label = "ok", "Compliant"
    return {"status": status, "label": label, "critical": crit,
            "warning": warn, "total": len(alerts)}


def to_frame(alerts: list) -> pd.DataFrame:
    if not alerts:
        return pd.DataFrame(columns=["Severity", "Area", "Finding", "Rule", "What to do"])
    return pd.DataFrame([a.as_dict() for a in alerts])


if __name__ == "__main__":
    print("Compliance guardian - self check\n")
    people = hr.sample_workforce("sorter", 30, "Alger")
    # Force a couple of violations for the demo
    today = _dt.date.today()
    people[0].contract = "CDD"; people[0].hire_date = today - _dt.timedelta(days=800)
    people[1].leave_taken_ytd = 999  # drive a negative balance

    roster = pd.DataFrame({
        "date": pd.date_range(today, periods=7).tolist() * 3,
        "shift": (["morning"] * 7 + ["afternoon"] * 7 + ["night"] * 7),
        "regular": [30] * 21, "overtime": [9] * 21,   # 30% > 20% cap
        "temp": [2] * 21, "total_staff": [41] * 21, "required_workers": [40] * 21,
    })

    alerts = scan(roster=roster, people=people)
    sc = scorecard(alerts)
    print(f"  status: {sc['label']} ({sc['critical']} critical, {sc['warning']} warning)\n")
    for a in alerts:
        print(f"  [{a.severity.upper():<8}] {a.category}: {a.message}")
