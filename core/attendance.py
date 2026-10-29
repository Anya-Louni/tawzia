"""
core/attendance.py
------------------
Requests in, attendance watched.

Two everyday HR jobs that a shift operation lives and dies by:

  1. **Requests** - the worker's "demande de sortie" (permission to leave
     during the shift), leave requests, sick notices. They arrive, someone must
     decide, and the decision has to be legal AND affordable. This module turns
     each request into a decision using the leave-law brain in `core/hr.py` and
     the demand forecast, so approving in a peak week is flagged, not silently
     granted.

  2. **Attendance** - who clocked in, who was late, who never showed. Lateness
     is not just a discipline matter; chronic lateness and absence are the
     strongest early signal of a worker about to quit, so this data later feeds
     the attrition model.

Demo attendance and requests are synthetic and clearly generated; a real
deployment reads the badge/clock system and the request inbox.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import hr, labour_dz

# Grace before a clock-in counts as "late", and the point it becomes "absent".
LATE_GRACE_MIN = 5
ABSENT_AFTER_MIN = 120

REQUEST_TYPES = {
    "sortie": "Short absence",
    "annual": "Annual leave",
    "sick": "Sick leave",
    "unpaid": "Unpaid leave",
    "family": "Family event",
}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

@dataclass
class Request:
    req_id: str
    emp_id: str
    emp_name: str
    role_key: str
    kind: str                    # key in REQUEST_TYPES
    start: _dt.date
    end: _dt.date
    hours: Optional[float]       # set for a same-day "sortie"
    reason: str
    created: _dt.date
    status: str = "pending"      # pending | approved | rejected

    @property
    def kind_label(self) -> str:
        return REQUEST_TYPES.get(self.kind, self.kind)

    @property
    def is_sortie(self) -> bool:
        return self.kind == "sortie"


def decide_request(
    req: Request,
    employee: hr.Employee,
    as_of: Optional[_dt.date] = None,
    forecast: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Turn a request into a recommendation (the human still clicks approve).

    A short 'sortie' is light-touch (hours, not leave-balance). Multi-day leave
    goes through the full legal + operational check in core/hr.py.
    """
    as_of = as_of or _dt.date.today()

    if req.is_sortie:
        reasons = [f"Short absence of {req.hours or 0:.0f} h on {req.start:%d %b}."]
        warnings = []
        # A short absence during a peak shift still needs cover.
        load = None
        if forecast is not None and not forecast.empty and "forecast" in forecast.columns:
            fc = forecast.copy(); fc["date"] = pd.to_datetime(fc["date"])
            day = fc[fc["date"] == pd.Timestamp(req.start)]
            if not day.empty:
                daily = fc.groupby("date")["forecast"].sum()
                if day["forecast"].sum() >= daily.quantile(0.70):
                    load = "peak"
                    warnings.append("This shift is a forecast peak: arrange cover before approving.")
        return {
            "recommend": "approve" if not warnings else "approve_with_cover",
            "reasons": reasons, "warnings": warnings, "load": load,
            "balance_after": employee.accrued_leave(as_of),
        }

    if req.kind in ("annual", "unpaid", "family"):
        v = hr.can_take_leave(employee, req.start, req.end, as_of=as_of, forecast=forecast)
        return {
            "recommend": "approve" if v.allowed and not v.warnings else
                         ("reject" if not v.allowed else "approve_with_note"),
            "reasons": v.reasons, "warnings": v.warnings, "load": v.demand_load,
            "balance_after": v.balance_after, "days": v.days_requested,
        }

    if req.kind == "sick":
        # Sick leave is a right, not a discretionary grant; it is recorded, and
        # the pay rule (50% first 15 days, then 100%) is flagged.
        span = (req.end - req.start).days + 1
        note = (f"{span} day(s). Paid at 50% for the first {hr.SICK_SPLIT_DAY} days, "
                f"then 100% (covered by CNAS). Medical certificate required.")
        return {"recommend": "record", "reasons": [note], "warnings": [], "load": None,
                "balance_after": employee.accrued_leave(as_of)}

    return {"recommend": "review", "reasons": ["Revue manuelle."], "warnings": [], "load": None,
            "balance_after": employee.accrued_leave(as_of)}


def sample_requests(people: list, seed: int = 5, as_of: Optional[_dt.date] = None) -> list:
    """A synthetic inbox of pending requests for the demo."""
    as_of = as_of or _dt.date.today()
    rng = np.random.default_rng(seed)
    reasons = {
        "sortie": ["Rendez-vous administratif", "Rendez-vous medical", "Affaire personnelle"],
        "annual": ["Vacances famille", "Repos", "Voyage"],
        "sick": ["Grippe", "Certificat medical"],
        "unpaid": ["Affaire personnelle prolongee"],
        "family": ["Mariage", "Deces proche", "Naissance"],
    }
    out = []
    n = min(max(len(people) // 4, 4), 10)
    for i in range(n):
        emp = people[int(rng.integers(0, len(people)))]
        kind = rng.choice(list(REQUEST_TYPES), p=[0.34, 0.30, 0.16, 0.08, 0.12])
        start = as_of + _dt.timedelta(days=int(rng.integers(1, 40)))
        if kind == "sortie":
            end = start; hours = float(rng.choice([1, 2, 3, 4]))
        elif kind == "sick":
            end = start + _dt.timedelta(days=int(rng.integers(1, 6))); hours = None
        else:
            end = start + _dt.timedelta(days=int(rng.integers(2, 12))); hours = None
        out.append(Request(
            req_id=f"R{200 + i}", emp_id=emp.emp_id, emp_name=emp.name,
            role_key=emp.role_key, kind=kind, start=start, end=end, hours=hours,
            reason=str(rng.choice(reasons[kind])), created=as_of - _dt.timedelta(days=int(rng.integers(0, 5))),
        ))
    return out


# ---------------------------------------------------------------------------
# Attendance / lateness
# ---------------------------------------------------------------------------

@dataclass
class ClockRecord:
    emp_id: str
    emp_name: str
    date: _dt.date
    scheduled: _dt.time
    actual: Optional[_dt.time]   # None = no-show
    shift: str

    @property
    def minutes_late(self) -> Optional[int]:
        if self.actual is None:
            return None
        sched = _dt.datetime.combine(self.date, self.scheduled)
        act = _dt.datetime.combine(self.date, self.actual)
        return int((act - sched).total_seconds() // 60)

    @property
    def flag(self) -> str:
        if self.actual is None:
            return "absent"
        m = self.minutes_late
        if m is None or m <= LATE_GRACE_MIN:
            return "on_time"
        if m >= ABSENT_AFTER_MIN:
            return "absent"
        return "late"


def sample_attendance(people: list, days: int = 14, seed: int = 8,
                      as_of: Optional[_dt.date] = None) -> list:
    """Synthetic clock-in log. Some workers are habitually late (attrition risk)."""
    as_of = as_of or _dt.date.today()
    rng = np.random.default_rng(seed)
    # give each worker a personal punctuality tendency
    tendency = {e.emp_id: rng.beta(1.4, 6.0) for e in people}   # mostly low, a few high
    sched_time = _dt.time(6, 0)
    records = []
    for d_off in range(days):
        day = as_of - _dt.timedelta(days=days - d_off)
        if day.weekday() in (4, 5):   # Friday-Saturday weekend
            continue
        for e in people:
            t = tendency[e.emp_id]
            r = rng.random()
            if r < 0.02 + t * 0.25:
                actual = None                       # no-show
            else:
                late = max(0, int(rng.normal(t * 40 - 6, 10)))
                actual = (_dt.datetime.combine(day, sched_time) +
                          _dt.timedelta(minutes=late)).time()
            records.append(ClockRecord(
                emp_id=e.emp_id, emp_name=e.name, date=day,
                scheduled=sched_time, actual=actual, shift="morning",
            ))
    return records


def lateness_summary(records: list) -> pd.DataFrame:
    """Per-employee attendance scorecard - the raw material for attrition risk."""
    if not records:
        return pd.DataFrame(columns=["ID", "Name", "Shifts", "Late", "Absent",
                                     "Late minutes", "Late %", "Absent %"])
    rows = {}
    for r in records:
        s = rows.setdefault(r.emp_id, {"Name": r.emp_name, "Shifts": 0, "Late": 0,
                                       "Absent": 0, "Late minutes": 0})
        s["Shifts"] += 1
        f = r.flag
        if f == "late":
            s["Late"] += 1; s["Late minutes"] += (r.minutes_late or 0)
        elif f == "absent":
            s["Absent"] += 1
    out = []
    for emp_id, s in rows.items():
        shifts = max(s["Shifts"], 1)
        out.append({
            "ID": emp_id, **s,
            "Late %": round(s["Late"] / shifts * 100, 1),
            "Absent %": round(s["Absent"] / shifts * 100, 1),
        })
    df = pd.DataFrame(out)
    return df.sort_values(["Absent %", "Late %"], ascending=False).reset_index(drop=True)


def todays_flags(records: list, on: Optional[_dt.date] = None) -> pd.DataFrame:
    """Late/absent flags for one day, for the live 'who is late right now' board."""
    _FLAG_FR = {"late": "Late", "absent": "Absent"}
    if not records:
        return pd.DataFrame(columns=["ID", "Name", "Scheduled", "Actual", "Late (min)", "Status"])
    on = on or max(r.date for r in records)
    rows = []
    for r in records:
        if r.date != on or r.flag == "on_time":
            continue
        rows.append({
            "ID": r.emp_id, "Name": r.emp_name,
            "Scheduled": r.scheduled.strftime("%H:%M"),
            "Actual": r.actual.strftime("%H:%M") if r.actual else "absent",
            "Late (min)": r.minutes_late if r.minutes_late is not None else "",
            "Status": _FLAG_FR.get(r.flag, r.flag),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Attendance & requests - self check\n")
    people = hr.sample_workforce("sorter", 24, "Alger")

    reqs = sample_requests(people)
    print(f"  {len(reqs)} pending requests")
    lookup = {e.emp_id: e for e in people}
    for r in reqs[:5]:
        d = decide_request(r, lookup[r.emp_id])
        print(f"    {r.req_id} {r.kind_label[:34]:<34} -> {d['recommend']}")

    att = sample_attendance(people, days=14)
    print(f"\n  {len(att)} clock records over 14 days")
    summ = lateness_summary(att)
    worst = summ.head(3)
    print("  worst attendance (attrition watch):")
    for _, w in worst.iterrows():
        print(f"    {w['Name']:<22} late {w['Late %']:>5}%  absent {w['Absent %']:>5}%")
    print(f"\n  today late/absent flags: {len(todays_flags(att))}")
