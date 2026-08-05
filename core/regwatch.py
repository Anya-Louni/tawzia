"""
core/regwatch.py
----------------
La veille du Journal Officiel.

Les règles algériennes du travail et de la paie bougent : le SNMG, les taux
CNAS, les tranches IRG, les congés et les heures supplémentaires changent par
décret. En manquer un met discrètement une entreprise hors conformité. Ce module
tient un registre des règles suivies, vérifie si la configuration du client
correspond encore à la valeur légale, et, pour tout changement, calcule qui est
affecté et ce que cela coûte, puis rédige la note de conformité.

Honnêteté : dans cette démonstration, le registre est un résumé curé des règles
suivies, avec les valeurs légales actuelles déjà utilisées par le moteur. En
production, il est alimenté par l'ingestion automatique du Journal Officiel et
des publications CNAS/DGI. Le contrôle "votre statut" et le simulateur de
changement, eux, sont réels : ils comparent et recalculent sur l'effectif réel.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

from . import labour_dz, ai, hr

IRG_EXEMPT_THRESHOLD = 30_000   # revenu mensuel exonéré d'IRG au plus


def our_config() -> dict:
    return {
        "snmg": labour_dz.SNMG_MONTHLY,
        "cnas_employer": labour_dz.CNAS_EMPLOYER,
        "cnas_employee": labour_dz.CNAS_EMPLOYEE,
        "overtime_cap": labour_dz.MAX_OVERTIME_FRACTION,
        "annual_leave": hr.ANNUAL_LEAVE_DAYS,
        "irg_exempt": IRG_EXEMPT_THRESHOLD,
    }


# Le registre des règles suivies (résumé curé). `legal_value` est la valeur
# légale actuelle ; `param` relie l'entrée à our_config().
REGISTER = [
    {"param": "snmg", "domain": "Salaire minimum",
     "ref": "SNMG , Loi de finances / décret exécutif",
     "title": "Salaire National Minimum Garanti (SNMG)",
     "summary": "Le salaire minimum mensuel national pour un temps plein.",
     "legal_value": labour_dz.SNMG_MONTHLY, "unit": "DZD/mois",
     "effective": "en vigueur"},
    {"param": "cnas_employer", "domain": "Sécurité sociale",
     "ref": "CNAS , Loi 83-11 et textes d'application",
     "title": "Taux de cotisation CNAS employeur",
     "summary": "Cotisation patronale de sécurité sociale sur le salaire brut.",
     "legal_value": labour_dz.CNAS_EMPLOYER, "unit": "taux",
     "effective": "en vigueur"},
    {"param": "cnas_employee", "domain": "Sécurité sociale",
     "ref": "CNAS , Loi 83-11 et textes d'application",
     "title": "Taux de cotisation CNAS salarié",
     "summary": "Cotisation salariale de sécurité sociale retenue sur le brut.",
     "legal_value": labour_dz.CNAS_EMPLOYEE, "unit": "taux",
     "effective": "en vigueur"},
    {"param": "irg_exempt", "domain": "Impôt sur le revenu",
     "ref": "Barème IRG , Loi de finances",
     "title": "Seuil d'exonération IRG",
     "summary": "Un salaire mensuel à ce niveau ou en-dessous est exonéré d'IRG.",
     "legal_value": IRG_EXEMPT_THRESHOLD, "unit": "DZD/mois",
     "effective": "en vigueur"},
    {"param": "overtime_cap", "domain": "Temps de travail",
     "ref": "Loi 90-11 , temps de travail",
     "title": "Plafond d'heures supplémentaires",
     "summary": "Les heures sup ne peuvent dépasser cette part du temps légal.",
     "legal_value": labour_dz.MAX_OVERTIME_FRACTION, "unit": "taux",
     "effective": "en vigueur"},
    {"param": "annual_leave", "domain": "Congés",
     "ref": "Loi 90-11 , congé annuel",
     "title": "Congés annuels payés",
     "summary": "Congé annuel payé minimum (plus le bonus des wilayas du sud).",
     "legal_value": hr.ANNUAL_LEAVE_DAYS, "unit": "jours/an",
     "effective": "en vigueur"},
]


def _fmt(value, unit) -> str:
    if unit == "taux":
        return f"{value:.0%}"
    if unit.startswith("DZD"):
        return f"{value:,.0f} {unit}"
    return f"{value:g} {unit}"


def status() -> list:
    """Compare la configuration réelle du moteur à chaque valeur légale suivie."""
    cfg = our_config()
    rows = []
    for item in REGISTER:
        ours = cfg.get(item["param"])
        legal = item["legal_value"]
        ok = abs(float(ours) - float(legal)) < 1e-9
        rows.append({
            "Règle": item["title"],
            "Domaine": item["domain"],
            "Votre paramètre": _fmt(ours, item["unit"]),
            "Valeur légale actuelle": _fmt(legal, item["unit"]),
            "Statut": "À jour" if ok else "OBSOLÈTE",
            "Référence": item["ref"],
        })
    return rows


@dataclass
class ChangeImpact:
    param: str
    old_value: float
    new_value: float
    unit: str
    affected: int
    workforce: int
    annual_cost_delta: float
    detail: str


def simulate_change(people, param: str, new_value: float,
                    as_of: Optional[_dt.date] = None) -> ChangeImpact:
    """Recalcule l'impact d'un changement de règle proposé sur l'effectif réel."""
    as_of = as_of or _dt.date.today()
    cfg = our_config()
    old_value = float(cfg.get(param, 0.0))
    unit = next((i["unit"] for i in REGISTER if i["param"] == param), "")
    n = len(people)
    affected = 0
    cost_delta = 0.0
    detail = ""

    if param == "snmg":
        loaded = 1 + labour_dz.CNAS_EMPLOYER
        for e in people:
            g = e.monthly_gross()
            if g < new_value:
                affected += 1
                cost_delta += (new_value - g) * 12 * loaded
        detail = (f"{affected} employés sur {n} sont sous le SNMG proposé de "
                  f"{new_value:,.0f} DZD et doivent y être relevés.")
    elif param in ("cnas_employer",):
        total_gross = sum(e.monthly_gross() for e in people)
        cost_delta = total_gross * 12 * (new_value - old_value)
        affected = n
        detail = (f"Le taux CNAS employeur passe de {old_value:.0%} à "
                  f"{new_value:.0%} sur toute la masse salariale.")
    else:
        detail = ("Ce changement de règle est suivi pour la conformité ; il n'a "
                  "pas de formule de coût direct dans ce simulateur.")

    return ChangeImpact(param, old_value, float(new_value), unit,
                        affected, n, round(cost_delta), detail)


def impact_notice(change: ChangeImpact, lang: str = "fr") -> str:
    """Note IA "ce que vous devez faire" pour un changement de règle."""
    lang_name = "French" if lang == "fr" else "English"
    system = (
        "You are a compliance officer for an Algerian HR platform. Write a short, "
        "practical notice telling the employer exactly what to change for a labour "
        "rule update. Ground strictly in the numbers given. "
        f"Write in {lang_name}."
    )
    old = _fmt(change.old_value, change.unit)
    new = _fmt(change.new_value, change.unit)
    user = (
        f"Rule '{change.param}' changes from {old} to {new}. "
        f"Impact: {change.detail} Estimated annual payroll cost change: "
        f"{change.annual_cost_delta:,.0f} DZD. Write: what to update in the system, "
        f"which employees/contracts are affected, and the deadline framing. "
        f"Under 130 words."
    )
    r = ai.chat(system, user, max_tokens=380, temperature=0.3)
    if r.ok and r.text.strip():
        return r.text.strip()
    # repli sans IA
    return (f"Action requise : mettre à jour « {change.param} » de {old} à {new}. "
            f"{change.detail} Variation annuelle estimée : "
            f"{change.annual_cost_delta:,.0f} DZD. À appliquer à la date d'effet, "
            f"puis relancer la paie et le contrôle de conformité.")


if __name__ == "__main__":
    from . import hr as _hr
    print("Veille Journal Officiel , auto-test\n")
    for r in status():
        print(f"  {r['Règle']:<34} {r['Statut']:<10} vous={r['Votre paramètre']}  légal={r['Valeur légale actuelle']}")
    people = _hr.sample_workforce("sorter", 30, "Alger")
    imp = simulate_change(people, "snmg", labour_dz.SNMG_MONTHLY + 6000)
    print("\nSNMG +6000 :", imp.detail, "| coût", f"{imp.annual_cost_delta:,.0f} DZD")
    print("\nnote (repli) :\n", impact_notice(imp, "fr"))
