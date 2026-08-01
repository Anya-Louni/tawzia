"""
core/odoo_bridge.py
-------------------
Odoo connector.

Many Algerian SMEs already run Odoo (often with a local payroll module like
dz_paie or eloapps_hr_dz). Rather than replace it, WorkForce.dz plugs in: it
reads employees and contracts out of Odoo over the standard XML-RPC API and maps
them into our own Employee model, so all the AI (forecasting, the inspection
simulator, the Journal Officiel watch, retention) runs on the customer's real
Odoo data with zero re-entry.

`from_odoo_records` is pure and unit-tested offline. `connect_and_fetch` uses
Odoo's documented /xmlrpc/2 endpoints (common.authenticate + object.execute_kw
with search_read) - the same calls Odoo's own external-API docs show.
"""

from __future__ import annotations

import datetime as _dt
from typing import List, Optional

from . import hr, labour_dz


def _guess_role(job_title: str, default: str) -> str:
    """Map an Odoo job title onto one of our costed roles."""
    t = (job_title or "").lower()
    table = {
        "driver": "driver", "chauffeur": "driver", "livreur": "driver",
        "picker": "sorter", "sorter": "sorter", "prepar": "sorter", "magasin": "loader",
        "loader": "loader", "manuten": "loader",
        "front": "front_desk", "reception": "front_desk", "accueil": "front_desk",
        "house": "housekeeper", "menage": "housekeeper",
        "dispatch": "dispatcher", "supervis": "dispatcher",
    }
    for needle, role in table.items():
        if needle in t and role in labour_dz.ROLES:
            return role
    return default if default in labour_dz.ROLES else next(iter(labour_dz.ROLES))


def _parse_date(value) -> _dt.date:
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str) and value:
        try:
            return _dt.date.fromisoformat(value[:10])
        except ValueError:
            pass
    return _dt.date.today()


def from_odoo_records(employees: List[dict], contracts: Optional[List[dict]] = None,
                      default_role: str = "sorter", wilaya: str = "Alger") -> List[hr.Employee]:
    """Map Odoo hr.employee (+ optional hr.contract) records to our Employee list."""
    contracts = contracts or []
    # index the newest running contract per employee id
    by_emp: dict = {}
    for c in contracts:
        emp_ref = c.get("employee_id")
        emp_id = emp_ref[0] if isinstance(emp_ref, (list, tuple)) else emp_ref
        if emp_id is None:
            continue
        prev = by_emp.get(emp_id)
        if prev is None or str(c.get("date_start", "")) > str(prev.get("date_start", "")):
            by_emp[emp_id] = c

    people: List[hr.Employee] = []
    for e in employees:
        oid = e.get("id")
        contract = by_emp.get(oid, {})
        job = e.get("job_title") or (e.get("job_id")[1] if isinstance(e.get("job_id"), (list, tuple)) else "")
        role = _guess_role(job, default_role)
        # Odoo contract_type: often a Many2one; 'CDD'/'CDI' by name if present
        ct = contract.get("contract_type_id")
        ct_name = ct[1].upper() if isinstance(ct, (list, tuple)) and len(ct) > 1 else str(ct or "")
        contract_kind = "CDD" if "CDD" in ct_name or "DETERMIN" in ct_name else "CDI"
        hire = _parse_date(contract.get("date_start") or e.get("first_contract_date"))
        people.append(hr.Employee(
            emp_id=str(oid),
            name=e.get("name", f"Employee {oid}"),
            role_key=role,
            wilaya=e.get("wilaya") or wilaya,
            hire_date=hire,
            contract=contract_kind,
        ))
    return people


def connect_and_fetch(url: str, db: str, username: str, password: str,
                      limit: int = 500, default_role: str = "sorter",
                      wilaya: str = "Alger") -> List[hr.Employee]:
    """Pull employees + contracts from a live Odoo over XML-RPC and map them.

    Standard Odoo external API: authenticate on /xmlrpc/2/common, then
    execute_kw('search_read') on /xmlrpc/2/object.
    """
    import xmlrpc.client  # stdlib, no extra dependency

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed - check url, db, user, password.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    employees = models.execute_kw(
        db, uid, password, "hr.employee", "search_read",
        [[]], {"fields": ["id", "name", "job_title", "job_id"], "limit": limit})
    contracts = models.execute_kw(
        db, uid, password, "hr.contract", "search_read",
        [[["state", "in", ["open", "draft"]]]],
        {"fields": ["employee_id", "date_start", "wage", "contract_type_id"], "limit": limit})
    return from_odoo_records(employees, contracts, default_role=default_role, wilaya=wilaya)


if __name__ == "__main__":
    print("Odoo bridge - self check (offline mapping)\n")
    emps = [
        {"id": 1, "name": "Amine B.", "job_title": "Livreur"},
        {"id": 2, "name": "Sara C.", "job_id": [7, "Reception"]},
        {"id": 3, "name": "Karim M.", "job_title": "Magasinier"},
    ]
    cons = [
        {"employee_id": [1, "Amine B."], "date_start": "2023-02-01", "contract_type_id": [2, "CDD"]},
        {"employee_id": [2, "Sara C."], "date_start": "2021-09-15", "contract_type_id": [1, "CDI"]},
    ]
    people = from_odoo_records(emps, cons)
    for p in people:
        print(f"  {p.name:<10} role={p.role_key:<11} contract={p.contract} hired={p.hire_date}")
    assert len(people) == 3
    assert people[0].contract == "CDD"
    print("\nOK - Odoo records map into", len(people), "Employee objects.")
