"""
core/seed_company.py
--------------------
La société de démonstration : **fictive**. Une entreprise d'assistance en escale
et de logistique, 140 salariés sur deux sites, l'un à Alger, l'autre dans une
wilaya du Sud (Ouargla), pour que les règles qui dépendent du site (congé du
Sud, dérogation au travail de nuit) se voient.

Aucun nom, logo ou chiffre d'une vraie entreprise. Les noms des salariés sont
des combinaisons de prénoms et de noms courants, sans lien avec une personne
réelle. Quelques écarts sont posés exprès (deux dépassements d'heures sup., une
saisie sous le SNMG, deux embauches de la semaine, trois salariés de moins de 19
ans) pour que les agents aient quelque chose de vrai à trouver : ce sont des
données de démonstration, et l'interface le dit.
"""

from __future__ import annotations

import datetime as _dt
import itertools
from functools import lru_cache

import numpy as np

from . import hr

COMPANY = {
    "name": "Démo Handling & Logistique",
    "legal_note": "Société fictive, données de démonstration",
    "sector": "Assistance en escale et logistique",
}

SITES = {
    "ALG": {"name": "Alger, hub aéroport et entrepôt", "wilaya": "Alger",
            "women_night_derogation": True},
    "OGX": {"name": "Ouargla, base sud", "wilaya": "Ouargla",
            "women_night_derogation": False},
}

# Effectif par site et par poste : 110 à Alger, 30 à Ouargla.
STAFFING = {
    "ALG": {"ramp_agent": 30, "checkin_agent": 20, "sorter": 18, "loader": 12,
            "driver": 10, "warehouse_op": 8, "supervisor": 7, "dispatcher": 5},
    "OGX": {"ramp_agent": 10, "checkin_agent": 6, "loader": 5, "driver": 4,
            "warehouse_op": 3, "supervisor": 2},
}

# Les postes qui demandent plus de vérifications à l'embauche (brief §6.6).
SENSITIVE_ROLES = {"ramp_agent", "supervisor", "dispatcher"}

_MEN = ["Amine", "Yacine", "Sofiane", "Karim", "Bilal", "Riad", "Nadir", "Walid",
        "Adel", "Fares", "Toufik", "Djamel", "Rachid", "Mourad", "Hamza", "Samir",
        "Lotfi", "Aymen", "Islam", "Mehdi"]
_WOMEN = ["Lamia", "Sara", "Imene", "Nawel", "Meriem", "Hana", "Sabrina", "Amina",
          "Yasmine", "Lina", "Rym", "Asma", "Dounia", "Feriel", "Khadija", "Souad"]
_LAST = ["Benali", "Haddad", "Cherif", "Boumediene", "Zerrouki", "Belkacem",
         "Meziane", "Saidi", "Bouzid", "Ferhat", "Khelifi", "Mansouri", "Brahimi",
         "Hamidi", "Rahmani", "Taleb", "Ouali", "Amrani", "Guerroudj", "Larbi"]


@lru_cache(maxsize=2)
def people(as_of: _dt.date | None = None) -> tuple:
    """Les 140 salariés, toujours les mêmes (graine fixe)."""
    as_of = as_of or _dt.date.today()
    rng = np.random.default_rng(2026)
    men = [f"{f} {l}" for f, l in itertools.product(_MEN, _LAST)]
    women = [f"{f} {l}" for f, l in itertools.product(_WOMEN, _LAST)]
    rng.shuffle(men)
    rng.shuffle(women)
    out, i = [], 0
    for site, roles in STAFFING.items():
        for role, n in roles.items():
            for _ in range(n):
                # Les femmes sont plus nombreuses à l'accueil, présentes partout.
                female = rng.random() < (0.55 if role == "checkin_agent" else 0.22)
                name = (women if female else men).pop()
                age = int(rng.integers(20, 58))
                hire = as_of - _dt.timedelta(days=int(rng.integers(90, 9 * 365)))
                # Un CDD dure rarement plus de deux ans : au-delà, presque tous en CDI.
                long = (as_of - hire).days > 730
                contract = "CDD" if rng.random() < (0.02 if long else 0.45) else "CDI"
                out.append(hr.Employee(
                    emp_id=f"DH{1000 + i}", name=name, role_key=role,
                    wilaya=SITES[site]["wilaya"], hire_date=hire,
                    dependants=int(rng.integers(0, 4)), spouse=bool(rng.random() < 0.5),
                    contract=contract,
                    leave_taken_ytd=float(rng.integers(0, 15)),
                    gender="F" if female else "M",
                    birth_date=as_of.replace(year=as_of.year - age) - _dt.timedelta(
                        days=int(rng.integers(0, 360))),
                    site=site,
                    overtime_hours_month=float(rng.choice([0, 0, 0, 4, 8, 12, 16])),
                ))
                i += 1

    # Les écarts posés exprès, pour que les agents aient de quoi travailler.
    by_role = lambda r: [e for e in out if e.role_key == r]  # noqa: E731
    by_role("ramp_agent")[0].overtime_hours_month = 46     # au-delà de 20 % (art. 31)
    by_role("loader")[1].overtime_hours_month = 41
    by_role("sorter")[2].gross_override = 22_000.0          # saisie sous le SNMG
    for e, days in zip(by_role("checkin_agent")[:2], (3, 7)):
        e.hire_date = as_of - _dt.timedelta(days=days)       # embauches de la semaine
        e.contract = "CDD"
    for e in by_role("sorter")[5:8]:                          # moins de 19 ans (art. 28)
        e.birth_date = as_of.replace(year=as_of.year - 18) - _dt.timedelta(days=40)
    return tuple(out)


def site_of(emp) -> dict:
    return SITES.get(getattr(emp, "site", None) or "ALG", SITES["ALG"])


def age(emp, as_of: _dt.date | None = None) -> int | None:
    if not getattr(emp, "birth_date", None):
        return None
    as_of = as_of or _dt.date.today()
    b = emp.birth_date
    return as_of.year - b.year - ((as_of.month, as_of.day) < (b.month, b.day))


if __name__ == "__main__":
    ppl = people()
    assert len(ppl) == 140, len(ppl)
    assert len({e.name for e in ppl}) == 140, "noms en double"
    assert sum(1 for e in ppl if e.site == "OGX") == 30
    assert sum(1 for e in ppl if age(e) is not None and age(e) < 19) == 3
    women = sum(1 for e in ppl if e.gender == "F")
    print(f"  {len(ppl)} salariés, {women} femmes, "
          f"{sum(1 for e in ppl if e.contract == 'CDD')} CDD, 2 sites : ok")
