"""
core/onboarding.py
------------------
De « offre acceptée » à « pleinement opérationnel », sans que le RH tape rien
(brief §6.6).

1. Le nouvel embauché remplit son dossier depuis son téléphone (lien à usage
   unique, 7 jours). En démo, la lecture des pièces (OCR) est **simulée** à
   partir du dossier fictif : l'interface le dit.
2. L'agent vérifie : pièce non expirée, noms identiques d'un document à l'autre,
   format du NIN et du RIB, âge minimum, moins de 19 ans (pas de nuit, art. 28),
   pièce floue ou manquante. Ce qui ne va pas repart au salarié, pas au RH.
3. Une seule carte pour le RH. À l'approbation, tout part en parallèle :
   contrat, affiliation CNAS, avis ANEM, paie, planning, accès et matériel,
   message d'accueil, puis le parcours (J1, semaine 1, J30/60/90, fin d'essai).

Un poste marqué sensible ajoute de lui-même références, enquête et revue des
accès. Rien n'est envoyé ni déposé sans clic humain : l'agent prépare.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

from . import legal, rules, seed_company

_C = rules.payroll()["onboarding"]
_WT = rules.payroll()["work_time"]

DOC_LABELS = {
    "cni": "Carte d'identité (recto, verso)", "extrait_naissance": "Extrait de naissance",
    "photo": "Photo d'identité", "rib": "RIB ou CCP", "diplome": "Diplôme",
    "certificat_travail": "Certificats de travail antérieurs",
    "aptitude_medicale": "Certificat d'aptitude médicale",
    "service_national": "Situation vis-à-vis du service national",
    "reglement_interieur_signe": "Règlement intérieur signé",
    "charte_donnees_25_11": "Notice données personnelles (loi 25-11) signée",
    "contact_urgence": "Contact en cas d'urgence",
    "references": "Prise de références", "enquete": "Enquête de moralité (résultat seul)",
    "revue_acces": "Revue des droits d'accès",
}


@dataclass
class Registration:
    candidate: str
    role_key: str
    site: str
    start: _dt.date
    contract: str = "CDI"
    cdd_reason: str = ""
    gender: str = "F"
    docs: dict = field(default_factory=dict)   # code -> {"status", "fields"}


def checklist(role_key: str, gender: str) -> list:
    docs = list(_C["documents"])
    if gender != "M":                          # le service national concerne les hommes
        docs = [d for d in docs if d != "service_national"]
    if role_key in seed_company.SENSITIVE_ROLES:
        docs += list(_C["sensitive_extra"])
    return docs


def simulate_upload(reg: Registration, birth: _dt.date, id_expiry: _dt.date,
                    blurry: tuple = ("diplome",)) -> Registration:
    """Démo : ce que l'OCR aurait lu sur chaque pièce. Une pièce floue exprès."""
    for code in checklist(reg.role_key, reg.gender):
        if code in _C["sensitive_extra"]:
            continue
        reg.docs[code] = {"status": "blurry" if code in blurry else "ok", "fields": {}}
    reg.docs["cni"]["fields"] = {"name": reg.candidate, "birth": birth.isoformat(),
                                 "nin": "1" + "0" * 16 + "7", "expiry": id_expiry.isoformat()}
    reg.docs["extrait_naissance"]["fields"] = {"name": reg.candidate, "birth": birth.isoformat()}
    reg.docs["rib"]["fields"] = {"name": reg.candidate, "rib": "00799999000123456789"}
    return reg


def verify(reg: Registration, today: _dt.date | None = None) -> dict:
    """Les contrôles de l'agent. `bounce` repart au salarié, `notes` va au RH."""
    today = today or _dt.date.today()
    need = [d for d in checklist(reg.role_key, reg.gender) if d not in _C["sensitive_extra"]]
    bounce, notes = [], []
    for d in need:
        st = reg.docs.get(d, {}).get("status")
        if st is None:
            bounce.append(f"{DOC_LABELS[d]} : pièce manquante, merci de l'ajouter.")
        elif st == "blurry":
            bounce.append(f"{DOC_LABELS[d]} : la photo est floue, merci de la reprendre.")
    cni = reg.docs.get("cni", {}).get("fields", {})
    names = {v["fields"].get("name") for v in reg.docs.values() if v.get("fields", {}).get("name")}
    if len(names) > 1:
        bounce.append("Le nom diffère d'une pièce à l'autre : vérifiez l'orthographe.")
    if cni:
        exp = _dt.date.fromisoformat(cni["expiry"])
        if exp < today:
            bounce.append("La carte d'identité est expirée.")
        elif (exp - today).days < 180:
            notes.append(f"La pièce d'identité expire dans {(exp - today).days // 30} mois.")
        if not re.fullmatch(r"\d{18}", cni.get("nin", "")):
            bounce.append("Le NIN doit compter 18 chiffres.")
        b = _dt.date.fromisoformat(cni["birth"])
        age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        if age < _C["min_age"]:
            notes.append(f"Âge {age} ans, sous le minimum de {_C['min_age']} ans (art. 15) [à vérifier].")
        elif age < _WT["night_min_age"]:
            notes.append(f"{age} ans : aucun shift de nuit possible (art. 28), le planning le sait.")
    rib = reg.docs.get("rib", {}).get("fields", {}).get("rib", "")
    if rib and not re.fullmatch(r"\d{20}", rib):
        bounce.append("Le RIB doit compter 20 chiffres.")
    if reg.contract == "CDD":
        c = legal.check_cdd(reg.cdd_reason, reg.start, reg.start + _dt.timedelta(days=180))
        if not c["valid"]:
            notes.append("Motif de CDD hors de l'art. 12 : contrat à requalifier en CDI.")
    done = len(need) - sum(1 for d in need if reg.docs.get(d, {}).get("status") != "ok")
    return {"complete": not bounce, "documents_ok": done, "documents_needed": len(need),
            "bounce": bounce, "notes": notes,
            "sensitive": reg.role_key in seed_company.SENSITIVE_ROLES}


def plan(reg: Registration) -> list:
    """Tout ce qui part à l'approbation, avec un responsable et une date."""
    s = reg.start
    d = lambda n: (s + _dt.timedelta(days=n)).isoformat()  # noqa: E731
    trial_months = _WT["trial_max_months"]
    trial_end = s + _dt.timedelta(days=int(trial_months * 30.44))
    tasks = [
        ("Contrat " + reg.contract + " généré, envoyé en signature (repli : impression et scan, loi 26-02)", "RH", d(-5)),
        ("Brouillon d'affiliation CNAS, à déposer sur teledeclaration.cnas.dz", "RH", d(10)),
        ("Avis d'embauche ANEM, brouillon", "RH", d(3)),
        ("Paie : salaire, primes, statut IRG, RIB (attend la première paie)", "Paie", d(-2)),
        ("Planning des deux premières semaines, avec un binôme sur les mêmes shifts", "Planning", d(-3)),
        ("Badge et accès au site", "Sécurité", d(-1)),
        ("Tenue et équipements de protection", "Logistique", d(-1)),
        ("Comptes : messagerie et application", "IT", d(-1)),
        ("Message d'accueil : date, adresse, contact, quoi apporter", "Guichet", d(-2)),
        ("Préparation du manager (3 jours avant)", "Manager", d(-3)),
        ("Jour 1 : accueil, consignes de sécurité, binôme", "Manager", d(0)),
        ("Semaine 1 : formations sécurité, données, conduite, harcèlement, avec quiz", "RH", d(5)),
    ]
    tasks += [(f"Point J{n} dans le guichet", "Guichet", d(n)) for n in _C["checkins_days"]]
    tasks.append((f"Fin d'essai le {trial_end:%d/%m/%Y} : confirmer, prolonger ou mettre fin "
                  f"(art. 18, 20), rappel {_C['trial_reminder_days_before']} j avant", "Manager",
                  (trial_end - _dt.timedelta(days=_C["trial_reminder_days_before"])).isoformat()))
    if reg.role_key in seed_company.SENSITIVE_ROLES:
        tasks += [("Prise de références : courriels préparés, envoi par le RH", "RH", d(-7)),
                  ("Enquête de moralité : résultat, date, auteur (jamais le document)", "Sécurité", d(-3)),
                  ("Revue des droits d'accès : bâtiments et systèmes", "Sécurité", d(-1))]
    return [{"task": t, "owner": o, "due": due} for t, o, due in tasks]


def offboarding(emp, last_day: _dt.date) -> list:
    """Le parcours miroir du départ."""
    return [{"task": t, "owner": o, "due": last_day.isoformat()} for t, o in (
        ("Certificat de travail", "RH"),
        ("Solde de tout compte, congés restants payés", "Paie"),
        ("Restitution du badge et du matériel", "Logistique"),
        ("Fermeture des comptes et révocation des accès", "IT"),
        ("Mises à jour CNAS et ANEM", "RH"),
        ("Questionnaire de départ", "Guichet"),
    )]


def approval_card(reg: Registration, v: dict) -> dict:
    notes = " ".join(v["notes"]) if v["notes"] else "Aucune remarque."
    return {
        "agent": "Intégration",
        "title": (f"Dossier de {reg.candidate} complet et vérifié : "
                  f"{v['documents_ok']}/{v['documents_needed']} pièces"),
        "detail": notes + (" Poste sensible : références, enquête et revue des accès "
                           "ajoutées d'office." if v["sensitive"] else ""),
        "law": "Affiliation CNAS sous 10 jours · loi 90-11 art. 12, 18, 28 · loi 25-11",
        "decision": f"Embauche validée : {len(plan(reg))} tâches lancées en parallèle.",
    }


def launch(con, reg: Registration, emp_id: str) -> int:
    """Après le clic « Approuver l'embauche » : les tâches entrent en base."""
    from . import db
    for t in plan(reg):
        con.execute("INSERT INTO onboarding_tasks (employee_id, task, owner, due, status) "
                    "VALUES (?,?,?,?, 'à faire')", (emp_id, t["task"], t["owner"], t["due"]))
    for code, d in reg.docs.items():
        con.execute("INSERT INTO documents (employee_id, kind, status, created) VALUES (?,?,?,?)",
                    (emp_id, code, "vérifié" if d["status"] == "ok" else d["status"],
                     _dt.date.today().isoformat()))
    con.commit()
    db.log(con, "hr", "hr", "embauche_approuvee", emp_id, reg.candidate)
    return len(plan(reg))


if __name__ == "__main__":
    today = _dt.date(2026, 10, 28)
    reg = Registration("Amina Belkacem", "ramp_agent", "ALG", today + _dt.timedelta(days=12),
                       gender="F")
    simulate_upload(reg, birth=_dt.date(2000, 3, 4), id_expiry=today + _dt.timedelta(days=120))
    v = verify(reg, today)
    assert not v["complete"] and any("floue" in b for b in v["bounce"])
    reg.docs["diplome"]["status"] = "ok"          # le salarié reprend la photo
    v = verify(reg, today)
    assert v["complete"] and v["sensitive"] and any("expire" in n for n in v["notes"])
    tasks = plan(reg)
    assert any("Enquête" in t["task"] for t in tasks) and any("J90" in t["task"] for t in tasks)
    assert "service_national" not in checklist("ramp_agent", "F")
    young = Registration("Test", "sorter", "ALG", today, gender="M")
    simulate_upload(young, birth=_dt.date(2008, 1, 1), id_expiry=today.replace(year=2030), blurry=())
    assert any("art. 28" in n for n in verify(young, today)["notes"])
    print(f"  intégration : {len(tasks)} tâches pour un poste sensible : ok")
