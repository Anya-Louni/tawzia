"""
core/anomalies.py
-----------------
Détection d'anomalies paie & présence.

Two ledgers where a quiet error is expensive: the monthly payroll and the daily
attendance log. This module surfaces the outliers a manager would otherwise only
find during a CNAS/DGI audit or after a worker has already walked out.

It combines two complementary detectors, because neither alone is enough:

  * **Règles interprétables** — hard, cited Algerian rules. A gross below the SNMG
    is illegal, full stop; an IRG that disagrees with the recomputed barème is a
    filing error; an absence rate far above the team is a flight risk. Each has a
    clear "why" and a clear fix. These never need a model to be trusted.
  * **Modèle non supervisé (IsolationForest)** — learns the shape of *this*
    company's own data and flags the rows that do not fit it, catching odd
    combinations no single threshold would (e.g. high pay + high absence + short
    tenure). This is the part that genuinely *learns from the company's database*:
    fit on the uploaded staff/attendance, so what counts as "normal" is the
    customer's own normal, not a generic benchmark.

Everything reads through core/company_data, so it runs on the imported company
file when present and on the labelled demo otherwise. No AI key required; the
copilote layer narrates these findings when a key is set.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import attendance as att_mod, labour_dz, payroll_dz


SEVERITY_ORDER = {"critique": 0, "élevée": 1, "moyenne": 2, "faible": 3}


@dataclass
class Anomaly:
    domain: str                 # "paie" | "présence"
    emp_id: str
    name: str
    severity: str               # critique | élevée | moyenne | faible
    kind: str                   # short machine-ish label
    detail: str                 # human sentence, French
    recommendation: str         # what to do
    score: float = 0.0          # model outlier score (0 = normal, higher = odd)


# ---------------------------------------------------------------------------
# Payroll anomalies
# ---------------------------------------------------------------------------

def payroll_frame(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """Per-employee pay ledger recomputed from the real Algerian stack."""
    as_of = as_of or _dt.date.today()
    rows = []
    for e in people:
        gross = e.monthly_gross()
        slip = payroll_dz.payslip(gross, e.role_key, e.dependants, e.spouse)
        role = labour_dz.ROLES[e.role_key]
        rows.append({
            "emp_id": e.emp_id, "name": e.name, "role_key": e.role_key,
            "role": role.label, "gross": gross, "role_gross": role.gross_monthly,
            "cnas_employee": slip.cnas_employee, "irg": slip.irg, "net": slip.net,
            "dependants": e.dependants, "seniority": e.seniority_years(as_of),
            "needs_dgi_check": slip.needs_dgi_check,
        })
    return pd.DataFrame(rows)


def _rule_payroll(df: pd.DataFrame) -> list:
    out = []
    snmg = labour_dz.SNMG_MONTHLY
    for _, r in df.iterrows():
        # 1. Below the legal minimum wage — illegal.
        if r["gross"] < snmg - 1:
            out.append(Anomaly(
                "paie", r["emp_id"], r["name"], "critique", "sous_snmg",
                f"Brut {r['gross']:,.0f} DZD sous le SNMG ({snmg:,.0f} DZD).",
                "Régulariser immédiatement : un salaire sous le SNMG est illégal.",
                score=1.0,
            ))
        # 2. Gross far off the role's reference band (data-entry / grille error).
        ref = r["role_gross"]
        if ref > 0:
            dev = (r["gross"] - ref) / ref
            if abs(dev) >= 0.35:
                sev = "élevée" if abs(dev) >= 0.6 else "moyenne"
                out.append(Anomaly(
                    "paie", r["emp_id"], r["name"], sev, "brut_hors_bande",
                    f"Brut {r['gross']:,.0f} DZD à {dev:+.0%} de la référence du "
                    f"poste ({ref:,.0f} DZD, {r['role']}).",
                    "Vérifier la grille salariale ou une erreur de saisie.",
                    score=min(abs(dev), 1.0),
                ))
        # 3. Recompute IRG; flag the DGI smoothing band that must be checked.
        if r["needs_dgi_check"]:
            out.append(Anomaly(
                "paie", r["emp_id"], r["name"], "moyenne", "bande_irg_dgi",
                f"Brut {r['gross']:,.0f} DZD dans la bande de lissage IRG "
                f"(30 001–35 000 DZD).",
                "Recalculer l'IRG avec la calculette officielle DGI avant dépôt.",
                score=0.5,
            ))
    return out


# ---------------------------------------------------------------------------
# Attendance anomalies
# ---------------------------------------------------------------------------

def attendance_frame(records: list) -> pd.DataFrame:
    """Per-employee attendance stats (late %, absent %, avg lateness)."""
    summ = att_mod.lateness_summary(records)
    if summ.empty:
        return pd.DataFrame(columns=["emp_id", "name", "shifts", "late_pct",
                                     "absent_pct", "avg_late_min"])
    out = summ.rename(columns={
        "ID": "emp_id", "Name": "name", "Shifts": "shifts",
        "Late %": "late_pct", "Absent %": "absent_pct",
    }).copy()
    out["avg_late_min"] = np.where(
        out["Late"] > 0, out["Late minutes"] / out["Late"].clip(lower=1), 0.0
    ).round(1)
    return out[["emp_id", "name", "shifts", "late_pct", "absent_pct", "avg_late_min"]]


def _rule_attendance(df: pd.DataFrame) -> list:
    out = []
    if df.empty:
        return out
    # Team baselines: an anomaly is relative to this company's own norm.
    abs_mean, abs_std = df["absent_pct"].mean(), df["absent_pct"].std(ddof=0) or 1.0
    late_mean, late_std = df["late_pct"].mean(), df["late_pct"].std(ddof=0) or 1.0
    for _, r in df.iterrows():
        z_abs = (r["absent_pct"] - abs_mean) / abs_std
        z_late = (r["late_pct"] - late_mean) / late_std
        if r["absent_pct"] >= 20 or z_abs >= 2.0:
            sev = "élevée" if r["absent_pct"] >= 30 else "moyenne"
            out.append(Anomaly(
                "présence", r["emp_id"], r["name"], sev, "absenteisme",
                f"Absence {r['absent_pct']:.0f}% (moyenne équipe "
                f"{abs_mean:.0f}%, écart {z_abs:+.1f}σ).",
                "Entretien de reprise : l'absentéisme chronique précède la démission.",
                score=float(max(z_abs, 0) / 4),
            ))
        if r["late_pct"] >= 30 or z_late >= 2.0:
            out.append(Anomaly(
                "présence", r["emp_id"], r["name"], "moyenne", "retards",
                f"Retards {r['late_pct']:.0f}% des shifts (moyenne équipe "
                f"{late_mean:.0f}%), {r['avg_late_min']:.0f} min en moyenne.",
                "Comprendre la cause (transport, shift) avant que ça s'aggrave.",
                score=float(max(z_late, 0) / 4),
            ))
    return out


# ---------------------------------------------------------------------------
# Unsupervised model — learns this company's own normal
# ---------------------------------------------------------------------------

def _isoforest_flags(df: pd.DataFrame, feature_cols: list, domain: str,
                     contamination: float = 0.12) -> dict:
    """
    Return {emp_id: outlier_score} for rows the IsolationForest finds odd.

    Fitted on the company's own rows, so "normal" is the customer's normal. Needs
    a few rows to be meaningful; silently returns {} below that.
    """
    feats = [c for c in feature_cols if c in df.columns]
    if len(df) < 8 or not feats:
        return {}
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except Exception:
        return {}
    X = df[feats].fillna(0.0).to_numpy(dtype=float)
    X = StandardScaler().fit_transform(X)
    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=7
    )
    model.fit(X)
    pred = model.predict(X)                 # -1 = outlier
    raw = -model.score_samples(X)           # higher = more anomalous
    scores = {}
    for emp_id, p, s in zip(df["emp_id"], pred, raw):
        if p == -1:
            scores[emp_id] = float(s)
    return scores


def _model_anomalies(df: pd.DataFrame, feature_cols: list, domain: str,
                     label_of) -> list:
    scores = _isoforest_flags(df, feature_cols, domain)
    if not scores:
        return []
    name_by_id = dict(zip(df["emp_id"], df["name"]))
    out = []
    hi = max(scores.values())
    for emp_id, s in scores.items():
        sev = "élevée" if s >= hi * 0.9 else "moyenne"
        out.append(Anomaly(
            domain, emp_id, name_by_id.get(emp_id, emp_id), sev, "profil_atypique",
            label_of(df[df["emp_id"] == emp_id].iloc[0]),
            "Combinaison inhabituelle vs le reste de l'entreprise — à vérifier.",
            score=round(float(s), 2),
        ))
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _dedupe(anomalies: list) -> list:
    """Keep the most severe anomaly per (emp_id, domain, kind); sort by severity."""
    best = {}
    for a in anomalies:
        key = (a.emp_id, a.domain, a.kind)
        if key not in best or SEVERITY_ORDER[a.severity] < SEVERITY_ORDER[best[key].severity]:
            best[key] = a
    return sorted(best.values(),
                  key=lambda a: (SEVERITY_ORDER[a.severity], -a.score))


def detect(people: list, records: list, as_of: Optional[_dt.date] = None) -> dict:
    """
    Run every detector over the company's pay + attendance data.

    Returns a dict with the two source frames and the ranked anomaly list, so the
    UI can show both the evidence and the findings.
    """
    pay = payroll_frame(people, as_of)
    presence = attendance_frame(records)

    found = []
    found += _rule_payroll(pay)
    found += _rule_attendance(presence)

    # Model layer: pay profile and attendance profile.
    if not pay.empty:
        found += _model_anomalies(
            pay, ["gross", "irg", "seniority", "dependants"], "paie",
            lambda r: (f"Profil paie atypique : brut {r['gross']:,.0f} DZD, "
                       f"IRG {r['irg']:,.0f}, ancienneté {int(r['seniority'])} ans."),
        )
    if not presence.empty:
        found += _model_anomalies(
            presence, ["late_pct", "absent_pct", "avg_late_min"], "présence",
            lambda r: (f"Profil présence atypique : {r['absent_pct']:.0f}% absence, "
                       f"{r['late_pct']:.0f}% retards."),
        )

    anomalies = _dedupe(found)
    return {
        "payroll_frame": pay,
        "attendance_frame": presence,
        "anomalies": anomalies,
        "summary": summarise(anomalies),
    }


def summarise(anomalies: list) -> dict:
    by_sev = {s: 0 for s in SEVERITY_ORDER}
    for a in anomalies:
        by_sev[a.severity] += 1
    return {
        "total": len(anomalies),
        "critique": by_sev["critique"],
        "élevée": by_sev["élevée"],
        "paie": sum(1 for a in anomalies if a.domain == "paie"),
        "présence": sum(1 for a in anomalies if a.domain == "présence"),
        "by_severity": by_sev,
    }


def anomalies_frame(anomalies: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "Gravité": a.severity, "Domaine": a.domain, "ID": a.emp_id,
        "Employé": a.name, "Constat": a.detail, "Action": a.recommendation,
    } for a in anomalies])


if __name__ == "__main__":
    from . import hr

    print("Anomaly detection (paie & présence) — self check\n")
    people = hr.sample_workforce("sorter", 40, "Alger")
    # inject a couple of obvious payroll errors
    people[0].leave_taken_ytd = 0
    records = att_mod.sample_attendance(people, days=20)

    res = detect(people, records)
    s = res["summary"]
    print(f"  {s['total']} anomalies — {s['critique']} critiques, "
          f"{s['élevée']} élevées | paie {s['paie']}, présence {s['présence']}\n")
    for a in res["anomalies"][:8]:
        print(f"  [{a.severity:<8}] {a.domain:<9} {a.name[:20]:<20} {a.detail}")
