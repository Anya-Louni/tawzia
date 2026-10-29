"""
core/seed_company.py
--------------------
The demo company: **fictional**. A ground-handling and logistics firm, 140
employees on two sites, one in Algiers, the other in a southern wilaya
(Ouargla), so the site-dependent rules (southern leave, night-work waiver) show.

No real company's name, logo or figures. Employee names are combinations of
common first and last names, with no link to a real person. A few gaps are
planted on purpose (two overtime breaches, one salary entered below the SNMG,
two hires this week, three employees under 19) so the agents have something
real to find: this is demo data, and the interface says so.
"""

from __future__ import annotations

import datetime as _dt
import itertools
from functools import lru_cache

import numpy as np

from . import hr

COMPANY = {
    "name": "Démo Handling & Logistique",
    "legal_note": "Fictional company, demo data",
    "sector": "Ground handling and logistics",
}

SITES = {
    "ALG": {"name": "Algiers, airport hub and warehouse", "wilaya": "Alger",
            "women_night_derogation": True},
    "OGX": {"name": "Ouargla, southern base", "wilaya": "Ouargla",
            "women_night_derogation": False},
}

# Headcount per site and role: 110 in Algiers, 30 in Ouargla.
STAFFING = {
    "ALG": {"ramp_agent": 30, "checkin_agent": 20, "sorter": 18, "loader": 12,
            "driver": 10, "warehouse_op": 8, "supervisor": 7, "dispatcher": 5},
    "OGX": {"ramp_agent": 10, "checkin_agent": 6, "loader": 5, "driver": 4,
            "warehouse_op": 3, "supervisor": 2},
}

# Roles that need more vetting at hiring (brief §6.6).
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
    """The 140 employees, always the same (fixed seed)."""
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
                # Women are more numerous at check-in, present everywhere.
                female = rng.random() < (0.55 if role == "checkin_agent" else 0.22)
                name = (women if female else men).pop()
                age = int(rng.integers(20, 58))
                hire = as_of - _dt.timedelta(days=int(rng.integers(90, 9 * 365)))
                # A CDD rarely lasts more than two years: beyond that, almost all are CDI.
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

    # The gaps planted on purpose, so the agents have work to do.
    by_role = lambda r: [e for e in out if e.role_key == r]  # noqa: E731
    by_role("ramp_agent")[0].overtime_hours_month = 46     # above 20% (art. 31)
    by_role("loader")[1].overtime_hours_month = 41
    by_role("sorter")[2].gross_override = 22_000.0          # entered below the SNMG
    for e, days in zip(by_role("checkin_agent")[:2], (3, 7)):
        e.hire_date = as_of - _dt.timedelta(days=days)       # hires this week
        e.contract = "CDD"
    for e in by_role("sorter")[5:8]:                          # under 19 (art. 28)
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
    assert len({e.name for e in ppl}) == 140, "duplicate names"
    assert sum(1 for e in ppl if e.site == "OGX") == 30
    assert sum(1 for e in ppl if age(e) is not None and age(e) < 19) == 3
    women = sum(1 for e in ppl if e.gender == "F")
    print(f"  {len(ppl)} employees, {women} women, "
          f"{sum(1 for e in ppl if e.contract == 'CDD')} CDD, 2 sites: ok")
