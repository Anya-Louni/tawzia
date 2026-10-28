"""
core/filings.py
---------------
Les brouillons de déclaration que l'agent prépare et que le RH dépose lui-même :
G50 (IRG retenu à la source), cotisations CNAS par branche, DAS annuelle, et le
fichier de virement des salaires.

Rien ici ne dépose quoi que ce soit : chaque fonction rend des chiffres, une
date limite et le lien du portail officiel. Le dépôt se fait sur le portail,
par un humain. Les délais et taux viennent de config/dz_payroll_<année>.toml.
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
    """Une échéance tombant un vendredi, un samedi ou un jour férié fixe est
    reportée au jour ouvré suivant, si la configuration le prévoit [à vérifier]."""
    if not _F["roll_to_next_working_day"]:
        return d
    hol = _fixed_holidays(d.year)
    while d.weekday() in calendar_dz.WEEKEND_WEEKDAYS or d in hol:
        d += _dt.timedelta(days=1)
    return d


def working_days_until(today: _dt.date, due: _dt.date) -> int:
    """Jours ouvrés restants, aujourd'hui exclu, échéance incluse."""
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
    """La ligne IRG salaires de la G50 du mois, avec sa date limite."""
    slips = _slips(people)
    y, m = _month_after(year, month)
    due = next_working_day(_dt.date(y, m, _F["g50_day"]))
    irg = sum(b["irg"] for _, b in slips)
    return {
        "type": "g50_irg", "period": f"{month:02d}/{year}",
        "employees": len(slips),
        "taxable_total": round(sum(b["taxable"] for _, b in slips)),
        "irg_total": irg, "due": due, "portal": PORTAL_G50,
        "late_penalty": (f"{_F['g50_late_base']:.0%} puis {_F['g50_late_per_month']:.0%} "
                         f"par mois, plafonné à {_F['g50_late_cap']:.0%} [à vérifier]"),
        "lines": [{"emp_id": e.emp_id, "name": e.name, "taxable": round(b["taxable"]),
                   "irg": b["irg"]} for e, b in slips],
        "sources": ["DGI, déclaration série G n°50, Jibaya'tic", payroll_dz.CONFIG_VERSION],
        "status": "brouillon, à déposer par vos soins",
    }


def cnas_draft(people: list, year: int, month: int) -> dict:
    """Les cotisations du mois, réparties par branche, part salariale et patronale."""
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
        "sources": ["CNAS, barème par branche [à vérifier]", payroll_dz.CONFIG_VERSION],
        "status": "brouillon, à déposer par vos soins",
    }


def das_draft(people: list, year: int) -> dict:
    """La déclaration annuelle des salaires : un salarié, une ligne."""
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
            "note": "Estimation sur le salaire courant : la paie réelle de chaque "
                    "mois remplace cette ligne dès qu'elle est clôturée.",
            "sources": ["CNAS, DAS avant le 31 janvier", payroll_dz.CONFIG_VERSION],
            "status": "brouillon, à déposer par vos soins"}


def to_csv(rows: list) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), delimiter=";")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def bank_transfer_csv(people: list) -> str:
    """Le fichier de virement : nom, net. Le RIB vient du dossier sécurisé."""
    rows = [{"matricule": e.emp_id, "nom": e.name,
             "net_dzd": payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})["net"],
             "rib": "à compléter depuis le dossier"} for e in people]
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
    print(f"  G50 {g['irg_total']} DZD le {g['due']}, CNAS {c['total_due']} DZD "
          f"le {c['due']}, DAS le {d['due']}")
    print("  brouillons de déclaration : ok")
