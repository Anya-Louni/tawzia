"""
core/deadlines_dz.py
--------------------
Le calendrier des obligations de l'employeur algérien : ce qui doit être
déclaré, à qui, avant quand, et ce que coûte l'oubli.

Le problème que ça règle
========================
Une PME algérienne ne perd pas de l'argent parce qu'elle calcule mal une paie.
Elle en perd parce qu'une déclaration part en retard : la cotisation reste due,
et la majoration de retard s'y ajoute. Le comptable connaît ces échéances, mais
il les porte de tête, et personne dans l'entreprise ne sait où on en est avant
le rappel de l'agence.

Ce module transforme donc les obligations récurrentes en dates réelles, calées
sur l'effectif du site (l'effectif décide de la périodicité CNAS), avec le
portail où la démarche se fait vraiment.

Honnêteté
=========
Les périodicités et les dates butoirs ci-dessous sont sourcées et datées, avec
le lien du portail officiel. Ce qui n'est PAS certain est marqué comme tel dans
`confidence` :

  * ``sourcee``     — vérifié auprès d'une source nommée, citée dans `source`.
  * ``a_confirmer`` — la règle existe, mais son montant ou sa date varie selon
                      les lois de finances et les usages d'agence. La plateforme
                      le dit au lieu de faire semblant.

Aucun montant de pénalité n'est affirmé comme un barème : plusieurs lois de
finances récentes ont rééchelonné ou supprimé des majorations, donc le module
donne l'ordre de grandeur et renvoie à l'agence. C'est la seule position
défendable devant un comptable.

Ce module ne remplace pas un comptable : il l'empêche d'oublier.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import labour_dz, rules

# Portails officiels où la démarche se fait réellement.
PORTAL_CNAS = "https://teledeclaration.cnas.dz"
PORTAL_CNAS_MAIN = "https://www.cnas.dz"
PORTAL_DGI = "https://jibayatic.dz"
PORTAL_CASNOS = "https://www.casnos.com.dz"

# Au-delà de ce seuil d'effectif, la déclaration des cotisations CNAS est
# mensuelle ; en dessous elle est trimestrielle.
CNAS_MONTHLY_THRESHOLD = rules.payroll()["filings"]["cnas_monthly_from_headcount"]

# Délai de dépôt et de paiement après la fin de la période cotisée.
CNAS_FILING_DAYS = rules.payroll()["filings"]["cnas_days_after_period"]  # [à vérifier]

# Jour limite de dépôt de la déclaration mensuelle G50 (mois suivant).
G50_DAY = rules.payroll()["filings"]["g50_day"]

# Date butoir de la déclaration annuelle des salaires (DAS) : 31 janvier.
DAS_MONTH, DAS_DAY = rules.payroll()["filings"]["das_month"], rules.payroll()["filings"]["das_day"]

_SEVERITY_ORDER = {"en_retard": 0, "urgent": 1, "a_venir": 2, "plus_tard": 3}

STATUS_FR = {
    "en_retard": "En retard",
    "urgent": "Urgent",
    "a_venir": "À préparer",
    "plus_tard": "Plus tard",
}


@dataclass
class Obligation:
    """Une échéance datée, avec son portail et sa provenance."""
    key: str
    label: str
    body: str                    # l'organisme destinataire
    due: _dt.date
    period: str                  # la période couverte, en clair
    what: str                    # ce qu'il faut faire, en une phrase
    portal: str
    penalty: str
    source: str
    confidence: str = "sourcee"  # sourcee | a_confirmer
    as_of: str = ""

    def days_left(self, as_of: _dt.date) -> int:
        return (self.due - as_of).days

    def status(self, as_of: _dt.date) -> str:
        d = self.days_left(as_of)
        if d < 0:
            return "en_retard"
        if d <= 7:
            return "urgent"
        if d <= 30:
            return "a_venir"
        return "plus_tard"


def _eom(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, calendar.monthrange(year, month)[1])


def _add_months(d: _dt.date, n: int) -> _dt.date:
    """Décale de n mois en gardant le jour, borné à la fin du mois d'arrivée."""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return _dt.date(year, month, day)


def _quarter_end(d: _dt.date) -> _dt.date:
    q_last_month = ((d.month - 1) // 3) * 3 + 3
    return _eom(d.year, q_last_month)


# ---------------------------------------------------------------------------
# Les obligations récurrentes
# ---------------------------------------------------------------------------

def _cnas_contributions(as_of: _dt.date, headcount: int,
                        horizon_days: int) -> list:
    """
    Déclaration et paiement des cotisations CNAS.

    Périodicité selon l'effectif : mensuelle à partir de 10 salariés,
    trimestrielle en dessous. Dépôt et paiement dans le délai fixé par la configuration suivant la
    fin de la période.
    """
    monthly = headcount >= CNAS_MONTHLY_THRESHOLD
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)

    if monthly:
        # On part du mois précédent : son échéance peut encore être devant nous.
        cursor = _eom(*_add_months(as_of.replace(day=1), -1).timetuple()[:2])
        while cursor <= limit:
            due = cursor + _dt.timedelta(days=CNAS_FILING_DAYS)
            if due >= as_of - _dt.timedelta(days=45) and due <= limit:
                out.append(Obligation(
                    key=f"cnas_mensuel_{cursor:%Y_%m}",
                    label="Cotisations CNAS du mois",
                    body="CNAS",
                    due=due,
                    period=f"mois de {_MONTHS_FR[cursor.month - 1]} {cursor.year}",
                    what="Déclarer et payer les cotisations sociales du mois "
                         f"(part salariale {labour_dz.CNAS_EMPLOYEE:.0%} + part patronale {labour_dz.CNAS_EMPLOYER:.1%}).",
                    portal=PORTAL_CNAS,
                    penalty="Majorations de retard sur les cotisations non "
                            "payées. Le taux a changé plusieurs fois : faites "
                            "confirmer le montant dû par votre agence.",
                    source="CNAS, périodicité mensuelle au-delà de 10 salariés, "
                           f"dépôt et paiement dans les {CNAS_FILING_DAYS} jours [à vérifier]",
                    confidence="a_confirmer",
                    as_of="2026",
                ))
            cursor = _eom(*_add_months(cursor.replace(day=1), 1).timetuple()[:2])
    else:
        q_end = _quarter_end(_add_months(as_of, -3))
        while q_end <= limit:
            due = q_end + _dt.timedelta(days=CNAS_FILING_DAYS)
            if due >= as_of - _dt.timedelta(days=45) and due <= limit:
                out.append(Obligation(
                    key=f"cnas_trimestre_{q_end:%Y_%m}",
                    label="Cotisations CNAS du trimestre",
                    body="CNAS",
                    due=due,
                    period=f"trimestre clos le {q_end:%d/%m/%Y}",
                    what="Déclarer et payer les cotisations sociales du "
                         f"trimestre (part salariale {labour_dz.CNAS_EMPLOYEE:.0%} + part patronale {labour_dz.CNAS_EMPLOYER:.1%}).",
                    portal=PORTAL_CNAS,
                    penalty="Majorations de retard sur les cotisations non "
                            "payées. Faites confirmer le montant dû par votre "
                            "agence.",
                    source="CNAS, périodicité trimestrielle en dessous de 10 "
                           f"salariés, dépôt et paiement dans les {CNAS_FILING_DAYS} jours [à vérifier]",
                    confidence="a_confirmer",
                    as_of="2026",
                ))
            q_end = _quarter_end(_add_months(q_end, 3))
    return out


def _g50(as_of: _dt.date, horizon_days: int) -> list:
    """
    Déclaration mensuelle G50, à déposer entre le 1er et le 20 du mois suivant.

    Elle porte l'IRG retenu sur les salaires et la TVA. La TAP a été supprimée
    par la loi de finances 2024 : elle n'y figure plus.
    """
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)
    month = _add_months(as_of.replace(day=1), -1)
    while True:
        due = _dt.date(*_add_months(month, 1).timetuple()[:2], G50_DAY)
        if due > limit:
            break
        if due >= as_of - _dt.timedelta(days=45):
            out.append(Obligation(
                key=f"g50_{month:%Y_%m}",
                label="Déclaration mensuelle G50",
                body="DGI (impôts)",
                due=due,
                period=f"mois de {_MONTHS_FR[month.month - 1]} {month.year}",
                what="Déposer la G50 : IRG retenu sur les salaires du mois et "
                     "TVA. Dépôt du 1er au 20 du mois suivant.",
                portal=PORTAL_DGI,
                penalty="Pénalités de retard sur les droits déclarés hors "
                        "délai. La DGI proroge parfois l'échéance : vérifiez "
                        "les avis en cours sur Jibaya'tic.",
                source="DGI, déclaration série G n°50, dépôt avant le 20 du "
                       "mois suivant (Jibaya'tic)",
                confidence="sourcee",
                as_of="2026",
            ))
        month = _add_months(month, 1)
    return out


def _das(as_of: _dt.date, horizon_days: int) -> list:
    """Déclaration annuelle des salaires et des salariés, avant le 31 janvier."""
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)
    for year in (as_of.year, as_of.year + 1):
        due = _dt.date(year, DAS_MONTH, DAS_DAY)
        if due < as_of - _dt.timedelta(days=45) or due > limit:
            continue
        out.append(Obligation(
            key=f"das_{year}",
            label="Déclaration annuelle des salaires (DAS)",
            body="CNAS",
            due=due,
            period=f"année {year - 1} (du 1er janvier au 31 décembre)",
            what="Déposer la DAS nominative : chaque salarié, son salaire et "
                 "ses cotisations de l'année écoulée.",
            portal=PORTAL_CNAS,
            penalty="La CNAS relance les employeurs défaillants ; le défaut de "
                    "dépôt est sanctionné. Déposez avant le 31 janvier.",
            source="CNAS, dépôt avant le 31 janvier sur teledeclaration.cnas.dz "
                   "(rappels APS et Radio Algérienne, janvier)",
            confidence="sourcee",
            as_of="2026",
        ))
    return out


_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")

# Obligations ponctuelles, déclenchées par un événement et non par le calendrier.
EVENT_DRIVEN = [
    {
        "label": "Affiliation d'un nouveau salarié",
        "body": "CNAS",
        "trigger": "À chaque embauche",
        "what": "Déclarer le salarié à la CNAS dès son entrée en poste, avant "
                "le premier bulletin.",
        "portal": PORTAL_CNAS,
        "note": "Le délai légal est court et se compte en jours. Faites "
                "confirmer le nombre exact de jours par votre agence CNAS.",
        "confidence": "a_confirmer",
    },
    {
        "label": "Déclaration d'activité de l'employeur",
        "body": "CNAS",
        "trigger": "À l'ouverture de l'activité",
        "what": "Déclarer l'existence de l'entreprise comme employeur.",
        "portal": PORTAL_CNAS_MAIN,
        "note": "Le défaut de déclaration d'activité est sanctionné par une "
                "amende, majorée par mois de retard. Montant à confirmer "
                "auprès de la CNAS.",
        "confidence": "a_confirmer",
    },
]


def upcoming(as_of: Optional[_dt.date] = None, headcount: int = 80,
             horizon_days: int = 120) -> list:
    """
    Toutes les échéances qui tombent dans la fenêtre, la plus urgente d'abord.

    `headcount` décide de la périodicité CNAS : c'est le seul paramètre qui
    change la liste, et c'est voulu, parce que c'est la seule règle qui dépend
    vraiment de l'entreprise.
    """
    as_of = as_of or _dt.date.today()
    items = (_cnas_contributions(as_of, headcount, horizon_days)
             + _g50(as_of, horizon_days)
             + _das(as_of, horizon_days))
    return sorted(items, key=lambda o: (_SEVERITY_ORDER[o.status(as_of)], o.due))


def frame(as_of: Optional[_dt.date] = None, headcount: int = 80,
          horizon_days: int = 120) -> pd.DataFrame:
    """Les mêmes échéances, en tableau, pour l'affichage et l'export."""
    as_of = as_of or _dt.date.today()
    rows = []
    for o in upcoming(as_of, headcount, horizon_days):
        rows.append({
            "Échéance": o.due,
            "Jours restants": o.days_left(as_of),
            "Statut": STATUS_FR[o.status(as_of)],
            "Obligation": o.label,
            "Organisme": o.body,
            "Période couverte": o.period,
            "À faire": o.what,
            "Portail": o.portal,
            "Retard": o.penalty,
            "Source": o.source,
            "Fiabilité": ("Sourcé" if o.confidence == "sourcee"
                          else "À confirmer"),
        })
    return pd.DataFrame(rows)


def next_critical(as_of: Optional[_dt.date] = None, headcount: int = 80) -> Optional[Obligation]:
    """La prochaine échéance qui demande une action, pour l'alerte du tableau de bord."""
    as_of = as_of or _dt.date.today()
    for o in upcoming(as_of, headcount, horizon_days=60):
        if o.status(as_of) in ("en_retard", "urgent", "a_venir"):
            return o
    return None


def counts(as_of: Optional[_dt.date] = None, headcount: int = 80,
           horizon_days: int = 120) -> dict:
    """Combien d'échéances par statut : de quoi tenir une pastille d'alerte."""
    as_of = as_of or _dt.date.today()
    out = {k: 0 for k in STATUS_FR}
    for o in upcoming(as_of, headcount, horizon_days):
        out[o.status(as_of)] += 1
    return out


def to_ics(obligations: list, reminder_days: int = 7) -> str:
    """
    Les échéances en fichier .ics, importable dans n'importe quel agenda.

    C'est la forme la plus utile pour un comptable : il ne va pas ouvrir la
    plateforme chaque matin, mais son agenda le prévient tout seul. Chaque
    événement porte un rappel `reminder_days` jours avant, et le lien du portail
    dans la description.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Tawzia//Echeances employeur//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Tawzia , échéances employeur",
    ]
    for o in obligations:
        # Un événement d'une journée : DTEND est exclusif, d'où le +1 jour.
        start = o.due.strftime("%Y%m%d")
        end = (o.due + _dt.timedelta(days=1)).strftime("%Y%m%d")
        desc = (f"{o.what} Organisme : {o.body}. Période : {o.period}. "
                f"Portail : {o.portal}").replace(",", "\\,").replace(";", "\\;")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{o.key}@tawzia",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{o.label} ({o.body})",
            f"DESCRIPTION:{desc}",
            f"URL:{o.portal}",
            "BEGIN:VALARM",
            f"TRIGGER:-P{int(reminder_days)}D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{o.label} dans {int(reminder_days)} jours",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


if __name__ == "__main__":
    print("Échéances employeur - auto-vérification\n")

    today = _dt.date.today()

    # 1. La périodicité CNAS suit bien l'effectif.
    small = [o for o in upcoming(today, headcount=6) if o.body == "CNAS"
             and "Cotisations" in o.label]
    big = [o for o in upcoming(today, headcount=80) if o.body == "CNAS"
           and "Cotisations" in o.label]
    ok = all("trimestre" in o.label for o in small) and \
        all("mois" in o.label for o in big)
    print(f"{'OK ' if ok else 'ECHEC'} 6 salariés -> trimestriel "
          f"({len(small)} échéances), 80 -> mensuel ({len(big)})")

    # 2. La G50 tombe toujours le 20.
    g50 = [o for o in upcoming(today, 80, 200) if o.key.startswith("g50")]
    ok = g50 and all(o.due.day == G50_DAY for o in g50)
    print(f"{'OK ' if ok else 'ECHEC'} G50 : {len(g50)} échéances, toutes le "
          f"{G50_DAY} du mois")

    # 3. La DAS tombe toujours le 31 janvier.
    das = [o for o in upcoming(today, 80, 400) if o.key.startswith("das")]
    ok = all(o.due.month == 1 and o.due.day == 31 for o in das)
    print(f"{'OK ' if ok else 'ECHEC'} DAS : {len(das)} échéance(s), "
          f"{'31 janvier' if ok else 'date inattendue'}")

    # 4. Le tri met bien l'urgent devant.
    ups = upcoming(today, 80, 120)
    order = [_SEVERITY_ORDER[o.status(today)] for o in ups]
    print(f"{'OK ' if order == sorted(order) else 'ECHEC'} tri : "
          f"le plus urgent en premier")

    # 5. Chaque obligation porte un portail et une source.
    ok = all(o.portal.startswith("https://") and o.source for o in ups)
    print(f"{'OK ' if ok else 'ECHEC'} chaque échéance a un portail et une source")

    # 6. L'export agenda est bien formé et contient chaque échéance.
    ics = to_ics(ups)
    ok = (ics.startswith("BEGIN:VCALENDAR")
          and ics.rstrip().endswith("END:VCALENDAR")
          and ics.count("BEGIN:VEVENT") == len(ups)
          and ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT"))
    print(f"{'OK ' if ok else 'ECHEC'} export agenda : "
          f"{ics.count('BEGIN:VEVENT')} événements pour {len(ups)} échéances")

    print(f"\nProchaine action : ", end="")
    nxt = next_critical(today, 80)
    if nxt:
        print(f"{nxt.label} le {nxt.due:%d/%m/%Y} "
              f"(dans {nxt.days_left(today)} jours) -> {nxt.portal}")
    else:
        print("aucune dans les 60 jours")

    print(f"\n{len(ups)} échéances sur 120 jours :")
    for o in ups[:8]:
        print(f"  {o.due:%d/%m/%Y}  {STATUS_FR[o.status(today)]:12s} "
              f"{o.label} ({o.body})")
