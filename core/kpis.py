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
    group: str         # "Effectif" | "Coût" | "Présence" | "Risque"


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

    # --- Effectif ----------------------------------------------------------
    cdd = sum(1 for e in people if e.contract == "CDD")
    cdd_pct = cdd / n * 100
    seniority = [e.seniority_years(as_of) for e in people]
    avg_sen = float(np.mean(seniority))
    first_year = sum(1 for e in people if e.months_of_service(as_of) < 12)
    first_year_pct = first_year / n * 100

    kpis.append(KPI("headcount", "Effectif", n, f"{n}", "employés",
                    "Nombre d'employés dans le périmètre.", "neutre", "Effectif"))
    kpis.append(KPI("cdd_pct", "Part de CDD", cdd_pct, f"{cdd_pct:.0f}%", "%",
                    "Part de contrats à durée déterminée : au-delà de 25% la "
                    "précarité pèse sur la fidélisation.",
                    _band(cdd_pct, good_below=15, warn_below=25), "Effectif"))
    kpis.append(KPI("avg_seniority", "Ancienneté moyenne", avg_sen,
                    f"{avg_sen:.1f}", "ans",
                    "Ancienneté moyenne de l'équipe.",
                    _band(avg_sen, good_above=3, warn_above=1.5), "Effectif"))
    kpis.append(KPI("first_year_pct", "Effectif < 1 an", first_year_pct,
                    f"{first_year_pct:.0f}%", "%",
                    "Part d'employés en première année : là où le turnover est "
                    "le plus fort.",
                    _band(first_year_pct, good_below=20, warn_below=35), "Effectif"))

    # --- Coût (paie sur la vraie pile SNMG + CNAS + IRG) -------------------
    slips = [payroll_dz.payslip(e.monthly_gross(), e.role_key, e.dependants, e.spouse)
             for e in people]
    gross = sum(s.gross for s in slips)
    employer_cost = sum(s.employer_cost for s in slips)
    cnas_total = sum(s.cnas_employee + s.cnas_employer for s in slips)
    irg_total = sum(s.irg for s in slips)
    net_total = sum(s.net for s in slips)
    load_pct = (employer_cost / gross - 1) * 100 if gross else 0

    kpis.append(KPI("wage_bill", "Masse salariale (brut)", gross,
                    _dzd(gross), "DZD/mois",
                    "Total des salaires bruts mensuels.", "neutre", "Coût"))
    kpis.append(KPI("employer_cost", "Coût employeur total", employer_cost,
                    _dzd(employer_cost), "DZD/mois",
                    "Brut + charges patronales CNAS (26%). Le vrai coût mensuel.",
                    "neutre", "Coût"))
    kpis.append(KPI("charges_load", "Charges patronales", load_pct,
                    f"+{load_pct:.0f}%", "%",
                    "Surcoût des charges patronales au-dessus du brut.",
                    "neutre", "Coût"))
    kpis.append(KPI("cnas_due", "CNAS à verser (35%)", cnas_total,
                    _dzd(cnas_total), "DZD/mois",
                    "Cotisations CNAS salarié 9% + employeur 26%.",
                    "neutre", "Coût"))
    kpis.append(KPI("irg_due", "IRG retenu (G50)", irg_total,
                    _dzd(irg_total), "DZD/mois",
                    "Impôt sur le revenu retenu à la source à reverser.",
                    "neutre", "Coût"))

    # --- Présence ----------------------------------------------------------
    summ = att_mod.lateness_summary(records)
    if not summ.empty:
        absent = float(summ["Absent %"].mean())
        late = float(summ["Late %"].mean())
        # absenteeism cost: absent shifts priced at the loaded daily cost + temp backfill
        role_keys = {e.emp_id: e.role_key for e in people}
        abs_cost = _absence_cost(records, role_keys)
    else:
        absent = late = abs_cost = 0.0

    kpis.append(KPI("absenteeism", "Taux d'absentéisme", absent,
                    f"{absent:.1f}%", "%",
                    "Part des shifts en absence. Au-delà de 8% le service et le "
                    "coût de remplacement décrochent.",
                    _band(absent, good_below=5, warn_below=8), "Présence"))
    kpis.append(KPI("lateness", "Taux de retard", late,
                    f"{late:.1f}%", "%",
                    "Part des shifts commencés en retard.",
                    _band(late, good_below=10, warn_below=20), "Présence"))
    kpis.append(KPI("absence_cost", "Coût mensuel de l'absentéisme", abs_cost,
                    _dzd(abs_cost), "DZD/mois",
                    "Shifts absents valorisés au coût chargé, remplacement "
                    "intérim inclus.", "neutre", "Présence"))

    # --- Risque (attrition + passif congés) --------------------------------
    risk_df = attr_mod.score_workforce(people, records, as_of)
    risk = attr_mod.summary(risk_df)
    leave_liab = _leave_liability(people, as_of)

    kpis.append(KPI("attrition_risk", "Risque de départ moyen", risk["avg_risk"],
                    f"{risk['avg_risk']:.0f}%", "%",
                    "Probabilité moyenne de départ à 6 mois (modèle attrition).",
                    _band(risk["avg_risk"], good_below=15, warn_below=25), "Risque"))
    kpis.append(KPI("high_risk", "Employés à haut risque", risk["high"],
                    f"{risk['high']}", "employés",
                    "Employés en bande de risque élevé, à traiter en priorité.",
                    _band(risk["high"], good_below=max(1, n * 0.05),
                          warn_below=max(2, n * 0.12)), "Risque"))
    kpis.append(KPI("cost_at_risk", "Coût de rotation à risque", risk["cost_at_risk"],
                    _dzd(risk["cost_at_risk"]), "DZD",
                    "Coût de remplacement pondéré par le risque de départ.",
                    "neutre", "Risque"))
    kpis.append(KPI("leave_liability", "Passif congés (solde acquis)", leave_liab,
                    _dzd(leave_liab), "DZD",
                    "Valeur des congés acquis non pris — un engagement au bilan.",
                    "neutre", "Risque"))

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
        "Groupe": k.group, "Indicateur": k.label, "Valeur": k.display,
        "État": k.band,
    } for k in kpis])


if __name__ == "__main__":
    from . import hr

    print("Tableau de KPI — self check\n")
    people = hr.sample_workforce("sorter", 60, "Alger")
    records = att_mod.sample_attendance(people, days=20)
    res = compute(people, records)
    for g in ["Effectif", "Coût", "Présence", "Risque"]:
        print(f"— {g} —")
        for k in res["kpis"]:
            if k.group == g:
                tag = {"bon": "OK", "surveiller": "!", "critique": "X"}.get(k.band, "-")
                print(f"  [{tag}] {k.label:<32} {k.display}")
        print()
