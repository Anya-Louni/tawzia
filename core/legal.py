"""
core/legal.py
-------------
Les contrôles du droit du travail algérien que les agents et le serveur MCP
appellent : heures supplémentaires, légalité d'un shift, validité d'un CDD.

Chaque seuil vient de config/dz_payroll_<année>.toml ; chaque résultat cite
l'article appliqué. Le code ne décide rien : il dit ce que la règle permet.
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
    Une semaine de travail : dépassement, plafond de 20 %, majoration due.

    `hours_per_day` : 7 valeurs, du samedi au vendredi ou dans l'ordre voulu.
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
        violations.append({"rule": "overtime_cap", "article": "Loi 90-11, art. 31",
                           "detail": f"{overtime:.1f} h sup. pour un plafond de {cap:.0f} h "
                                     f"(20 % de la durée légale)."})
    if long_days:
        violations.append({"rule": "max_day", "article": "Durée journalière maximale [à vérifier]",
                           "detail": f"Jour(s) {', '.join(str(d + 1) for d in long_days)} au-delà "
                                     f"de {_WT['max_hours_per_day']} h."})
    if worked_days == 7:
        violations.append({"rule": "weekly_rest", "article": "Loi 90-11, art. 33",
                           "detail": "Aucun jour de repos dans la semaine."})
    return {
        "total_hours": total, "overtime_hours": overtime, "cap_hours": cap,
        "cap_used_pct": round(overtime / cap * 100, 1) if cap else 0.0,
        "legal": not violations, "violations": violations,
        "min_premium_rate": _HOURS["overtime_min_premium"],
        "min_premium_due": round(overtime * hourly_wage * _HOURS["overtime_min_premium"]),
        "sources": ["Loi 90-11, art. 31 (plafond)", "Loi 90-11, art. 32 (majoration ≥ 50 %)",
                    "Ordonnance 97-03 (40 h)"],
    }


def is_night(start: _dt.time, end: _dt.time) -> bool:
    """Le shift touche-t-il la plage de nuit (21 h à 5 h par défaut) ?"""
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
    """La légalité d'un shift pour une personne donnée, article par article."""
    if worker_gender not in ("F", "M"):
        raise ValueError("worker_gender must be 'F' or 'M'.")
    night = is_night(start, end)
    v = []
    if night and worker_age < _WT["night_min_age"]:
        v.append({"rule": "night_minor", "article": "Loi 90-11, art. 28",
                  "detail": f"Travail de nuit interdit avant {_WT['night_min_age']} ans."})
    if (night and worker_gender == "F" and _WT["women_night_needs_derogation"]
            and not site_women_night_derogation):
        v.append({"rule": "night_women", "article": "Loi 90-11, art. 29",
                  "detail": "Travail de nuit des femmes soumis à une dérogation de "
                            "l'inspecteur du travail, absente pour ce site. La "
                            "dérogation ouvre l'accès égal aux postes de nuit."})
    if on_weekly_rest_day and not compensatory_rest_planned:
        v.append({"rule": "rest_day", "article": "Loi 90-11, art. 33 et 36",
                  "detail": "Shift sur le repos hebdomadaire sans repos compensateur "
                            "d'une durée égale."})
    return {"night": night, "legal": not v, "violations": v,
            "night_window": f"{_WT['night_start']} à {_WT['night_end']} (art. 27)"}


CDD_CASES = {
    "remplacement": "Remplacement d'un titulaire absent",
    "surcroit_temporaire": "Surcroît temporaire de travail",
    "saisonnier": "Activité saisonnière",
    "travaux_temporaires": "Travaux ou services non renouvelables par nature",
}


def check_cdd(reason: str, start: _dt.date, end: _dt.date, renewals: int = 0) -> dict:
    """Un CDD n'est valable que dans les cas de l'art. 12."""
    if end <= start:
        raise ValueError("end must be after start.")
    ok = reason in rules.payroll()["cdd"]["allowed_cases"]
    months = (end - start).days / 30.44
    notes = []
    if ok and renewals >= 2:
        notes.append("Renouvellements répétés : le juge peut y voir un emploi permanent "
                     "et requalifier en CDI.")
    return {
        "valid": ok, "case": CDD_CASES.get(reason, "Cas non prévu par l'art. 12"),
        "duration_months": round(months, 1), "notes": notes,
        "explanation": ("Cas prévu par l'art. 12 : le CDD est possible, la durée et le "
                        "motif doivent figurer au contrat." if ok else
                        "Motif hors des cas de l'art. 12 : le contrat est réputé à "
                        "durée indéterminée."),
        "allowed_cases": CDD_CASES,
        "sources": ["Loi 90-11, art. 12"],
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
    print("  contrôles légaux : ok")
