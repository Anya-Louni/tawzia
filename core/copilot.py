"""
core/copilot.py
---------------
Copilote décisionnel — qui apprend de la base de l'entreprise.

The other AI touchpoints answer one narrow question each. This one is the manager
sitting across the desk: you ask "faut-il embaucher ?", "qui risque de partir ?",
"est-ce qu'on est en règle ?", and it answers *grounded in this company's own
numbers*, then recommends and can quantify the recommendation as a scenario.

How it "learns from the company's database"
===========================================
It never free-associates. On every question it first builds a **factual brief**
from the company's data through the owned engines — KPIs (core/kpis), anomalies
(core/anomalies), attrition (core/attrition), the real cost stack (core/labour_dz,
payroll_dz) — all read via core/company_data, so on an imported file the brief is
the customer's real figures. That brief is handed to the language layer
(core/ai, Groq) as the ONLY source of truth, with a strict instruction to reason
only from it and to cite the numbers. The intelligence is in the local models;
Groq turns their output into a decision, in French.

Without an AI key it still works: it returns the brief plus a deterministic,
rule-based recommendation, so the feature degrades to "very useful" rather than
"broken".
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Optional

from . import ai, anomalies as anom_mod, attrition as attr_mod, kpis as kpi_mod


# ---------------------------------------------------------------------------
# The factual brief — the company's own numbers
# ---------------------------------------------------------------------------

def build_brief(people: list, records: list, as_of: Optional[_dt.date] = None,
                source_label: str = "") -> dict:
    """Everything the copilot is allowed to reason from, computed locally."""
    as_of = as_of or _dt.date.today()
    kres = kpi_mod.compute(people, records, as_of)
    ares = anom_mod.detect(people, records, as_of)
    risk_df = kres["extras"].get("risk_frame")

    kpis = {k.key: {"label": k.label, "value": round(float(k.value), 2),
                    "display": k.display, "band": k.band} for k in kres["kpis"]}

    top_anoms = [{
        "gravité": a.severity, "domaine": a.domain, "employé": a.name,
        "constat": a.detail, "action": a.recommendation,
    } for a in ares["anomalies"][:8]]

    top_risk = []
    if risk_df is not None and not risk_df.empty:
        for _, r in risk_df.head(5).iterrows():
            top_risk.append({
                "employé": r["Name"], "risque_%": r["Risk %"],
                "facteur": r["Top driver"],
                "coût_remplacement": int(r["Replacement cost (DZD)"]),
            })

    return {
        "source": source_label or "démonstration",
        "date": as_of.isoformat(),
        "effectif": len(people),
        "kpis": kpis,
        "anomalies": {"total": ares["summary"]["total"],
                      "critiques": ares["summary"]["critique"],
                      "élevées": ares["summary"]["élevée"],
                      "principales": top_anoms},
        "risque_depart": {"resume": attr_mod.summary(risk_df) if risk_df is not None else {},
                          "top": top_risk},
    }


def brief_as_text(brief: dict) -> str:
    """Compact human/LLM-readable rendering of the brief."""
    lines = [f"SOURCE DES DONNÉES : {brief['source']} · {brief['effectif']} employés "
             f"· au {brief['date']}", "", "INDICATEURS CLÉS :"]
    for k in brief["kpis"].values():
        lines.append(f"  - {k['label']} : {k['display']} [{k['band']}]")
    a = brief["anomalies"]
    lines += ["", f"ANOMALIES : {a['total']} au total "
                  f"({a['critiques']} critiques, {a['élevées']} élevées)"]
    for x in a["principales"]:
        lines.append(f"  - [{x['gravité']}] {x['domaine']} · {x['employé']} : {x['constat']}")
    r = brief["risque_depart"]
    if r["top"]:
        lines += ["", "RISQUE DE DÉPART (top) :"]
        for x in r["top"]:
            lines.append(f"  - {x['employé']} : {x['risque_%']}% ({x['facteur']}), "
                         f"remplacement {x['coût_remplacement']:,} DZD")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic recommendation (no key needed)
# ---------------------------------------------------------------------------

def rule_recommendation(brief: dict) -> list:
    """Concrete moves derived from the brief alone, ranked by urgency."""
    recs = []
    a = brief["anomalies"]
    if a["critiques"]:
        recs.append(f":material/error: {a['critiques']} anomalie(s) critique(s) de "
                    f"paie à régulariser en priorité (voir Détection d'anomalies).")
    kpis = brief["kpis"]

    def band_of(key):
        return kpis.get(key, {}).get("band")

    if band_of("absenteeism") in ("surveiller", "critique"):
        recs.append(f":material/event_busy: Absentéisme "
                    f"{kpis['absenteeism']['display']} — cibler 4% libère "
                    f"{kpis.get('absence_cost', {}).get('display', 'du budget')} "
                    f"(simulez-le dans le Simulateur de scénarios).")
    if band_of("attrition_risk") in ("surveiller", "critique"):
        n_high = kpis.get("high_risk", {}).get("display", "plusieurs")
        recs.append(f":material/trending_down: Risque de départ élevé : {n_high} "
                    f"employé(s) à haut risque — entretiens de rétention cette semaine.")
    if band_of("cdd_pct") == "critique":
        recs.append(f":material/badge: Part de CDD {kpis['cdd_pct']['display']} — "
                    f"stabiliser les meilleurs éléments en CDI réduit le turnover.")
    for x in brief["risque_depart"].get("top", [])[:1]:
        recs.append(f":material/priority_high: Parler à {x['employé']} "
                    f"({x['risque_%']}% de risque, {x['facteur'].lower()}).")
    if not recs:
        recs.append(":material/check_circle: Aucun signal critique — indicateurs "
                    "dans les normes. Continuer le suivi hebdomadaire.")
    return recs


# ---------------------------------------------------------------------------
# The AI decision layer, grounded strictly in the brief
# ---------------------------------------------------------------------------

_SYSTEM = (
    "Tu es le copilote décisionnel RH de WorkForce.dz, pour un employeur algérien. "
    "Tu raisonnes UNIQUEMENT à partir du BRIEF chiffré fourni (les vrais chiffres de "
    "l'entreprise, calculés par les modèles maison). N'invente aucun chiffre : si une "
    "donnée manque, dis-le. Cite les indicateurs du brief pour justifier chaque point. "
    "Contexte algérien : SNMG, CNAS, IRG, droit du travail. Réponds en FRANÇAIS, de "
    "façon concise et actionnable. Structure ta réponse : (1) réponse directe, "
    "(2) ce que disent les chiffres, (3) recommandation concrète, et si pertinent "
    "(4) le scénario à simuler pour la chiffrer."
)


def ask(question: str, brief: dict, max_tokens: int = 800) -> dict:
    """
    Answer a manager's question, grounded in the company's brief.

    Returns {"text", "grounded": bool, "recommendations": [...], "used_ai": bool}.
    """
    rule_recs = rule_recommendation(brief)
    if not any(ai.providers_available().values()):
        return {
            "text": "", "grounded": True, "recommendations": rule_recs,
            "used_ai": False,
            "note": "Sans clé IA : recommandations issues des règles. Ajoutez "
                    "GROQ_API_KEY pour une réponse rédigée.",
        }

    user = (f"BRIEF (source de vérité — ne raisonne qu'à partir de ceci) :\n"
            f"{brief_as_text(brief)}\n\nQUESTION DU RESPONSABLE :\n{question}")
    res = ai.chat(_SYSTEM, user, max_tokens=max_tokens, temperature=0.25)
    if not res.ok:
        return {"text": "", "grounded": True, "recommendations": rule_recs,
                "used_ai": False, "note": res.error or "Erreur IA."}
    return {"text": res.text, "grounded": True, "recommendations": rule_recs,
            "used_ai": True, "model": res.model}


SUGGESTED_QUESTIONS = [
    "Quels sont les 3 risques les plus urgents ce mois-ci ?",
    "Faut-il embaucher, et à quel poste en priorité ?",
    "Sommes-nous en règle côté paie et CNAS/IRG ?",
    "Qui risque de partir et que faire pour les retenir ?",
    "Où puis-je réduire les coûts sans casser le service ?",
]


if __name__ == "__main__":
    from . import attendance as att_mod, hr

    print("Copilote décisionnel — self check\n")
    people = hr.sample_workforce("sorter", 50, "Alger")
    records = att_mod.sample_attendance(people, days=20)
    brief = build_brief(people, records, source_label="démonstration (simulée)")
    print(brief_as_text(brief)[:900], "...\n")
    print("Recommandations (règles, sans IA) :")
    for r in rule_recommendation(brief):
        print("   ", r.split(": ", 1)[-1])
    print("\nIA disponible :", any(ai.providers_available().values()))
