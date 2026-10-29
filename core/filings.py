"""
core/filings.py
---------------
The filing drafts the agent prepares and HR files itself: G50 (IRG withheld
at source), CNAS contributions by branch, the annual DAS, and the salary bank
transfer file.

Nothing here files anything: each function returns figures, a deadline and the
official portal link. Filing happens on the portal, by a human. Delays and rates
come from config/dz_payroll_<year>.toml.
"""

from __future__ import annotations

import calendar
import csv
import datetime as _dt
import io

from . import calendar_dz, payroll_dz, rules

_F = rules.payroll()["filings"]
PORTAL_G50 = "https://jibayatic.dz"
PORTAL_CNAS = "https://teledeclaration.cnas.dz"


def _fixed_holidays(year: int) -> set:
    return {_dt.date(year, m, d) for (m, d) in calendar_dz.CIVIL_HOLIDAYS}


def next_working_day(d: _dt.date) -> _dt.date:
    """A deadline falling on a Friday, a Saturday or a fixed public holiday moves
    to the next working day, when the configuration says so [verify]."""
    if not _F["roll_to_next_working_day"]:
        return d
    hol = _fixed_holidays(d.year)
    while d.weekday() in calendar_dz.WEEKEND_WEEKDAYS or d in hol:
        d += _dt.timedelta(days=1)
    return d


def working_days_until(today: _dt.date, due: _dt.date) -> int:
    """Working days left, today excluded, deadline included."""
    n, d = 0, today
    hol = _fixed_holidays(today.year) | _fixed_holidays(due.year)
    while d < due:
        d += _dt.timedelta(days=1)
        if d.weekday() not in calendar_dz.WEEKEND_WEEKDAYS and d not in hol:
            n += 1
    return n


def _month_after(year: int, month: int) -> tuple:
    return (year + month // 12, month % 12 + 1)


def _slips(people: list) -> list:
    out = []
    for e in people:
        b = payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})
        out.append((e, b))
    return out


def g50_draft(people: list, year: int, month: int) -> dict:
    """The month's G50 salary IRG line, with its deadline."""
    slips = _slips(people)
    y, m = _month_after(year, month)
    due = next_working_day(_dt.date(y, m, _F["g50_day"]))
    irg = sum(b["irg"] for _, b in slips)
    return {
        "type": "g50_irg", "period": f"{month:02d}/{year}",
        "employees": len(slips),
        "taxable_total": round(sum(b["taxable"] for _, b in slips)),
        "irg_total": irg, "due": due, "portal": PORTAL_G50,
        "late_penalty": (f"{_F['g50_late_base']:.0%} then {_F['g50_late_per_month']:.0%} "
                         f"a month, capped at {_F['g50_late_cap']:.0%} [verify]"),
        "lines": [{"emp_id": e.emp_id, "name": e.name, "taxable": round(b["taxable"]),
                   "irg": b["irg"]} for e, b in slips],
        "sources": ["DGI, G series no. 50 return, Jibaya'tic", payroll_dz.CONFIG_VERSION],
        "status": "draft, for you to file",
    }


def cnas_draft(people: list, year: int, month: int) -> dict:
    """The month's contributions, split by branch, employee and employer shares."""
    slips = _slips(people)
    end = _dt.date(year, month, calendar.monthrange(year, month)[1])
    due = next_working_day(end + _dt.timedelta(days=_F["cnas_days_after_period"]))
    branches = {}
    for _, b in slips:
        for k, v in b["employer_by_branch"].items():
            branches.setdefault(k, [0, 0])[0] += v
        for k, v in b["employee_by_branch"].items():
            branches[k][1] += v
    employer = sum(v[0] for v in branches.values())
    employee = sum(b["cnas_employee"] for _, b in slips)
    return {
        "type": "cnas_monthly", "period": f"{month:02d}/{year}",
        "employees": len(slips),
        "base_total": round(sum(b["cnas_base"] for _, b in slips)),
        "employer_total": employer, "employee_total": employee,
        "total_due": employer + employee,
        "by_branch": {k: {"employer": v[0], "employee": v[1]} for k, v in branches.items()},
        "monthly": len(slips) >= _F["cnas_monthly_from_headcount"],
        "due": due, "portal": PORTAL_CNAS,
        "sources": ["CNAS, branch table [verify]", payroll_dz.CONFIG_VERSION],
        "status": "draft, for you to file",
    }


def das_draft(people: list, year: int) -> dict:
    """The annual salary declaration: one employee, one line."""
    slips = _slips(people)
    due = next_working_day(_dt.date(year + 1, _F["das_month"], _F["das_day"]))
    rows = []
    for e, b in slips:
        start = max(e.hire_date, _dt.date(year, 1, 1))
        months = max(0, 12 - (start.month - 1)) if start.year == year else (
            12 if start.year < year else 0)
        rows.append({"emp_id": e.emp_id, "name": e.name, "months": months,
                     "cnas_base_year": round(b["cnas_base"] * months),
                     "cnas_employee_year": round(b["cnas_employee"] * months)})
    return {"type": "das", "period": str(year), "employees": len(rows),
            "base_total": sum(r["cnas_base_year"] for r in rows), "due": due,
            "portal": PORTAL_CNAS, "lines": rows,
            "note": "Estimated from the current salary: each month's actual payroll "
                    "replaces this line once it is closed.",
            "sources": ["CNAS, DAS before 31 January", payroll_dz.CONFIG_VERSION],
            "status": "draft, for you to file"}


def to_csv(rows: list) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=";")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def bank_transfer_csv(people: list) -> str:
    """The bank transfer file: name, net. The RIB comes from the secure file."""
    rows = [{"staff_number": e.emp_id, "name": e.name,
             "net_dzd": payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})["net"],
             "rib": "fill in from the secure file"} for e in people]
    return to_csv(rows)


if __name__ == "__main__":
    from . import hr
    ppl = hr.sample_workforce("sorter", 20, "Alger")
    g = g50_draft(ppl, 2026, 10)
    assert g["due"].weekday() not in (4, 5) and g["due"] >= _dt.date(2026, 11, 20)
    c = cnas_draft(ppl, 2026, 10)
    assert c["total_due"] == c["employer_total"] + c["employee_total"]
    assert abs(c["employer_total"] - c["base_total"] * payroll_dz.CNAS_EMPLOYER) <= 20
    d = das_draft(ppl, 2026)
    assert d["due"].year == 2027 and len(d["lines"]) == 20
    assert next_working_day(_dt.date(2026, 11, 20)) == _dt.date(2026, 11, 22)  # ven. -> dim.
    assert working_days_until(_dt.date(2026, 11, 14), _dt.date(2026, 11, 22)) == 6
    print(f"  G50 {g['irg_total']} DZD on {g['due']}, CNAS {c['total_due']} DZD "
          f"on {c['due']}, DAS on {d['due']}")
    print("  filing drafts: ok")
