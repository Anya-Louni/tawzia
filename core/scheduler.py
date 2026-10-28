"""
core/scheduler.py
-----------------
L'agent de planning : le planning de la semaine par OR-Tools CP-SAT, avec le
droit du travail algérien en contraintes **dures** (le solveur ne peut pas les
violer) et le reste en objectifs (brief §6.2, §8.2).

Contraintes dures
=================
- un shift par jour au plus, au moins un jour de repos par semaine (art. 33) ;
- 48 h par semaine au plus : 40 h légales (ord. 97-03) + 20 % d'heures sup.
  (art. 31) ;
- pas de nuit (21 h à 5 h, art. 27) avant 19 ans (art. 28) ;
- pas de nuit pour une travailleuse sans dérogation du site (art. 29) ;
- pas de shift du matin au lendemain d'une nuit (repos minimal entre deux
  shifts : règle de bon sens opérationnel, pas un article) ;
- congés approuvés respectés.

Objectifs, pondérés dans la configuration
=========================================
couvrir la demande, limiter le coût des heures sup., **garder le planning de la
semaine précédente** (la stabilité paie : essai randomisé de Gap, +7 % de
ventes, +5 % de productivité), répartir équitablement nuits et vendredis, laisser
le vendredi libre quand c'est possible.

La demande vient de la prévision existante (Ramadan, Aïd, météo compris).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from ortools.sat.python import cp_model

from . import labour_dz, legal, rules, seed_company

_S = rules.payroll()["scheduler"]
_H = rules.payroll()["hours"]
DAYS_FR = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")


@dataclass
class Result:
    week_start: _dt.date
    site: str
    ramadan: bool
    status: str
    assign: dict            # (emp_id, day_index) -> shift code
    need: dict              # (day_index, shift) -> required
    shortfall: dict         # (day_index, shift) -> missing heads
    overtime_hours: float
    overtime_cost: float
    stability: float | None  # share of last week's assignments kept, 0..1
    blocked_nights: list    # (name, article) the solver could not use at night
    violations: list        # re-checked after solving, must be empty
    people: list


def shifts(ramadan: bool) -> list:
    return [(c, s, float(h)) for c, s, h in (_S["ramadan_shifts"] if ramadan else _S["shifts"])]


def demand(site_headcount: int, day_load: list, ramadan: bool) -> dict:
    """Effectif requis par jour et par shift. `day_load` : 7 multiplicateurs
    (1 = jour moyen), tirés de la prévision."""
    sh = shifts(ramadan)
    base = site_headcount * _S["share_working"]
    return {(d, c): max(1, round(base * day_load[d] * _S["shift_split"][i]))
            for d in range(7) for i, (c, _, _) in enumerate(sh)}


def load_from_forecast(fc, week_start: _dt.date) -> list:
    """Les 7 multiplicateurs de charge à partir d'une prévision (date, forecast)."""
    if fc is None or getattr(fc, "empty", True):
        return [1.0] * 7
    import pandas as pd
    f = fc.copy()
    f["date"] = pd.to_datetime(f["date"]).dt.date
    daily = f.groupby("date")["forecast"].sum()
    mean = daily.mean() or 1.0
    return [float(daily.get(week_start + _dt.timedelta(days=d), mean) / mean) for d in range(7)]


def solve(site: str, week_start: _dt.date, day_load: list | None = None, *,
          ramadan: bool = False, women_derogation: bool | None = None,
          last_week: dict | None = None, leaves: dict | None = None,
          people: list | None = None) -> Result:
    """Résoudre une semaine pour un site."""
    people = [e for e in (people or seed_company.people()) if e.site == site]
    derog = (seed_company.SITES[site]["women_night_derogation"]
             if women_derogation is None else women_derogation)
    sh = shifts(ramadan)
    codes = [c for c, _, _ in sh]
    hours = {c: h for c, _, h in sh}
    need = demand(len(people), day_load or [1.0] * 7, ramadan)
    leaves = leaves or {}
    night = {c for c, start, h in sh
             if legal.is_night(_dt.time(*map(int, start.split(":"))),
                               (_dt.datetime.combine(week_start, _dt.time(*map(int, start.split(":"))))
                                + _dt.timedelta(hours=h)).time())}
    fri = next(d for d in range(7) if (week_start + _dt.timedelta(days=d)).weekday() == 4)

    m = cp_model.CpModel()
    x = {(e.emp_id, d, c): m.new_bool_var(f"x_{e.emp_id}_{d}_{c}")
         for e in people for d in range(7) for c in codes}
    blocked = []
    week_cap = _H["legal_week"] * (1 + _H["overtime_cap_fraction"])
    obj = []
    w = _S["weights"]
    nights_per = []
    fridays_per = []
    for e in people:
        age = seed_company.age(e, week_start)
        for d in range(7):
            m.add_at_most_one(x[e.emp_id, d, c] for c in codes)
            if d in leaves.get(e.emp_id, ()):
                for c in codes:
                    m.add(x[e.emp_id, d, c] == 0)
        # Repos hebdomadaire : au moins un jour sans shift (art. 33).
        m.add(sum(x[e.emp_id, d, c] for d in range(7) for c in codes) <= 6)
        # 48 h au plus (40 h + 20 %). Heures en dixièmes pour rester entier.
        tenths = sum(int(hours[c] * 10) * x[e.emp_id, d, c] for d in range(7) for c in codes)
        m.add(tenths <= int(week_cap * 10))
        ot = m.new_int_var(0, int(week_cap * 10), f"ot_{e.emp_id}")
        m.add(ot >= tenths - int(_H["legal_week"] * 10))
        hourly = labour_dz.ROLES[e.role_key].gross_monthly / _H["legal_month"]
        obj.append(int(round(hourly * (1 + _S["overtime_premium"]) * w["overtime_per_hour"] / 10)) * ot)
        # Nuit : interdite avant 19 ans (art. 28), et pour les femmes sans
        # dérogation du site (art. 29).
        why = ("art. 28" if age is not None and age < rules.payroll()["work_time"]["night_min_age"]
               else "art. 29" if e.gender == "F" and not derog else None)
        if why:
            blocked.append((e.name, why))
            for d in range(7):
                for c in night:
                    m.add(x[e.emp_id, d, c] == 0)
        # Pas de matin le lendemain d'une nuit.
        for d in range(6):
            for c in night:
                m.add(x[e.emp_id, d, c] + x[e.emp_id, d + 1, codes[0]] <= 1)
        nights_per.append(sum(x[e.emp_id, d, c] for d in range(7) for c in night))
        fridays_per.append(sum(x[e.emp_id, fri, c] for c in codes))
        obj.append(w["friday_work"] * fridays_per[-1])
        if last_week:
            for d in range(7):
                prev = last_week.get((e.emp_id, d))
                for c in codes:
                    # Coût quand on s'écarte de la semaine passée, dans un sens ou l'autre.
                    obj.append(w["stability"] * (x[e.emp_id, d, c] if prev != c
                                                 else 1 - x[e.emp_id, d, c]))

    short = {}
    for (d, c), req in need.items():
        s = m.new_int_var(0, req, f"short_{d}_{c}")
        m.add(sum(x[e.emp_id, d, c] for e in people) + s >= req)
        short[d, c] = s
        obj.append(w["shortfall"] * s)

    # Équité : l'écart entre le plus et le moins de nuits, et de vendredis.
    for series in (nights_per, fridays_per):
        hi = m.new_int_var(0, 7, "hi")
        lo = m.new_int_var(0, 7, "lo")
        m.add_max_equality(hi, series)
        m.add_min_equality(lo, series)
        obj.append(w["fairness"] * (hi - lo))

    m.minimize(sum(obj))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(_S["solve_seconds"])
    solver.parameters.num_workers = 8
    st = solver.solve(m)
    status = solver.status_name(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Result(week_start, site, ramadan, status, {}, need, {}, 0, 0, None, blocked, [], people)

    assign = {(e.emp_id, d): c for e in people for d in range(7) for c in codes
              if solver.value(x[e.emp_id, d, c])}
    ot_h, ot_cost = 0.0, 0.0
    for e in people:
        h = sum(hours[assign[e.emp_id, d]] for d in range(7) if (e.emp_id, d) in assign)
        extra = max(h - _H["legal_week"], 0.0)
        ot_h += extra
        ot_cost += extra * labour_dz.ROLES[e.role_key].gross_monthly / _H["legal_month"] * (1 + _S["overtime_premium"])
    stability = None
    if last_week:
        keys = {(e.emp_id, d) for e in people for d in range(7)}
        stability = sum(1 for k in keys if assign.get(k) == last_week.get(k)) / len(keys)

    # Contre-vérification indépendante : chaque shift repassé dans core/legal.
    violations = []
    for (eid, d), c in assign.items():
        e = next(p for p in people if p.emp_id == eid)
        start = next(s for cc, s, _ in sh if cc == c)
        t0 = _dt.time(*map(int, start.split(":")))
        t1 = (_dt.datetime.combine(week_start, t0) + _dt.timedelta(hours=hours[c])).time()
        r = legal.check_shift(t0, t1, worker_age=seed_company.age(e, week_start) or 30,
                              worker_gender=e.gender or "M", site_women_night_derogation=derog)
        violations += [(e.name, d, v["article"]) for v in r["violations"]]
    return Result(week_start, site, ramadan, status, assign, need,
                  {k: solver.value(v) for k, v in short.items()}, ot_h, round(ot_cost),
                  stability, blocked, violations, people)


def grid(res: Result) -> list:
    """Une ligne par salarié, une colonne par jour : M, A, N ou repos."""
    rows = []
    for e in res.people:
        row = {"Salarié": e.name, "Poste": labour_dz.ROLES[e.role_key].label}
        for d in range(7):
            day = res.week_start + _dt.timedelta(days=d)
            row[f"{DAYS_FR[day.weekday()]} {day.day}"] = res.assign.get((e.emp_id, d), "·")
        rows.append(row)
    return rows


def next_week_start(today: _dt.date | None = None) -> _dt.date:
    """Le prochain samedi : la semaine de travail algérienne commence le samedi
    pour les équipes postées qui tournent sept jours sur sept."""
    today = today or _dt.date.today()
    return today + _dt.timedelta(days=(5 - today.weekday()) % 7 or 7)


if __name__ == "__main__":
    ws = _dt.date(2026, 10, 31)
    base = solve("OGX", ws - _dt.timedelta(days=7))
    assert base.status in ("OPTIMAL", "FEASIBLE"), base.status
    r = solve("OGX", ws, last_week={(eid, d): c for (eid, d), c in base.assign.items()})
    assert not r.violations, r.violations
    assert any(a == "art. 29" for _, a in r.blocked_nights), "OGX n'a pas de dérogation"
    women = {e.emp_id for e in r.people if e.gender == "F"}
    assert not [k for k, c in r.assign.items() if k[0] in women and c == "N"]
    for e in r.people:
        n = sum(1 for d in range(7) if (e.emp_id, d) in r.assign)
        assert n <= 6, "jour de repos manquant"
    ram = solve("OGX", ws, ramadan=True)
    assert ram.status in ("OPTIMAL", "FEASIBLE") and not ram.violations
    print(f"  OGX : {r.status}, stabilité {r.stability:.0%}, manque "
          f"{sum(r.shortfall.values())}, heures sup. {r.overtime_hours:.0f} h, "
          f"{len(r.blocked_nights)} nuits bloquées par la loi : ok")
