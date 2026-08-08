"""
core/skills.py
--------------
Cartographie des compétences et mobilité interne.

Le recrutement externe est la réponse par défaut à un poste vacant. C'est aussi
la plus chère et la plus lente : il faut sourcer, trier, embaucher, intégrer, et
accepter qu'une part des recrues parte avant d'être rentable. Or dans la plupart
des effectifs, quelqu'un est déjà à deux compétences du poste à pourvoir , et
personne ne le sait, parce que les compétences ne sont écrites nulle part.

Ce module écrit ce qui manque :

  1. **Le référentiel** , quelles compétences, à quel niveau, chaque poste exige.
  2. **Le profil de chaque salarié** , déduit du poste tenu et de l'ancienneté.
  3. **L'écart d'équipe** , les compétences où l'effectif est en dessous du
     niveau requis par son propre poste. C'est le plan de formation.
  4. **La mobilité interne** , qui, dans l'effectif actuel, est le plus près
     d'un poste à pourvoir, ce qui lui manque, et en combien de jours il y est.
  5. **L'arbitrage former / recruter** , les deux coûts côte à côte, avec le
     délai, parce que la décision se prend sur les deux à la fois.

Ce qui est réel, ce qui est modélisé
====================================
Le référentiel de compétences par poste est un choix de modélisation explicite,
construit à partir des rôles de core/labour_dz : il décrit ce que le métier
exige, et c'est la première chose qu'un client remplace par sa propre grille.
Les coûts de formation et de recrutement sont des hypothèses nommées, ci-dessous.
Les profils individuels de la démo sont dérivés de l'effectif synthétique , en
déploiement réel ils viennent de l'évaluation annuelle ou du fichier RH importé.

La déduction est **déterministe** : même salarié, même profil, à chaque
exécution. Un moteur de mobilité qui change d'avis entre deux affichages ne
serait pas utilisable pour une décision de carrière.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import labour_dz, sources

# ---------------------------------------------------------------------------
# Le référentiel de compétences
# ---------------------------------------------------------------------------

SKILLS = {
    "securite": "Sécurité au travail (HSE)",
    "manutention": "Manutention & gestes techniques",
    "scan_wms": "Scan & système de gestion d'entrepôt",
    "inventaire": "Gestion de stock & inventaire",
    "conduite": "Conduite & code de la route",
    "itineraire": "Optimisation de tournée",
    "cash": "Encaissement & gestion des espèces",
    "service_client": "Relation client",
    "langue_ar": "Arabe , usage professionnel",
    "langue_fr": "Français , usage professionnel",
    "langue_en": "Anglais , usage professionnel",
    "informatique": "Outils numériques & bureautique",
    "reservation": "Systèmes de réservation & billetterie",
    "hygiene": "Hygiène & propreté",
    "restauration": "Service en restauration",
    "planification": "Planification & organisation",
    "encadrement": "Encadrement d'équipe",
    "droit_travail": "Droit du travail algérien",
    "kpi": "Pilotage par indicateurs",
    "maintenance": "Maintenance de premier niveau",
    "surete": "Sûreté & procédures aéroportuaires",
    "pedagogie": "Pédagogie & conduite de classe",
}

# Niveau requis par poste, de 1 (notions) à 5 (maîtrise, peut former les autres).
ROLE_SKILLS = {
    "sorter": {"securite": 3, "manutention": 3, "scan_wms": 3, "inventaire": 2,
               "langue_ar": 2, "informatique": 2},
    "warehouse_op": {"securite": 3, "manutention": 3, "scan_wms": 3, "inventaire": 3,
                     "maintenance": 2, "informatique": 2},
    "loader": {"securite": 3, "manutention": 4, "inventaire": 2, "langue_ar": 2},
    "courier": {"conduite": 4, "itineraire": 3, "cash": 3, "service_client": 3,
                "securite": 2, "langue_ar": 3},
    "driver": {"conduite": 4, "itineraire": 3, "securite": 3, "maintenance": 2,
               "langue_ar": 2},
    "ramp_agent": {"securite": 4, "manutention": 3, "surete": 3, "maintenance": 2,
                   "langue_en": 2},
    "checkin_agent": {"service_client": 4, "reservation": 3, "surete": 3,
                      "langue_fr": 3, "langue_en": 3, "langue_ar": 3, "informatique": 3},
    "front_desk": {"service_client": 4, "reservation": 3, "langue_fr": 3,
                   "langue_en": 3, "langue_ar": 3, "informatique": 3, "cash": 2},
    "fnb_staff": {"service_client": 3, "restauration": 3, "hygiene": 3,
                  "langue_fr": 2, "langue_ar": 2, "cash": 2},
    "housekeeper": {"hygiene": 4, "securite": 2, "manutention": 2, "service_client": 2},
    "supervisor": {"encadrement": 4, "planification": 4, "kpi": 3, "droit_travail": 3,
                   "securite": 3, "informatique": 3, "service_client": 2},
    "dispatcher": {"planification": 4, "itineraire": 3, "kpi": 3, "informatique": 3,
                   "encadrement": 2, "langue_ar": 2},
    "teacher": {"pedagogie": 4, "langue_ar": 4, "langue_fr": 3, "planification": 3,
                "informatique": 2},
    "school_life": {"pedagogie": 3, "encadrement": 3, "service_client": 3,
                    "langue_ar": 3, "planification": 2, "securite": 2},
}

# ---------------------------------------------------------------------------
# Hypothèses de coût , nommées pour être remplacées par les chiffres du client
# ---------------------------------------------------------------------------

TRAINING_DAYS_PER_LEVEL = 4        # jours de formation pour gagner un niveau
# Les deux montants viennent du registre des sources, pour qu'ils apparaissent
# sur la page Sources et ne puissent pas diverger du chiffre affiché.
TRAINING_COST_PER_DAY = sources.value("training_cost_per_day")
MAX_TRAINABLE_GAP = 2              # au-delà de 2 niveaux, c'est un autre métier
ONBOARDING_MONTHS = 2.0            # montée en compétence d'une recrue externe
EXTERNAL_RECRUIT_COST = sources.value("external_recruit_cost")
READY_THRESHOLD = 85               # % de couverture au-delà duquel on est prêt


# ---------------------------------------------------------------------------
# Profil de compétences d'un salarié
# ---------------------------------------------------------------------------

def _jitter(emp_id: str, skill: str) -> float:
    """
    Variation individuelle stable, dans [-1, +1].

    Déduite d'un hachage de (matricule, compétence) : deux salariés du même
    poste et de la même ancienneté n'ont pas exactement le même profil, mais
    chacun garde le sien d'une exécution à l'autre.
    """
    h = hashlib.sha256(f"{emp_id}:{skill}".encode()).hexdigest()
    return (int(h[:8], 16) % 2000) / 1000.0 - 1.0


def employee_skills(employee, as_of: Optional[_dt.date] = None) -> dict:
    """
    Le profil de compétences d'un salarié, déduit du poste et de l'ancienneté.

    Un salarié tient son poste : il est donc à peu près au niveau requis, un peu
    en dessous s'il est nouveau, un peu au-dessus après quelques années. Les
    compétences hors de son poste ne sont pas nulles pour autant , le socle
    transversal (langues, sécurité, informatique) s'acquiert partout.
    """
    as_of = as_of or _dt.date.today()
    years = employee.seniority_years(as_of)
    required = ROLE_SKILLS.get(employee.role_key, {})

    # L'expérience fait progresser, en rendements décroissants. Calibré pour
    # qu'une recrue soit nettement sous le niveau de son poste, qu'un salarié
    # de 4-5 ans soit tout juste au niveau, et qu'un ancien le dépasse : sans
    # cela le plan de formation ressort vide, ce qui n'arrive dans aucun
    # effectif réel.
    experience = min(years * 0.22, 1.1)

    profile = {}
    for skill in SKILLS:
        if skill in required:
            base = required[skill] - 1.0 + experience
        else:
            # Socle transversal : présent partout, mais faible.
            base = 0.8 + experience * 0.45
        level = base + _jitter(employee.emp_id, skill) * 0.6
        profile[skill] = int(max(0, min(5, round(level))))
    return profile


def skill_matrix(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """La matrice effectif x compétences, en niveaux 0-5."""
    rows = []
    for e in people:
        prof = employee_skills(e, as_of)
        row = {"ID": e.emp_id, "Nom": e.name,
               "Poste": labour_dz.ROLES[e.role_key].label,
               "Ancienneté (ans)": e.seniority_years(as_of or _dt.date.today())}
        row.update({SKILLS[k]: v for k, v in prof.items()})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Écart d'équipe , le plan de formation
# ---------------------------------------------------------------------------

def team_gaps(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """
    Pour chaque compétence exigée par les postes tenus, l'écart moyen entre le
    niveau réel de l'effectif et le niveau requis.

    Un écart positif est une compétence où l'équipe est en dessous de ce que son
    propre métier demande : c'est le plan de formation, par ordre de priorité.
    """
    if not people:
        return pd.DataFrame(columns=["Compétence", "Niveau requis", "Niveau moyen",
                                     "Écart", "Sous le niveau", "Effectif concerné"])

    as_of = as_of or _dt.date.today()
    agg = {}
    for e in people:
        required = ROLE_SKILLS.get(e.role_key, {})
        prof = employee_skills(e, as_of)
        for skill, req in required.items():
            a = agg.setdefault(skill, {"req_sum": 0.0, "lvl_sum": 0.0, "n": 0, "below": 0})
            a["req_sum"] += req
            a["lvl_sum"] += prof[skill]
            a["n"] += 1
            if prof[skill] < req:
                a["below"] += 1

    rows = []
    for skill, a in agg.items():
        req = a["req_sum"] / a["n"]
        lvl = a["lvl_sum"] / a["n"]
        rows.append({
            "Compétence": SKILLS[skill],
            "Niveau requis": round(req, 1),
            "Niveau moyen": round(lvl, 1),
            "Écart": round(req - lvl, 2),
            "Sous le niveau": a["below"],
            "Effectif concerné": a["n"],
        })
    return (pd.DataFrame(rows)
            .sort_values(["Écart", "Sous le niveau"], ascending=False)
            .reset_index(drop=True))


def training_plan(people: list, top: int = 5, as_of: Optional[_dt.date] = None) -> dict:
    """Chiffrer la remise à niveau des compétences les plus en écart."""
    gaps = team_gaps(people, as_of)
    gaps = gaps[gaps["Écart"] > 0].head(top)
    if gaps.empty:
        return {"lines": [], "total_days": 0, "total_cost": 0}

    lines, total_days, total_cost = [], 0.0, 0.0
    for _, g in gaps.iterrows():
        days = g["Écart"] * TRAINING_DAYS_PER_LEVEL * g["Sous le niveau"]
        cost = days * TRAINING_COST_PER_DAY
        lines.append({
            "Compétence": g["Compétence"],
            "Personnes à former": int(g["Sous le niveau"]),
            "Jours de formation": round(days),
            "Coût (DZD)": round(cost),
        })
        total_days += days
        total_cost += cost
    return {"lines": lines, "total_days": round(total_days),
            "total_cost": round(total_cost)}


# ---------------------------------------------------------------------------
# Mobilité interne
# ---------------------------------------------------------------------------

@dataclass
class Fit:
    emp_id: str
    name: str
    current_role: str
    coverage: int              # % des exigences du poste cible déjà couvertes
    missing: list              # [(compétence, niveau actuel, niveau requis)]
    training_days: int
    training_cost: int
    blocked: bool              # un écart trop grand pour une formation
    verdict: str               # prêt | formable | écart trop large


def role_fit(employee, target_role: str, as_of: Optional[_dt.date] = None) -> Fit:
    """L'adéquation d'un salarié à un poste cible, et ce qu'il faut pour l'y amener."""
    required = ROLE_SKILLS.get(target_role, {})
    prof = employee_skills(employee, as_of)

    covered, total, missing, days, blocked = 0.0, 0.0, [], 0.0, False
    for skill, req in required.items():
        have = prof.get(skill, 0)
        total += req
        covered += min(have, req)
        if have < req:
            gap = req - have
            missing.append((SKILLS[skill], have, req))
            days += gap * TRAINING_DAYS_PER_LEVEL
            if gap > MAX_TRAINABLE_GAP:
                blocked = True

    coverage = int(round(covered / total * 100)) if total else 0
    missing.sort(key=lambda m: m[2] - m[1], reverse=True)

    if blocked:
        verdict = "écart trop large"
    elif coverage >= READY_THRESHOLD and not missing:
        verdict = "prêt"
    elif coverage >= READY_THRESHOLD:
        verdict = "prêt après mise à niveau courte"
    else:
        verdict = "formable"

    return Fit(
        emp_id=employee.emp_id, name=employee.name,
        current_role=labour_dz.ROLES[employee.role_key].label,
        coverage=coverage, missing=missing,
        training_days=int(round(days)),
        training_cost=int(round(days * TRAINING_COST_PER_DAY)),
        blocked=blocked, verdict=verdict,
    )


def mobility_candidates(people: list, target_role: str, top: int = 10,
                        as_of: Optional[_dt.date] = None) -> list:
    """
    Classer l'effectif pour un poste à pourvoir : d'abord les plus proches, et à
    couverture égale, celui qui coûte le moins cher à former.

    Les salariés déjà sur le poste cible sont exclus , on cherche un mouvement.
    """
    fits = [role_fit(e, target_role, as_of) for e in people
            if e.role_key != target_role]
    fits.sort(key=lambda f: (not f.blocked, f.coverage, -f.training_days), reverse=True)
    return fits[:top]


def mobility_frame(fits: list) -> pd.DataFrame:
    rows = []
    for i, f in enumerate(fits, 1):
        rows.append({
            "Rang": i,
            "Salarié": f.name,
            "Poste actuel": f.current_role,
            "Couverture %": f.coverage,
            "Verdict": f.verdict,
            "Compétences manquantes": len(f.missing),
            "À combler": "; ".join(f"{m[0]} ({m[1]}→{m[2]})" for m in f.missing[:3]) or "-",
            "Formation (j)": f.training_days,
            "Coût formation (DZD)": f.training_cost,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Former ou recruter
# ---------------------------------------------------------------------------

def reskill_vs_recruit(fit: Fit, target_role: str) -> dict:
    """
    Les deux options chiffrées côte à côte pour un poste à pourvoir.

    Le coût de la formation interne, ce sont les jours de formation. Le coût du
    recrutement externe, c'est le sourcing plus la période de montée en
    compétence, pendant laquelle le poste est payé sans être pleinement tenu.
    La comparaison inclut le délai, parce qu'un poste vacant coûte aussi.
    """
    role = labour_dz.ROLES[target_role]
    monthly = role.loaded_monthly

    internal_cost = fit.training_cost
    internal_days = fit.training_days

    # Externe : frais de recrutement + productivité perdue pendant l'intégration.
    ramp_loss = monthly * ONBOARDING_MONTHS * 0.5
    external_cost = EXTERNAL_RECRUIT_COST + ramp_loss
    external_days = int(round(ONBOARDING_MONTHS * 30))

    saving = external_cost - internal_cost
    return {
        "internal_cost": round(internal_cost),
        "internal_days": internal_days,
        "external_cost": round(external_cost),
        "external_days": external_days,
        "saving": round(saving),
        "days_saved": external_days - internal_days,
        "recommendation": (
            "Former en interne" if (saving > 0 and not fit.blocked)
            else "Recruter en externe"
        ),
    }


def role_options() -> dict:
    """Les postes cibles disponibles, pour un sélecteur d'UI."""
    return {k: labour_dz.ROLES[k].label for k in ROLE_SKILLS if k in labour_dz.ROLES}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # la console Windows est en cp1252

    print("Compétences & mobilité interne , auto-contrôle\n")
    from . import hr

    people = hr.sample_workforce("sorter", 40, "Alger")

    print("  Écart d'équipe (agents de tri) :")
    print(team_gaps(people).head(6).to_string(index=False))

    plan = training_plan(people)
    print(f"\n  Plan de formation : {plan['total_days']} jours, "
          f"{plan['total_cost']:,} DZD")

    print("\n  Mobilité interne vers « Superviseur de shift » :")
    fits = mobility_candidates(people, "supervisor", top=5)
    print(mobility_frame(fits).to_string(index=False))

    best = fits[0]
    arb = reskill_vs_recruit(best, "supervisor")
    print(f"\n  Arbitrage pour {best.name} :")
    print(f"    former  : {arb['internal_cost']:,} DZD en {arb['internal_days']} j")
    print(f"    recruter: {arb['external_cost']:,} DZD en {arb['external_days']} j")
    print(f"    -> {arb['recommendation']} (économie {arb['saving']:,} DZD, "
          f"{arb['days_saved']} j gagnés)")

    # Déterminisme : deux appels doivent donner exactement le même profil.
    a = employee_skills(people[0])
    b = employee_skills(people[0])
    print(f"\n  Déterministe : {a == b}")
