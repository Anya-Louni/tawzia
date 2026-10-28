"""
core/autopilot.py
-----------------
L'autopilote RH : chaque moteur de la plateforme passe sur les données du jour,
fait le travail, et ne laisse au responsable que les décisions.

Le principe
===========
Un logiciel RH classique attend qu'on ouvre ses écrans. Ici, les agents tournent
d'abord (présence, paie, conformité, déclarations, rétention, recrutement,
guichet salarié) et produisent une **boîte de décisions** : chaque carte dit ce
qui a été fait, pourquoi, ce que l'approbation déclenche et l'argent en jeu.

Aucun agent n'envoie, ne dépose, ne paie ni ne refuse sans un clic humain.
Ce qui est conforme à la loi et sans risque opérationnel (`auto=True`) est
regroupé pour être signé d'un seul clic ; le reste a sa propre carte. Le moteur
prépare et recommande, l'humain signe.

Les minutes « économisées » sont une **hypothèse** (temps manuel moyen par
tâche, `MANUAL_MINUTES`) et sont présentées comme telle.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import (anomalies as anom_mod, attendance, compliance, cv_screen,
               deadlines_dz as dl, retention, talent)

# Temps manuel moyen par tâche, en minutes. Hypothèse, pas une mesure : ce
# qu'un gestionnaire RH passe à vérifier une demande, recalculer un bulletin,
# préparer une déclaration. Un pilote le remplace par le chronométrage réel.
MANUAL_MINUTES = {
    "request": 8,        # vérifier solde, préavis, planning, répondre
    "anomaly": 25,       # retrouver l'écart, recalculer, corriger
    "deadline": 90,      # préparer une déclaration CNAS / G50 / DAS
    "compliance": 30,    # lire le texte, vérifier le dossier
    "retention": 45,     # analyser un départ probable, préparer l'entretien
    "shortlist": 120,    # trier les CV reçus pour un poste
    "ticket": 12,        # attestation, solde, copie de bulletin
    "payroll": 240,      # clôture de paie mensuelle, contrôles compris
    "anem": 40,          # suivi de l'offre ANEM et compte rendu par candidat
    "affiliation": 30,   # dossier d'affiliation CNAS d'un nouvel embauché
}

# Fenêtre ANEM : jours ouvrés laissés à l'agence pour proposer des candidats
# avant tout recrutement direct (loi 04-19 modifiée par la loi 20-03).
ANEM_WINDOW_DAYS = 5
CNAS_AFFILIATION_DAYS = 10

AGENTS = ("Présence", "Paie", "Conformité", "Déclarations", "Rétention",
          "Recrutement", "Guichet")


def working_days_between(a: _dt.date, b: _dt.date) -> int:
    """Jours ouvrés de a (exclu) à b (inclus), hors week-end vendredi-samedi."""
    n, d = 0, a
    while d < b:
        d += _dt.timedelta(days=1)
        if d.weekday() not in (4, 5):
            n += 1
    return n


@dataclass
class Action:
    key: str                 # identifiant stable, pour mémoriser la décision
    agent: str               # l'agent qui a produit la carte
    title: str               # la décision, en une ligne
    detail: str              # ce que l'agent a constaté et fait
    decision: str            # ce que « Approuver » déclenche
    urgency: int             # 0 critique, 1 haute, 2 normale, 3 info
    minutes: float           # temps manuel évité (hypothèse)
    stakes_dzd: float = 0.0  # argent en jeu, si chiffrable
    auto: bool = False       # conforme et sans arbitrage : signable en lot
    page: str = ""           # écran de détail (chemin app_pages/...)
    law: str = ""            # le texte ou la source appliquée
    payload: dict = field(default_factory=dict)


@dataclass
class Run:
    actions: list            # toutes les cartes produites
    log: list                # (agent, ce qui a été traité) pour le journal

    def pending(self, decided: dict) -> list:
        return [a for a in self.actions if a.key not in decided]

    def handled(self, decided: dict) -> list:
        return [a for a in self.actions if a.key in decided]


# ---------------------------------------------------------------------------
# Les agents
# ---------------------------------------------------------------------------

_REC_FR = {
    "approve": "approuver", "approve_with_cover": "approuver avec remplacement",
    "approve_with_note": "approuver avec réserve", "reject": "refuser",
    "record": "enregistrer", "review": "revue manuelle",
}


def _requests_agent(requests, people, forecast, as_of) -> tuple[list, str]:
    lookup = {e.emp_id: e for e in people}
    out = []
    for r in requests:
        emp = lookup.get(r.emp_id)
        if emp is None or r.status != "pending":
            continue
        d = attendance.decide_request(r, emp, as_of=as_of, forecast=forecast)
        rec = d["recommend"]
        span = (f"le {r.start:%d/%m}" if r.is_sortie
                else f"du {r.start:%d/%m} au {r.end:%d/%m}")
        why = " ".join((d["warnings"] or d["reasons"])[:1])
        out.append(Action(
            key=f"req:{r.req_id}", agent="Présence",
            title=f"{r.kind_label} de {r.emp_name} {span} : {_REC_FR.get(rec, rec)}",
            detail=f"« {r.reason} ». {why}",
            decision=("Réponse envoyée au salarié, planning mis à jour."
                      if rec != "reject" else
                      "Refus motivé envoyé au salarié, avec les dates possibles."),
            urgency=1 if rec in ("reject", "approve_with_cover") else 2,
            minutes=MANUAL_MINUTES["request"],
            # Conforme et sans pic : rien à arbitrer, l'agent répond seul.
            auto=rec in ("approve", "record"),
            page="app_pages/requests_view.py",
            law=("Loi 83-11, assurances sociales" if r.kind == "sick" else
                 "Loi 90-11, art. 54 (absences spéciales)" if r.kind == "family" else
                 "Loi 90-11, art. 39 à 42 (congé annuel)" if r.kind == "annual" else
                 "Règlement intérieur, demandes de sortie"),
            payload={"recommend": rec, "req_id": r.req_id},
        ))
    return out, f"{len(out)} demandes de congé et de sortie vérifiées (solde, préavis, charge prévue)"


_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")


def _payroll_agent(people, records, as_of) -> tuple[list, str]:
    """La paie du mois, recalculée et contrôlée : une seule carte à signer."""
    res = anom_mod.detect(people, records, as_of)
    pay = res["payroll_frame"]
    issues, seen = [], set()
    for a in res["anomalies"]:
        # Seules les règles de paie violées comptent ici. Les profils
        # « atypiques » du modèle et la présence restent dans l'écran de détail.
        if a.domain != "paie" or a.detail.startswith("Profil") or a.emp_id in seen:
            continue
        seen.add(a.emp_id)
        issues.append(f"{a.name} : {a.detail.rstrip('.')}")
    # Heures sup. du mois contre le plafond de 20 % de la durée légale (art. 31),
    # ramené au mois : 8 h par semaine x 52 / 12.
    from . import rules
    h = rules.payroll()["hours"]
    cap_month = h["legal_week"] * h["overtime_cap_fraction"] * 52 / 12
    for e in people:
        ot = getattr(e, "overtime_hours_month", 0) or 0
        if ot > cap_month and e.emp_id not in seen:
            seen.add(e.emp_id)
            issues.insert(0, f"{e.name} : {ot:.0f} h sup. ce mois, au-delà du plafond "
                             f"de {cap_month:.0f} h (loi 90-11, art. 31)")
    if pay.empty:
        return [], "aucun bulletin à calculer"
    net = float(pay["net"].sum()) if "net" in pay else 0.0
    month = _MONTHS_FR[as_of.month - 1]
    found = (f"{len(issues)} point(s) à corriger : " + " ; ".join(issues[:3])
             + ("…" if len(issues) > 3 else "")) if issues else \
        "Aucun écart avec le SNMG, la CNAS ou le barème IRG."
    return [Action(
        key=f"pay:{as_of:%Y-%m}", agent="Paie",
        title=(f"Paie {'d' + chr(39) if month[0] in 'aeiouéèâ' else 'de '}{month} prête : "
               f"{len(pay)} salariés, net total "
               + f"{net:,.0f}".replace(",", " ")
               + f" DZD, {len(issues)} point(s) à vérifier"),
        detail=f"{len(pay)} bulletins recalculés : brut, CNAS, IRG, net. {found}",
        decision="Bulletins publiés, fichier de virement et écritures générés.",
        urgency=1 if issues else 2, minutes=MANUAL_MINUTES["payroll"],
        page="app_pages/payroll_view.py",
        law="SNMG (décret 26-01), CNAS, IRG barème art. 104, heures sup. art. 31",
        payload={"issues": issues},
    )], f"{len(pay)} bulletins recalculés, {len(issues)} écarts de paie"


def _draft_figure(o, people) -> str:
    """Le montant du brouillon préparé pour cette échéance, s'il se calcule."""
    from . import filings
    parts = o.key.split("_")
    n = lambda v: f"{v:,.0f}".replace(",", " ")  # noqa: E731
    try:
        if o.key.startswith("g50_"):
            d = filings.g50_draft(people, int(parts[1]), int(parts[2]))
            return f" Brouillon prêt : IRG retenu {n(d['irg_total'])} DZD sur {d['employees']} salariés."
        if o.key.startswith("cnas_mensuel_"):
            d = filings.cnas_draft(people, int(parts[2]), int(parts[3]))
            return (f" Brouillon prêt : {n(d['total_due'])} DZD à verser "
                    f"(patronal {n(d['employer_total'])}, salarial {n(d['employee_total'])}).")
        if o.key.startswith("das_"):
            d = filings.das_draft(people, int(parts[1]))
            return f" Brouillon prêt : {d['employees']} lignes salariés."
    except (ValueError, IndexError):
        pass
    return ""


def _deadlines_agent(headcount, as_of, people=()) -> tuple[list, str]:
    items = dl.upcoming(as_of, headcount=headcount, horizon_days=45)
    out = []
    for o in items:
        st = o.status(as_of)
        if st not in ("en_retard", "urgent", "a_venir"):
            continue
        days = o.days_left(as_of)
        when = ("en retard, à régulariser" if days < 0 else
                "à déposer aujourd'hui" if days == 0 else f"à déposer dans {days} j")
        out.append(Action(
            key=f"dl:{o.key}:{o.due.isoformat()}", agent="Déclarations",
            title=f"{o.label} · {o.body} : {when}",
            detail=(f"{o.period}. {o.what}"
                    + (_draft_figure(o, people).replace(",", "\u202f") if people else "")),
            decision=f"Brouillon validé et transmis au comptable, qui dépose sur "
                     f"{o.portal}. Rappel J-3 dans l'agenda. L'agent ne dépose rien.",
            urgency=0 if st in ("en_retard", "urgent") else 2,
            minutes=MANUAL_MINUTES["deadline"],
            page="app_pages/deadlines_view.py", law=o.source,
            payload={"penalty": o.penalty},
        ))
    return out, f"{len(items)} échéances CNAS, G50 et DAS calculées sur 45 jours"


def _compliance_agent(people, as_of) -> tuple[list, str]:
    alerts = compliance.scan(people=people, as_of=as_of)
    out = []
    for i, a in enumerate(alerts):
        if a.severity == "info":
            continue
        out.append(Action(
            key=f"comp:{a.category}:{a.message[:60]}", agent="Conformité",
            title=a.message, detail=a.action, law=a.rule,
            decision="Le dossier est mis en conformité et la pièce archivée.",
            urgency=0 if a.severity == "critical" else 1,
            minutes=MANUAL_MINUTES["compliance"],
            page="app_pages/inspector_sim.py",
        ))
    return out, f"{len(people)} dossiers passés au crible du code du travail"


def _retention_agent(attrition_df, people, records, as_of, top: int = 3) -> tuple[list, str]:
    out = []
    if attrition_df is None or attrition_df.empty:
        return out, "aucun effectif à analyser"
    high = attrition_df[attrition_df["Band"] == "high"].head(top)
    for _, row in high.iterrows():
        plan = retention.plan_for_employee(people, records, row["ID"], as_of)
        if plan is None or plan.best is None or plan.best.net_dzd <= 0:
            continue
        b = plan.best
        out.append(Action(
            key=f"ret:{row['ID']}", agent="Rétention",
            title=f"Garder {row['Name']} : {b.label[0].lower()}{b.label[1:]}",
            detail=(f"Risque de départ {plan.base_risk * 100:.0f}% (cause principale : "
                    f"{plan.top_driver.lower()}). L'action le ramène à "
                    f"{b.new_risk * 100:.0f}% "
                    + (f"pour {b.cost_dzd:,.0f} DZD par an." if b.cost_dzd > 0
                       else "sans coût direct.")),
            decision="Entretien planifié avec le manager, script d'entretien joint.",
            urgency=1, minutes=MANUAL_MINUTES["retention"], stakes_dzd=b.net_dzd,
            page="app_pages/retention_negotiator.py",
            law="Alerte précoce par règles (pas encore entraînée sur vos départs)",
        ))
    return out, (f"{len(attrition_df)} salariés scorés, {int((attrition_df['Band'] == 'high').sum())} "
                 f"à risque élevé")


def _recruiting_agent(role_key: str) -> tuple[list, str]:
    key = role_key if role_key in cv_screen.JOBS else next(iter(cv_screen.JOBS))
    job = cv_screen.JOBS[key]
    ranked = talent.rank_pool(talent.sample_pool(key, n=28), job)
    strong = [s for s in ranked if s.band == "strong"][:3]
    out = []
    if strong:
        names = ", ".join(s.candidate.name for s in strong)
        out.append(Action(
            key=f"rec:{key}:{'|'.join(s.candidate.name for s in strong)}",
            agent="Recrutement",
            title=f"Inviter {len(strong)} candidats en entretien ({job.title})",
            detail=(f"{len(ranked)} candidatures lues et classées. Retenus : {names}. "
                    f"Chaque classement est explicable dans le vivier."),
            decision="Invitations envoyées avec trois créneaux proposés.",
            urgency=2, minutes=MANUAL_MINUTES["shortlist"],
            page="app_pages/talent_pool.py",
            law="Score par règles explicables : formation, expérience, langues, permis",
        ))
    return out, f"{len(ranked)} CV lus et classés pour le poste {job.title}"


def _anem_agent(role_title: str, filed_on: _dt.date, as_of: _dt.date) -> tuple[list, str]:
    """La fenêtre ANEM de l'offre ouverte : le compte à rebours, et la suite."""
    used = working_days_between(filed_on, as_of)
    left = ANEM_WINDOW_DAYS - used
    law = "Loi 04-19 modifiée par la loi 20-03 (délai de 5 jours ouvrés)"
    if left > 0:
        act = Action(
            key=f"anem:{filed_on.isoformat()}:{used}", agent="Recrutement",
            title=(f"Offre {role_title} à l'ANEM : jour {used} sur {ANEM_WINDOW_DAYS}, "
                   f"{left} jour(s) ouvré(s) restant(s)"),
            detail=(f"Offre déposée le {filed_on:%d/%m}. Chaque candidat orienté par "
                    "l'agence est contacté et son résultat noté pour le compte rendu "
                    "nominatif."),
            decision="Compte rendu par candidat envoyé à l'ANEM.",
            urgency=1 if left <= 1 else 2, minutes=MANUAL_MINUTES["anem"],
            page="app_pages/job_post_view.py", law=law)
    else:
        act = Action(
            key=f"anem:{filed_on.isoformat()}:open", agent="Recrutement",
            title=f"Fenêtre ANEM close pour {role_title} : recrutement direct autorisé",
            detail="Cinq jours ouvrés écoulés sans placement. Le vivier interne et "
                   "les autres canaux peuvent être ouverts.",
            decision="Recrutement direct ouvert, l'ANEM sera informée de l'embauche.",
            urgency=1, minutes=MANUAL_MINUTES["anem"],
            page="app_pages/sourcing_view.py", law=law)
    return [act], (f"offre {role_title} suivie à l'ANEM, jour "
                   f"{min(used, ANEM_WINDOW_DAYS)} sur {ANEM_WINDOW_DAYS}")


def _affiliation_agent(people, as_of) -> tuple[list, str]:
    """Chaque nouvel embauché doit être affilié à la CNAS sous dix jours."""
    out = []
    for e in people:
        age = (as_of - e.hire_date).days
        if 0 <= age <= CNAS_AFFILIATION_DAYS:
            left = CNAS_AFFILIATION_DAYS - age
            out.append(Action(
                key=f"aff:{e.emp_id}", agent="Déclarations",
                title=f"Affiliation CNAS de {e.name} : {left} jour(s) restant(s)",
                detail=(f"Embauché le {e.hire_date:%d/%m}. Formulaire, contrat et "
                        f"copie de la pièce d'identité rassemblés."),
                decision="Dossier d'affiliation prêt à déposer sur le portail CNAS.",
                urgency=0 if left <= 3 else 1, minutes=MANUAL_MINUTES["affiliation"],
                page="app_pages/people.py",
                law="Affiliation CNAS sous 10 jours suivant l'embauche"))
    return out, f"{len(out)} nouvel(s) embauché(s) à affilier"


def _tickets_agent(tickets: list) -> tuple[list, str]:
    out = []
    for t in tickets:
        if not t.get("needs_signature"):
            continue
        out.append(Action(
            key=f"tk:{t['id']}", agent="Guichet",
            title=(f"{t['label']} pour {t['emp_name']} : prête à signer"
                   if t.get("document") else f"{t['label']} de {t['emp_name']}"),
            detail=f"Demandée au guichet : « {t['text']} ». Rédigée sur le dossier du salarié.",
            decision=t.get("decision", "Document signé et remis au salarié."),
            urgency=2, minutes=MANUAL_MINUTES["ticket"],
            # Un document signé au nom de l'entreprise a sa propre carte.
            auto=False, page="app_pages/self_service.py",
            law="Faits du dossier salarié", payload={"ticket": t["id"]},
        ))
    answered = sum(1 for t in tickets if not t.get("needs_signature"))
    return out, f"{len(tickets)} demandes de salariés reçues, {answered} répondues seules"


def run(*, people: list, records: list, requests: list, attrition_df: pd.DataFrame,
        forecast: Optional[pd.DataFrame], headcount: int, role_key: str,
        tickets: Optional[list] = None, as_of: Optional[_dt.date] = None,
        anem_filed: Optional[_dt.date] = None, open_role_title: str = "") -> Run:
    """Faire passer chaque agent, dans l'ordre où un responsable le ferait."""
    as_of = as_of or _dt.date.today()
    steps = [
        ("Présence", lambda: _requests_agent(requests, people, forecast, as_of)),
        ("Paie", lambda: _payroll_agent(people, records, as_of)),
        ("Déclarations", lambda: _deadlines_agent(headcount, as_of, people)),
        ("Affiliations", lambda: _affiliation_agent(people, as_of)),
        ("Conformité", lambda: _compliance_agent(people, as_of)),
        ("Rétention", lambda: _retention_agent(attrition_df, people, records, as_of)),
        ("Recrutement", lambda: _recruiting_agent(role_key)),
        ("ANEM", lambda: _anem_agent(open_role_title or "ouverte",
                                     anem_filed or as_of - _dt.timedelta(days=6), as_of)),
        ("Guichet", lambda: _tickets_agent(tickets or [])),
    ]
    actions, log = [], []
    for agent, fn in steps:
        try:
            acts, note = fn()
        except Exception as exc:  # noqa: BLE001 , un agent en panne ne bloque pas les autres
            acts, note = [], f"indisponible ({type(exc).__name__})"
        actions += acts
        log.append((agent, note))
    actions.sort(key=lambda a: (a.urgency, -a.stakes_dzd))
    return Run(actions=actions, log=log)


def totals(actions: list) -> dict:
    return {
        "count": len(actions),
        "minutes": sum(a.minutes for a in actions),
        "stakes": sum(a.stakes_dzd for a in actions),
    }


if __name__ == "__main__":
    from . import attrition, hr
    people = hr.sample_workforce("sorter", 60, "Alger")
    records = attendance.sample_attendance(people)
    r = run(people=people, records=records,
            requests=attendance.sample_requests(people),
            attrition_df=attrition.score_workforce(people, records),
            forecast=None, headcount=60, role_key="sorter",
            tickets=[{"id": "t1", "label": "Attestation de travail",
                      "emp_name": "Test", "text": "attestation",
                      "needs_signature": True}])
    for agent, note in r.log:
        print(f"  {agent:12s} {note}")
    assert r.actions, "l'autopilote doit produire au moins une carte"
    assert all(a.agent in AGENTS for a in r.actions)
    assert {a.key for a in r.actions}.__len__() == len(r.actions), "clés en double"
    batch = [a for a in r.pending({}) if a.auto]
    assert batch, "les demandes conformes doivent pouvoir se signer en lot"
    assert not any(a.agent == "Guichet" for a in batch), "un document signé a sa carte"
    print(f"  {len(r.actions)} cartes, dont {len(batch)} signables en un clic")
    print("  ok")
