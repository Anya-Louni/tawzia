"""
core/company_data.py
--------------------
One data spine for every company.

The new AI features (détection d'anomalies, tableau de KPI, copilote décisionnel,
appariement CV) must not each invent their own way of getting at "the company's
data". They all read through here. This module returns the same internal objects
the rest of the engine already speaks (`hr.Employee`, `attendance.ClockRecord`,
`attendance.Request`), from one of two sources:

  * **Imported** — a company uploads its own staff / attendance CSV. Parsed into
    the internal objects and stored in the Streamlit session. This is what makes
    the platform "learn from the company's database" and adapt to any company.
  * **Simulated demo** — when nothing is uploaded, the existing sample generators
    (built on the real Algerian calendar and labour law) provide clearly-labelled
    demonstration data.

The source is always surfaced to the user via `source_label()`, so a simulated
number is never mistaken for a real one. Column names are matched flexibly in
both French and English, because no two HR exports look alike.

No Streamlit import at module top: the parsing/normalising functions are pure and
unit-testable; only the session-backed accessors touch `st`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import numpy as np
import pandas as pd

from . import attendance as att, hr, labour_dz

# Session keys for an uploaded dataset.
_PEOPLE_KEY = "company_people"
_ATT_KEY = "company_attendance"
_LABEL_KEY = "company_source_label"


# ---------------------------------------------------------------------------
# Column resolution (French + English, tolerant)
# ---------------------------------------------------------------------------

_WORKFORCE_ALIASES = {
    "emp_id": ["id", "matricule", "emp_id", "identifiant", "code"],
    "name": ["nom", "name", "nom complet", "employe", "employé", "nom_prenom"],
    "role": ["poste", "role", "rôle", "fonction", "metier", "métier", "emploi"],
    "wilaya": ["wilaya", "region", "région", "site", "lieu", "ville"],
    "hire_date": ["date_embauche", "embauche", "hire_date", "date d'embauche",
                  "date embauche", "anciennete_debut", "date_entree"],
    "contract": ["contrat", "contract", "type_contrat", "type contrat"],
    "dependants": ["personnes_a_charge", "personnes à charge", "dependants",
                   "enfants", "charges", "nb_enfants"],
    "spouse": ["conjoint", "spouse", "marie", "marié", "situation_familiale"],
    "leave_taken": ["conges_pris", "congés pris", "leave_taken", "conges_ytd",
                    "conges_consommes", "jours_conges_pris"],
    "gross": ["brut", "salaire", "salaire_brut", "gross", "brut_mensuel"],
}

_ATT_ALIASES = {
    "emp_id": ["id", "matricule", "emp_id", "identifiant", "code"],
    "name": ["nom", "name", "employe", "employé", "nom_prenom"],
    "date": ["date", "jour", "journee", "journée"],
    "scheduled": ["prevu", "prévu", "scheduled", "heure_prevue", "planifie", "planifié"],
    "actual": ["reel", "réel", "actual", "heure_reelle", "pointage", "clock_in"],
    "shift": ["shift", "poste_horaire", "vacation", "equipe", "équipe"],
}


def _norm(s: str) -> str:
    s = str(s).strip().lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"), ("à", "a"),
                 ("â", "a"), ("ä", "a"), ("î", "i"), ("ï", "i"), ("ô", "o"),
                 ("ö", "o"), ("û", "u"), ("ù", "u"), ("ü", "u"), ("ç", "c")):
        s = s.replace(a, b)
    return s.replace("-", "_").replace(" ", "_")


def _resolve_columns(df: pd.DataFrame, aliases: dict) -> dict:
    """Map our canonical field names to the actual columns present in `df`."""
    present = {_norm(c): c for c in df.columns}
    found = {}
    for field, names in aliases.items():
        for cand in [field] + names:
            key = _norm(cand)
            if key in present:
                found[field] = present[key]
                break
    return found


def _role_key_from_text(text: str, default_key: str) -> str:
    """Best-effort map of a free-text job title to one of our role keys."""
    t = _norm(text)
    if not t:
        return default_key
    if t in labour_dz.ROLES:
        return t
    # direct label containment
    for k, r in labour_dz.ROLES.items():
        for lab in (r.label, labour_dz.LABEL_FR.get(k, "")):
            rl = _norm(lab)
            if rl and (t in rl or rl in t):
                return k
    # token overlap
    t_tokens = set(t.split("_"))
    best, best_score = default_key, 0
    for k, r in labour_dz.ROLES.items():
        score = len(t_tokens & set(_norm(labour_dz.role_aliases(k)).split("_")))
        if score > best_score:
            best, best_score = k, score
    return best


def _to_date(v, default: _dt.date) -> _dt.date:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    try:
        return pd.to_datetime(v, dayfirst=True, errors="raise").date()
    except Exception:
        return default


def _to_time(v) -> Optional[_dt.time]:
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() == "":
        return None
    s = str(v).strip().lower()
    if s in ("absence", "absent", "no-show", "noshow", "-"):
        return None
    try:
        return pd.to_datetime(v, errors="raise").time()
    except Exception:
        try:
            hh, mm = s.split(":")[:2]
            return _dt.time(int(hh), int(mm))
        except Exception:
            return None


# ---------------------------------------------------------------------------
# CSV -> internal objects
# ---------------------------------------------------------------------------

def parse_workforce(df: pd.DataFrame, *, default_role: str = "sorter",
                    default_wilaya: str = "Alger") -> list:
    """Turn an uploaded staff table into a list of `hr.Employee`."""
    cols = _resolve_columns(df, _WORKFORCE_ALIASES)
    today = _dt.date.today()
    people = []
    for i, row in df.reset_index(drop=True).iterrows():
        def g(field, dflt=None):
            c = cols.get(field)
            return row[c] if c is not None and c in row else dflt

        wilaya = str(g("wilaya", default_wilaya) or default_wilaya).strip() or default_wilaya
        role_key = _role_key_from_text(g("role", ""), default_role)
        hire = _to_date(g("hire_date"), today - _dt.timedelta(days=365 * 2))

        spouse_raw = _norm(g("spouse", ""))
        spouse = spouse_raw in ("1", "true", "oui", "yes", "marie", "marié", "m")

        def _int(v, d=0):
            try:
                return int(float(v))
            except Exception:
                return d

        def _float_or_none(v):
            try:
                f = float(str(v).replace(" ", "").replace(",", "."))
                return f if f > 0 else None
            except Exception:
                return None

        people.append(hr.Employee(
            emp_id=str(g("emp_id", f"E{1000 + i}")).strip() or f"E{1000 + i}",
            name=str(g("name", f"Employé {i + 1}")).strip() or f"Employé {i + 1}",
            role_key=role_key,
            wilaya=wilaya,
            hire_date=hire,
            dependants=_int(g("dependants", 0)),
            spouse=spouse,
            contract=str(g("contract", "CDI")).strip().upper() or "CDI",
            leave_taken_ytd=float(_int(g("leave_taken", 0))),
            gross_override=_float_or_none(g("gross")),
        ))
    return people


def parse_attendance(df: pd.DataFrame, people: Optional[list] = None) -> list:
    """Turn an uploaded clock-in table into a list of `attendance.ClockRecord`."""
    cols = _resolve_columns(df, _ATT_ALIASES)
    name_by_id = {p.emp_id: p.name for p in (people or [])}
    default_sched = _dt.time(6, 0)
    records = []
    for _, row in df.reset_index(drop=True).iterrows():
        def g(field, dflt=None):
            c = cols.get(field)
            return row[c] if c is not None and c in row else dflt

        emp_id = str(g("emp_id", "")).strip()
        if not emp_id:
            continue
        date = _to_date(g("date"), _dt.date.today())
        sched = _to_time(g("scheduled")) or default_sched
        actual = _to_time(g("actual"))
        records.append(att.ClockRecord(
            emp_id=emp_id,
            emp_name=str(g("name", name_by_id.get(emp_id, emp_id))).strip(),
            date=date, scheduled=sched, actual=actual,
            shift=str(g("shift", "morning")).strip() or "morning",
        ))
    return records


# ---------------------------------------------------------------------------
# Session-backed store + accessors
# ---------------------------------------------------------------------------

def _ss():
    import streamlit as st
    return st.session_state


def set_company_data(people: list, records: Optional[list] = None,
                     label: str = "Données importées") -> None:
    ss = _ss()
    ss[_PEOPLE_KEY] = people
    ss[_ATT_KEY] = records if records is not None else []
    ss[_LABEL_KEY] = label


def clear_company_data() -> None:
    ss = _ss()
    for k in (_PEOPLE_KEY, _ATT_KEY, _LABEL_KEY):
        ss.pop(k, None)


def is_uploaded() -> bool:
    try:
        return bool(_ss().get(_PEOPLE_KEY))
    except Exception:
        return False


def source_label() -> str:
    """Human-readable provenance, always shown next to any figure."""
    if is_uploaded():
        return _ss().get(_LABEL_KEY, "Données importées")
    return "Demo data (simulated)"


def is_real() -> bool:
    """True only when the figures come from an uploaded company dataset."""
    return is_uploaded()


def people() -> list:
    """The company's employees: uploaded if present, else the simulated demo."""
    if is_uploaded():
        return _ss()[_PEOPLE_KEY]
    from . import appdata
    return appdata.hr_people()


def attendance_records() -> list:
    """The company's clock-in log: uploaded if present, else the simulated demo."""
    if is_uploaded():
        recs = _ss().get(_ATT_KEY) or []
        if recs:
            return recs
    from . import appdata
    return appdata.hr_attendance()


def workforce_template() -> pd.DataFrame:
    """A blank template a company can fill and re-upload."""
    return pd.DataFrame([{
        "matricule": "E1001", "nom": "Exemple Nom", "poste": "Agent de tri (hub)",
        "wilaya": "Alger", "date_embauche": "2021-03-15", "contrat": "CDI",
        "personnes_a_charge": 2, "conjoint": "oui", "conges_pris": 6,
    }])


def attendance_template() -> pd.DataFrame:
    return pd.DataFrame([{
        "matricule": "E1001", "nom": "Exemple Nom", "date": "2026-08-03",
        "prevu": "06:00", "reel": "06:12", "shift": "morning",
    }])


if __name__ == "__main__":
    print("company_data — self check\n")
    wf = workforce_template()
    # round-trip: template -> people -> back to a frame
    ppl = parse_workforce(pd.concat([wf] * 3, ignore_index=True))
    print(f"  parsed {len(ppl)} employees; first role_key resolved to "
          f"{ppl[0].role_key!r} ({labour_dz.ROLES[ppl[0].role_key].label})")
    at_df = attendance_template()
    recs = parse_attendance(pd.concat([at_df] * 2, ignore_index=True), ppl)
    print(f"  parsed {len(recs)} clock records; first flag = {recs[0].flag}")
    # tolerant column names
    alt = wf.rename(columns={"matricule": "ID", "poste": "Fonction", "nom": "Name"})
    ppl2 = parse_workforce(alt)
    print(f"  tolerant parse kept name: {ppl2[0].name!r}, role {ppl2[0].role_key!r}")
