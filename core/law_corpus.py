"""
core/law_corpus.py
------------------
Le petit corpus juridique que l'assistant et le serveur MCP citent.

Ce sont des **résumés**, pas le texte officiel : chaque entrée dit ce que
l'article prévoit, en une ou deux phrases, et renvoie au texte. Le corpus ne
couvre que les articles que la plateforme applique. Une question qui n'y trouve
pas de réponse part au service RH : le système ne devine jamais un droit.
"""

from __future__ import annotations

import unicodedata

WIPO_90_11 = "https://www.wipo.int/wipolex/edocs/lexdocs/laws/fr/dz/dz039fr.html"
JO_25_11 = "https://droit.mjustice.gov.dz/sites/default/files/loi_25-11-fr.pdf"

ARTICLES = [
    ("90-11/12", "Loi 90-11", "art. 12", "Contrat à durée déterminée",
     "Le CDD n'est permis que dans des cas listés : remplacement d'un titulaire, "
     "surcroît temporaire ou saisonnier, travaux temporaires par nature.", WIPO_90_11),
    ("90-11/18", "Loi 90-11", "art. 18", "Période d'essai",
     "La période d'essai a une durée maximale, plus longue pour les postes de haute "
     "qualification. La plateforme applique les valeurs de sa configuration "
     "(10 et 12 mois) [à vérifier sur le texte].", WIPO_90_11),
    ("90-11/20", "Loi 90-11", "art. 20", "Rupture pendant l'essai",
     "Pendant l'essai, chaque partie peut rompre sans préavis ni indemnité.", WIPO_90_11),
    ("90-11/27", "Loi 90-11", "art. 27", "Travail de nuit",
     "Est travail de nuit celui exécuté entre 21 heures et 5 heures.", WIPO_90_11),
    ("90-11/28", "Loi 90-11", "art. 28", "Nuit et âge",
     "Les travailleurs de moins de 19 ans ne peuvent pas travailler de nuit.", WIPO_90_11),
    ("90-11/29", "Loi 90-11", "art. 29", "Nuit et travailleuses",
     "Le travail de nuit des femmes requiert une dérogation de l'inspecteur du "
     "travail territorialement compétent.", WIPO_90_11),
    ("90-11/31", "Loi 90-11", "art. 31", "Heures supplémentaires",
     "Les heures supplémentaires ne peuvent dépasser 20 % de la durée légale.", WIPO_90_11),
    ("90-11/32", "Loi 90-11", "art. 32", "Majoration",
     "Chaque heure supplémentaire est majorée d'au moins 50 % du salaire horaire normal.",
     WIPO_90_11),
    ("90-11/33", "Loi 90-11", "art. 33", "Repos hebdomadaire",
     "Le travailleur a droit à une journée entière de repos par semaine, en principe "
     "le vendredi.", WIPO_90_11),
    ("90-11/36", "Loi 90-11", "art. 36", "Repos compensateur",
     "Le travail un jour de repos légal ouvre droit à un repos compensateur d'égale durée.",
     WIPO_90_11),
    ("90-11/37", "Loi 90-11", "art. 37", "Déplacement du repos",
     "Le repos hebdomadaire peut être déplacé pour des raisons de production.", WIPO_90_11),
    ("90-11/40", "Loi 90-11", "art. 40", "Année de référence des congés",
     "Le droit au congé se calcule sur l'année du 1er juillet au 30 juin.", WIPO_90_11),
    ("90-11/41", "Loi 90-11", "art. 41", "Durée du congé annuel",
     "Deux jours et demi par mois de travail, dans la limite de 30 jours calendaires par an.",
     WIPO_90_11),
    ("90-11/42", "Loi 90-11", "art. 42", "Congé dans le Sud",
     "Les travailleurs des wilayas du Sud bénéficient d'au moins dix jours supplémentaires.",
     WIPO_90_11),
    ("90-11/54", "Loi 90-11", "art. 54", "Absences spéciales payées",
     "Trois jours ouvrables payés pour certains événements familiaux listés "
     "(mariage, naissance, décès d'un proche).", WIPO_90_11),
    ("90-11/75", "Loi 90-11", "art. 75", "Règlement intérieur",
     "Obligatoire dans les organismes employeurs d'au moins 20 travailleurs.", WIPO_90_11),
    ("97-03", "Ordonnance 97-03", "art. 2", "Durée légale",
     "La durée légale du travail est de 40 heures par semaine.", WIPO_90_11),
    ("20-03", "Loi 04-19 modifiée par la loi 20-03", "", "Offre d'emploi et ANEM",
     "L'employeur dépose ses offres auprès des services de l'emploi ; l'ANEM dispose de "
     "cinq jours ouvrés pour proposer des candidats avant tout recrutement direct.",
     "https://blog.emploitic.com/index.php/delai-de-traitement-de-loffre-demploi-par-lanem-et-organismes-de-recrutement-prives/"),
    ("25-11", "Loi 18-07 modifiée par la loi 25-11", "", "Données personnelles",
     "Les traitements de données des salariés sont tracés (collecte, consultation, "
     "modification, effacement) et les transferts à l'étranger exigent des garanties.",
     JO_25_11),
]

FIELDS = ("id", "text", "article", "title", "summary", "url")


def _plain(s: str) -> str:
    t = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def search(query: str, limit: int = 5) -> list:
    """Les articles dont le titre ou le résumé partage le plus de mots avec la question."""
    words = [w for w in _plain(query).replace("'", " ").split() if len(w) > 2]
    scored = []
    for row in ARTICLES:
        hay = _plain(" ".join(row[1:5]))
        score = sum(hay.count(w) for w in words) + (3 if _plain(row[2]) in _plain(query) and row[2] else 0)
        if score:
            scored.append((score, dict(zip(FIELDS, row))))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


if __name__ == "__main__":
    assert search("travail de nuit des femmes")[0]["article"] in ("art. 29", "art. 27")
    assert search("heures supplémentaires plafond")[0]["article"] == "art. 31"
    assert search("congé dans le sud")[0]["article"] == "art. 42"
    assert search("xyzzy") == []
    print("  corpus juridique : ok")
