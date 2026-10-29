"""
core/legal.py
-------------
The Algerian labour-law checks the agents and the MCP server call: overtime,
shift legality, CDD validity.

Every threshold comes from config/dz_payroll_<year>.toml; every result cites the
article applied. The code decides nothing: it says what the rule allows.
"""

from __future__ import annotations

import datetime as _dt

from . import rules

_WT = rules.payroll()["work_time"]
_HOURS = rules.payroll()["hours"]


def _t(s: str) -> _dt.time:
    h, m = s.split(":")
    return _dt.time(int(h), int(m))


def check_overtime(hours_per_day: list, hourly_wage: float,
                   contract_hours: float | None = None) -> dict:
    """
    One working week: excess hours, the 20% cap, the premium due.

    `hours_per_day`: 7 values, Saturday to Friday or any order.
    """
    if len(hours_per_day) != 7 or any(h < 0 or h > 24 for h in hours_per_day):
        raise ValueError("hours_per_day needs 7 values between 0 and 24.")
    legal = contract_hours or _HOURS["legal_week"]
    total = float(sum(hours_per_day))
    overtime = max(total - legal, 0.0)
    cap = _HOURS["legal_week"] * _HOURS["overtime_cap_fraction"]
    long_days = [i for i, h in enumerate(hours_per_day) if h > _WT["max_hours_per_day"]]
    worked_days = sum(1 for h in hours_per_day if h > 0)
    violations = []
    if overtime > cap:
        violations.append({"rule": "overtime_cap", "article": "Law 90-11, art. 31",
                           "detail": f"{overtime:.1f} h overtime against a {cap:.0f} h cap "
                                     f"(20% of legal hours)."})
    if long_days:
        violations.append({"rule": "max_day", "article": "Maximum daily hours [verify]",
                           "detail": f"Day(s) {', '.join(str(d + 1) for d in long_days)} above "
                                     f"{_WT['max_hours_per_day']} h."})
    if worked_days == 7:
        violations.append({"rule": "weekly_rest", "article": "Law 90-11, art. 33",
                           "detail": "No rest day in the week."})
    return {
        "total_hours": total, "overtime_hours": overtime, "cap_hours": cap,
        "cap_used_pct": round(overtime / cap * 100, 1) if cap else 0.0,
        "legal": not violations, "violations": violations,
        "min_premium_rate": _HOURS["overtime_min_premium"],
        "min_premium_due": round(overtime * hourly_wage * _HOURS["overtime_min_premium"]),
        "sources": ["Law 90-11, art. 31 (cap)", "Law 90-11, art. 32 (premium of at least 50%)",
                    "Ordinance 97-03 (40 h)"],
    }


def is_night(start: _dt.time, end: _dt.time) -> bool:
    """Does the shift touch the night window (21:00 to 05:00 by default)?"""
    ns, ne = _t(_WT["night_start"]), _t(_WT["night_end"])
    mins = lambda t: t.hour * 60 + t.minute  # noqa: E731
    a, b = mins(start), mins(end)
    if b <= a:            # passe minuit
        b += 24 * 60
    night = [(mins(ns), mins(ne) + 24 * 60), (mins(ns) - 24 * 60, mins(ne))]
    return any(a < hi and b > lo for lo, hi in night)


def check_shift(start: _dt.time, end: _dt.time, *, worker_age: int,
                worker_gender: str, site_women_night_derogation: bool,
                on_weekly_rest_day: bool = False,
                compensatory_rest_planned: bool = False) -> dict:
    """The legality of a shift for one person, article by article."""
    if worker_gender not in ("F", "M"):
        raise ValueError("worker_gender must be 'F' or 'M'.")
    night = is_night(start, end)
    v = []
    if night and worker_age < _WT["night_min_age"]:
        v.append({"rule": "night_minor", "article": "Law 90-11, art. 28",
                  "detail": f"Night work is not allowed under {_WT['night_min_age']}."})
    if (night and worker_gender == "F" and _WT["women_night_needs_derogation"]
            and not site_women_night_derogation):
        v.append({"rule": "night_women", "article": "Law 90-11, art. 29",
                  "detail": "Night work for women needs a labour inspector's "
                            "waiver, which this site does not have. The waiver "
                            "opens equal access to night roles."})
    if on_weekly_rest_day and not compensatory_rest_planned:
        v.append({"rule": "rest_day", "article": "Law 90-11, art. 33 and 36",
                  "detail": "Shift on the weekly rest day without an equal "
                            "compensatory rest."})
    return {"night": night, "legal": not v, "violations": v,
            "night_window": f"{_WT['night_start']} to {_WT['night_end']} (art. 27)"}


CDD_CASES = {
    "remplacement": "Replacing an absent employee",
    "surcroit_temporaire": "Temporary increase in work",
    "saisonnier": "Seasonal activity",
    "travaux_temporaires": "Work or services that are temporary by nature",
}


def check_cdd(reason: str, start: _dt.date, end: _dt.date, renewals: int = 0) -> dict:
    """A CDD is only valid in the cases of art. 12."""
    if end <= start:
        raise ValueError("end must be after start.")
    ok = reason in rules.payroll()["cdd"]["allowed_cases"]
    months = (end - start).days / 30.44
    notes = []
    if ok and renewals >= 2:
        notes.append("Repeated renewals: a court may see a permanent job and "
                     "requalify it as a CDI.")
    return {
        "valid": ok, "case": CDD_CASES.get(reason, "Not a case listed in art. 12"),
        "duration_months": round(months, 1), "notes": notes,
        "explanation": ("A case listed in art. 12: the CDD is allowed; the duration and "
                        "reason must appear in the contract." if ok else
                        "Reason outside the cases of art. 12: the contract is deemed "
                        "open-ended."),
        "allowed_cases": CDD_CASES,
        "sources": ["Law 90-11, art. 12"],
    }


if __name__ == "__main__":
    t = _dt.time
    r = check_overtime([8, 8, 8, 8, 8, 8, 0], hourly_wage=200)
    assert r["overtime_hours"] == 8 and r["legal"] and r["min_premium_due"] == 800
    r = check_overtime([10, 10, 10, 10, 10, 0, 0], hourly_wage=200)
    assert not r["legal"] and r["violations"][0]["article"].endswith("31")
    assert is_night(t(22), t(6)) and is_night(t(4), t(12)) and not is_night(t(6), t(14))
    r = check_shift(t(22), t(6), worker_age=25, worker_gender="F",
                    site_women_night_derogation=False)
    assert not r["legal"] and r["violations"][0]["article"].endswith("29")
    assert check_shift(t(22), t(6), worker_age=25, worker_gender="F",
                       site_women_night_derogation=True)["legal"]
    assert not check_shift(t(22), t(6), worker_age=18, worker_gender="M",
                           site_women_night_derogation=True)["legal"]
    assert check_cdd("saisonnier", _dt.date(2026, 6, 1), _dt.date(2026, 9, 30))["valid"]
    assert not check_cdd("poste_permanent", _dt.date(2026, 1, 1), _dt.date(2026, 12, 31))["valid"]
    print("  legal checks: ok")
