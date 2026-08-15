"""
core/talent.py
--------------
Le vivier de candidats : classer des candidatures du plus au moins adapté, et
pouvoir les parcourir.

Ce que ça ajoute par rapport à `core/cv_screen.py`
=================================================
`cv_screen` sait juger **une** candidature contre **un** poste. Ici on raisonne
sur le lot : un vivier de profils, un poste, un classement, et de quoi filtrer.
Le calcul de score reste celui de `cv_screen.score` , il n'y a pas deux barèmes
dans le produit, sinon deux écrans donneraient deux réponses différentes sur le
même candidat.

Le classement est **déterministe et explicable** : chaque candidat porte ses
points forts et ses réserves, et le score se décompose critère par critère. Un
recruteur qui doit justifier un refus peut le faire.

Les profils de démonstration
============================
`sample_pool()` fabrique un vivier plausible (noms, wilayas, formations,
expérience, langues, permis, service national) parce qu'aucun vivier réel de CV
algériens n'est public. **Ces profils sont simulés et l'écran le dit.** En
production, le vivier vient des CV réellement reçus, lus par `cv_screen.extract`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import numpy as np
import pandas as pd

from . import cv_screen, hr

# Formations réellement rencontrées sur un CV algérien, du plus court au plus long.
_EDUCATIONS = [
    ("sans", "Niveau secondaire, sans diplôme"),
    ("cap", "CAP / CFPA"),
    ("bac", "Baccalauréat"),
    ("bts", "BTS / Technicien supérieur"),
    ("licence", "Licence (LMD)"),
    ("master", "Master (LMD)"),
    ("ingenieur", "Ingénieur d'État"),
]

_ESTABLISHMENTS = [
    "CFPA Rouiba", "CFPA Blida", "INSFP Alger", "INSFP Oran",
    "Université d'Alger 1", "USTHB", "Université de Blida 1",
    "Université d'Oran 2", "ESC Alger", "ENSM Koléa",
    "Université de Constantine 2", "Université de Sétif 1",
]

_POSITIONS = {
    "sorter": ["Agent de tri", "Magasinier", "Préparateur de commandes",
               "Manutentionnaire", "Agent de quai"],
    "courier": ["Chauffeur-livreur", "Coursier", "Livreur deux-roues",
                "Chauffeur poids lourd"],
    "checkin_agent": ["Agent d'escale", "Agent d'enregistrement",
                      "Agent de comptoir", "Hôtesse d'accueil"],
    "front_desk": ["Réceptionniste", "Agent de réservation",
                   "Chargé d'accueil", "Night auditor"],
}

_SKILL_POOL = {
    "sorter": ["logistique", "manutention", "scan", "stock", "inventaire",
               "cariste", "gestion d'entrepot"],
    "courier": ["livraison", "conduite", "relation client", "encaissement",
                "gps", "deux-roues"],
    "checkin_agent": ["accueil", "aeroport", "billetterie", "relation client",
                      "amadeus", "gestion de file"],
    "front_desk": ["accueil", "reservation", "hotellerie", "relation client",
                   "opera pms", "encaissement"],
}

_SN_STATES = ["degage", "degage", "degage", "exempte", "en cours", "inconnu"]

# Le verdict, en français. Défini ici et pas emprunté à un autre module : c'est
# cette table qui alimente les filtres de l'écran, donc elle doit vivre à côté
# du tableau qu'elle remplit.
BANDS_FR = {"strong": "Fort", "possible": "Possible", "weak": "Faible"}

_WILAYA_MIX = ["Alger", "Alger", "Alger", "Blida", "Boumerdes", "Tipaza",
               "Oran", "Constantine", "Setif", "Annaba", "Bejaia", "Tizi Ouzou"]


def sample_pool(role_key: str = "sorter", n: int = 28, seed: int = 11) -> list:
    """
    Un vivier de candidatures plausible pour la démonstration.

    Les profils sont **simulés**. La variété est voulue : quelques très bons
    dossiers, une majorité de dossiers moyens, et des profils faibles ou
    incomplets, parce qu'un vivier réel ressemble à ça et qu'un écran de tri qui
    ne montre que des bons candidats ne prouve rien.
    """
    rng = np.random.default_rng(seed)
    positions = _POSITIONS.get(role_key, _POSITIONS["sorter"])
    skills = _SKILL_POOL.get(role_key, _SKILL_POOL["sorter"])
    out = []
    for i in range(n):
        # Le niveau global du dossier. La loi est volontairement tirée vers le
        # bas (moyenne ~0,38) : une annonce d'agent de tri attire surtout des
        # profils qui ne cochent pas toutes les cases, et un vivier de
        # démonstration où tout le monde est excellent ne prouve rien. C'est ce
        # réglage qui produit un vrai classement, avec des refus motivés.
        tier = float(np.clip(rng.beta(1.6, 2.6), 0, 1))

        edu_idx = int(np.clip(round(tier * 6 + rng.normal(0, .9)),
                              0, len(_EDUCATIONS) - 1))
        edu_key, edu_label = _EDUCATIONS[edu_idx]

        years = float(max(0, round(tier * 8 - .8 + rng.normal(0, 1.1), 1)))

        langs = ["arabe"]
        if rng.random() < .30 + tier * .55:
            langs.append("francais")
        if rng.random() < .05 + tier * .55:
            langs.append("anglais")
        if rng.random() < .35:
            langs.append("tamazight")

        k = int(np.clip(round(tier * len(skills) * .8), 0, len(skills)))
        picked = list(rng.choice(skills, size=k, replace=False)) if k else []

        held = int(np.clip(round(years / 2.5), 0, 3))
        out.append(cv_screen.Candidate(
            name=f"{hr._FIRST[(i * 7 + 3) % len(hr._FIRST)]} "
                 f"{hr._LAST[(i * 5 + 1) % len(hr._LAST)]}",
            wilaya=_WILAYA_MIX[i % len(_WILAYA_MIX)],
            education=edu_key,
            education_raw=edu_label,
            establishment=str(rng.choice(_ESTABLISHMENTS)),
            experience_years=years,
            positions=[str(p) for p in
                       (rng.choice(positions, size=max(held, 1), replace=False)
                        if held else rng.choice(positions, size=1))],
            skills=[str(s) for s in picked],
            languages=langs,
            driving_licence=bool(rng.random() < .18 + tier * .5),
            service_national=str(rng.choice(_SN_STATES)),
            mobility="mobile" if rng.random() < .45 else "sur place",
        ))
    return out


def rank_pool(candidates: list, job: cv_screen.Job) -> list:
    """Le vivier trié du plus au moins adapté, avec le détail de chaque score."""
    scored = [cv_screen.score(c, job, method="rules") for c in candidates]
    return sorted(scored, key=lambda s: (-s.score, s.candidate.name))


def pool_frame(screenings: list) -> pd.DataFrame:
    """
    Le classement en tableau, une ligne par candidat.

    Colonnes pensées pour être filtrées et triées telles quelles par l'écran :
    tout ce sur quoi un recruteur veut restreindre est une colonne.
    """
    rows = []
    for rank, s in enumerate(screenings, start=1):
        c = s.candidate
        rows.append({
            "Rang": rank,
            "Nom": c.name,
            "Score": s.score,
            "Verdict": BANDS_FR.get(s.band, s.band),
            "Wilaya": c.wilaya,
            "Formation": c.education_raw or c.education,
            "Niveau": c.education,
            "Expérience": c.experience_years,
            "Langues": ", ".join(c.languages),
            "Permis": bool(c.driving_licence),
            "Service national": c.service_national,
            "Mobilité": c.mobility,
            "Points forts": len(s.pluses),
            "Réserves": len(s.flags),
        })
    return pd.DataFrame(rows)


def score_breakdown(screening) -> pd.DataFrame:
    """
    Le score critère par critère, pour pouvoir justifier un classement.

    On recalcule chaque part avec la même logique que `cv_screen.score`, puis on
    la pondère : c'est ce qui rend le classement défendable devant un candidat
    qui demande pourquoi.
    """
    c, job = screening.candidate, screening.job
    w = job.weight
    need = cv_screen.EDUCATION_RANK.get(job.min_education, 2)
    have = cv_screen.EDUCATION_RANK.get(c.education, 0)

    req = set(job.required_languages)
    missing = req - set(c.languages)

    parts = {
        "Formation": (1.0 if have >= need
                      else max(0.0, have / max(need, 1) * 0.7)),
        "Expérience": (1.0 if job.min_experience_years <= 0 else
                       min(c.experience_years / job.min_experience_years, 1.0)),
        "Langues": 1.0 - (len(missing) / max(len(req), 1)),
        "Compétences": (min(len(set(c.skills) & set(job.skills)) /
                            len(job.skills), 1.0) if job.skills else 1.0),
        "Permis": (1.0 if not job.needs_driving_licence
                   else (1.0 if c.driving_licence else 0.0)),
        "Service national": _sn_part(c, job),
    }
    keys = {"Formation": "education", "Expérience": "experience",
            "Langues": "languages", "Compétences": "skills",
            "Permis": "licence", "Service national": "service_national"}
    total_w = sum(w.values())
    rows = []
    for label, part in parts.items():
        weight = w.get(keys[label], 0)
        rows.append({
            "Critère": label,
            "Atteint": round(part * 100),
            "Poids": round(weight / total_w * 100),
            "Apport": round(part * weight / total_w * 100, 1),
        })
    return pd.DataFrame(rows)


def _sn_part(c, job) -> float:
    if not job.needs_service_national_cleared:
        return 1.0
    if c.service_national in ("degage", "exempte", "n/a"):
        return 1.0
    return 0.4 if c.service_national == "en cours" else 0.5


def shortlist_note(screenings: list, job: cv_screen.Job, keep: int = 5) -> str:
    """Une phrase de synthèse pour le haut de l'écran, sans jargon."""
    if not screenings:
        return "Aucune candidature dans le vivier."
    strong = sum(1 for s in screenings if s.band == "strong")
    possible = sum(1 for s in screenings if s.band == "possible")
    top = screenings[0]
    return (f"{len(screenings)} candidatures pour « {job.title} » : "
            f"{strong} dossiers solides, {possible} à voir, "
            f"{len(screenings) - strong - possible} hors cible. "
            f"Le mieux placé est {top.candidate.name} ({top.score}%).")


if __name__ == "__main__":
    print("Vivier de candidats - auto-vérification\n")

    job = cv_screen.JOBS["sorter"]
    pool = sample_pool("sorter", n=28)
    ranked = rank_pool(pool, job)

    print(f"{'OK ' if len(pool) == 28 else 'ECHEC'} vivier généré : "
          f"{len(pool)} profils")

    scores = [s.score for s in ranked]
    print(f"{'OK ' if scores == sorted(scores, reverse=True) else 'ECHEC'} "
          f"classement décroissant : {scores[0]}% -> {scores[-1]}%")

    bands = {b: sum(1 for s in ranked if s.band == b)
             for b in ("strong", "possible", "weak")}
    spread = all(v > 0 for v in bands.values())
    print(f"{'OK ' if spread else 'ECHEC'} les trois verdicts sont représentés : "
          f"{bands}")

    df = pool_frame(ranked)
    print(f"{'OK ' if len(df) == len(ranked) else 'ECHEC'} tableau : "
          f"{len(df)} lignes, {len(df.columns)} colonnes")

    # Le verdict doit sortir en français : c'est cette colonne que l'écran
    # filtre, et une valeur anglaise ne correspondrait à aucune case cochée,
    # donc le classement s'afficherait vide sans lever d'erreur.
    labels = set(df["Verdict"].unique())
    ok = labels <= set(BANDS_FR.values())
    print(f"{'OK ' if ok else 'ECHEC'} verdicts affichables : {sorted(labels)}")

    bd = score_breakdown(ranked[0])
    total = bd["Apport"].sum()
    close = abs(total - ranked[0].score) <= 1.5
    print(f"{'OK ' if close else 'ECHEC'} décomposition du score : somme des "
          f"apports {total:.1f} vs score {ranked[0].score}")

    # Le même candidat doit obtenir le même score partout dans le produit.
    direct = cv_screen.score(ranked[0].candidate, job)
    print(f"{'OK ' if direct.score == ranked[0].score else 'ECHEC'} un seul "
          f"barème : cv_screen donne {direct.score}%, le vivier "
          f"{ranked[0].score}%")

    print("\n" + shortlist_note(ranked, job))
    print("\nTop 5 :")
    for s in ranked[:5]:
        c = s.candidate
        print(f"  {s.score:3d}%  {c.name:22s} {c.education:10s} "
              f"{c.experience_years:4.1f} ans  {c.wilaya}")
