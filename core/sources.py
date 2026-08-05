"""
core/sources.py
---------------
A single registry for every externally-sourced number used anywhere in
WorkForce.dz, plus every assumption we make.

Why this exists
===============
The fastest way to lose a jury or an investor is to show a number you can't
defend. This module makes that structurally hard: any figure the app displays
should be pulled from here (or computed from something pulled from here), and
the UI renders the citation next to it.

Three kinds of entry:

  * ``measured``    — published by a named source; we cite it.
  * ``live``        — fetched at runtime from a public API; we cite the API.
  * ``assumption``  — our own modelling choice. Stated plainly as an
                      assumption, with the reasoning, so nobody mistakes it
                      for evidence. These are the numbers a customer would
                      replace with their own during a pilot.

If you add a number to the product, add it here first.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Fact:
    key: str
    label: str
    value: Any
    unit: str
    kind: str  # "measured" | "live" | "assumption"
    source: str
    url: str = ""
    as_of: str = ""
    note: str = ""
    tags: tuple = field(default_factory=tuple)

    @property
    def is_assumption(self) -> bool:
        return self.kind == "assumption"

    def cite(self) -> str:
        """Short inline citation string for the UI."""
        if self.kind == "assumption":
            return f"Hypothèse — {self.note or 'choix de modélisation'}"
        bits = [self.source]
        if self.as_of:
            bits.append(self.as_of)
        return ", ".join(bits)


# ---------------------------------------------------------------------------
# LABOUR & COST — the inputs that decide whether our savings number is real
# ---------------------------------------------------------------------------

_FACTS = [
    Fact(
        key="snmg_monthly_dzd",
        label="SNMG (salaire national minimum garanti)",
        value=24000,
        unit="DZD/mois",
        kind="measured",
        source="Conseil des ministres / APS — SNMG relevé de 20 000 à 24 000 DZD",
        url="https://www.aps.dz/fr/presidence-news/mim6ow3o-augmentation-du-snmg-a-24-000-da-a-partir-de-janvier-2026",
        as_of="en vigueur janvier 2026",
        note="Une hausse de 20% , la plus forte depuis des décennies. Elle "
             "déplace directement chaque ligne de coût de main-d'œuvre de ce "
             "modèle, d'où le fait qu'on s'indexe dessus plutôt que d'inventer "
             "un salaire.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="legal_monthly_hours",
        label="Heures légales de travail mensuelles",
        value=173.33,
        unit="heures/mois",
        kind="measured",
        source="Code du travail algérien — semaine légale de 40h",
        as_of="2026",
        note="40h/semaine × 52 / 12 = 173,33h/mois. Le diviseur légal utilisé "
             "pour dériver un taux horaire à partir d'un salaire mensuel.",
        tags=("labour",),
    ),
    Fact(
        key="cnas_employer_rate",
        label="Cotisation sociale patronale CNAS",
        value=0.26,
        unit="fraction du brut",
        kind="measured",
        source="Barème de cotisation patronale CNAS",
        as_of="2026",
        note="Part patronale (~25% + versement œuvres sociales). La principale "
             "raison pour laquelle le salaire affiché ≠ le vrai coût d'une heure "
             "de travail.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="cnas_employee_rate",
        label="Cotisation sociale salariale CNAS",
        value=0.09,
        unit="fraction du brut",
        kind="measured",
        source="Barème de cotisation CNAS",
        as_of="2026",
        note="Retenue sur le salarié, pas un coût employeur. Suivie pour que le "
             "modèle ne la compte jamais deux fois.",
        tags=("labour",),
    ),

    # ---- Market: the problem we sell against -----------------------------
    Fact(
        key="ecom_market_usd",
        label="Taille du marché e-commerce algérien",
        value=2_000_000_000,
        unit="USD/an",
        kind="measured",
        source="EasySell market analysis — Algeria e-commerce & COD landscape",
        url="https://easysellapp.com/blogs/wiki/algeria-ecommerce-cod-market-entry-shopify-2026",
        as_of="2026",
        note="Utilisé uniquement pour le cadrage du TAM. Traité comme un ordre "
             "de grandeur, pas comme une mesure précise.",
        tags=("market",),
    ),
    Fact(
        key="cod_share",
        label="Part des commandes e-commerce algériennes payées à la livraison",
        value=0.95,
        unit="fraction",
        kind="measured",
        source="EasySell / dz-ecom market analyses",
        url="https://easysellapp.com/blogs/wiki/algeria-ecommerce-cod-market-entry-shopify-2026",
        as_of="2026",
        note="Rapportée dans la fourchette 70-95% selon la source et le segment. "
             "Le paiement à la livraison explique qu'une journée mal dotée coûte "
             "deux fois au marchand : envoi aller ET retour.",
        tags=("market", "problem"),
    ),
    Fact(
        key="cod_return_rate",
        label="Taux de retour des commandes payées à la livraison (MENA)",
        value=0.19,
        unit="fraction",
        kind="measured",
        source="MENA COD benchmark — 19% COD vs 8% prepaid",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="En Algérie précisément, le choix du transporteur et la fiabilité "
             "de livraison font varier ce taux entre environ 15% et 25%. Les "
             "tentatives de livraison tardives ou manquées , c'est-à-dire le "
             "sous-effectif , le poussent vers le haut de la fourchette.",
        tags=("market", "problem"),
    ),
    Fact(
        key="yalidine_branches",
        label="Plus grand réseau d'agences d'un transporteur algérien",
        value=160,
        unit="agences",
        kind="measured",
        source="Yalidine network — 160+ branches, 1,469 communes, all 58 wilayas",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="Chaque agence est une opération de tri et de dispatch distincte "
             "avec son propre planning de shifts. C'est ce qui fait du marché "
             "une vente logicielle multi-sites plutôt qu'une mission de conseil "
             "unique.",
        tags=("market", "sam"),
    ),
    Fact(
        key="port_demurrage_usd_day",
        label="Surestaries des navires dans les ports algériens congestionnés",
        value=5000,
        unit="USD/jour/navire",
        kind="measured",
        source="Recovery Advisers market alert — Algeria customs & port delays",
        url="https://www.recoveryadvisers.com/insights/market-alert-algeria/",
        as_of="2025",
        note="Facturées après le troisième jour de retard. Les temps d'attente "
             "ont dépassé 7 jours à Alger et Skikda, avec jusqu'à 15 navires au "
             "mouillage au pic. Preuve que les erreurs de timing logistique en "
             "Algérie sont déjà chiffrées en devise forte.",
        tags=("market", "problem", "expansion"),
    ),
    Fact(
        key="algiers_port_wait_days",
        label="Temps d'attente des navires, port d'Alger",
        value=7,
        unit="jours",
        kind="measured",
        source="Port congestion monitoring — Algiers & Skikda >7 days",
        url="https://www.gocomet.com/real-time-port-congestion/algeria",
        as_of="2025",
        note="Bejaia et Djen-Djen 5-6 jours, Oran ~3 jours. Pose le vertical "
             "d'expansion : la main-d'œuvre des entrepôts sous douane et du "
             "dédouanement.",
        tags=("market", "expansion"),
    ),

    # ---- Payroll & compliance -------------------------------------------
    Fact(
        key="irg_exemption_monthly",
        label="Seuil d'exonération IRG (salaire mensuel)",
        value=30000,
        unit="DZD/mois",
        kind="measured",
        source="DGI — IRG traitements et salaires (LF 2022 reform)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Les salaires mensuels égaux ou inférieurs à 30 000 DZD ne paient "
             "aucun impôt sur le revenu. Comme le SNMG est de 24 000, les "
             "salariés au minimum sont exonérés , ce que le moteur de paie doit "
             "refléter exactement.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_abatement",
        label="Abattement proportionnel IRG sur l'impôt salarial",
        value=0.40,
        unit="fraction de l'IRG calculé",
        kind="measured",
        source="DGI — 40% abatement, floor 1,000 / cap 1,500 DZD per month",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Appliqué à l'impôt calculé par barème, borné à [1000, 1500] "
             "DZD/mois.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_family_reduction",
        label="Réduction IRG par personne à charge",
        value=1500,
        unit="DZD/mois chacune",
        kind="measured",
        source="DGI — 1,500 DZD/month for a non-earning spouse and per child (max 5)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Réduit directement l'IRG mensuel. Un déploiement réel collecte les "
             "personnes à charge de chaque salarié ; la démo est à zéro par "
             "défaut.",
        tags=("payroll",),
    ),
    Fact(
        key="cnas_social_works",
        label="Versement œuvres sociales CNAS (inclus dans les 26% patronaux)",
        value=0.005,
        unit="fraction du brut",
        kind="measured",
        source="CLEISS / CNAS — employer 25% across 5 branches + 0.5% oeuvres sociales",
        url="https://www.cleiss.fr/docs/cotisations/algerie.html",
        as_of="2025",
        note="Les 26% patronaux se décomposent en : assurances sociales 12,5%, "
             "retraite 10%, accidents du travail 1,25%, chômage 1%, retraite "
             "anticipée 0,25%, plus 0,5% d'œuvres sociales.",
        tags=("payroll",),
    ),

    # ---- HR / leave law --------------------------------------------------
    Fact(
        key="annual_leave_days",
        label="Congé annuel payé légal",
        value=30,
        unit="jours/an",
        kind="measured",
        source="Code du travail algérien — 2,5 jours acquis par mois travaillé",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="30 jours par an, acquis à raison de 2,5/mois. Les wilayas du Sud "
             "(sahariennes) ajoutent 10 jours (40 au total). Le moteur de congés "
             "doit acquérir et imposer cela exactement.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="south_leave_bonus_days",
        label="Congé annuel supplémentaire, wilayas du Sud",
        value=10,
        unit="jours/an",
        kind="measured",
        source="Code du travail algérien — wilayas sahariennes",
        url="https://vacationtracker.io/leave-laws/africa/algeria/",
        as_of="2024",
        note="Les salariés des wilayas du Sud reçoivent 40 jours au total.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="maternity_leave_weeks",
        label="Congé de maternité",
        value=14,
        unit="semaines",
        kind="measured",
        source="Code du travail / de la sécurité sociale algérien — plein salaire",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="14 semaines à plein salaire (typiquement 6 avant, 8 après la "
             "naissance), financées par la CNAS.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="sick_leave_split_day",
        label="Jour de passage du taux de maladie",
        value=15,
        unit="jours",
        kind="measured",
        source="Règles de sécurité sociale algérienne — 50% les 15 premiers jours, puis 100%",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="Les 15 premiers jours payés à demi-salaire ; plein salaire à "
             "partir du 16e jour ou en cas d'hospitalisation.",
        tags=("hr", "leave"),
    ),

    # ---- Aviation vertical (Air Algérie / Aéroport d'Alger) --------------
    Fact(
        key="airalgerie_pax_2025",
        label="Passagers Air Algérie, 2025",
        value=8_800_000,
        unit="passagers/an",
        kind="measured",
        source="Air Algérie 2026 transformation plan reporting (DzairTube)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="2025",
        note="En hausse d'environ 11% sur 2024. La courbe de croissance que "
             "l'aéroport doit doter en personnel.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="airalgerie_pax_target_2026",
        label="Objectif de passagers Air Algérie, 2026",
        value=10_000_000,
        unit="passagers/an",
        kind="measured",
        source="Air Algérie 2026 expansion strategy (DzairTube / Travel & Tour World)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="objectif 2026",
        note="Objectif d'environ 10M, plus ~60 nouveaux appareils (Boeing 737 "
             "MAX 8/9, gros-porteurs, ATR). Une croissance rapide sur un hub "
             "congestionné est précisément la pression que traite le module "
             "aéroportuaire.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="alg_pax_2024",
        label="Passagers Aéroport d'Alger, 2024",
        value=9_151_517,
        unit="passagers/an",
        kind="measured",
        source="Houari Boumediene Airport traffic figures",
        url="https://en.wikipedia.org/wiki/Houari_Boumediene_Airport",
        as_of="2024",
        note="ALG est le hub principal d'Air Algérie, avec des retards de "
             "période de pointe documentés et au moins une journée de retards en "
             "cascade médiatisée.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="reactionary_delay_share",
        label="Part réactionnaire (par ricochet) des retards aériens",
        value=0.45,
        unit="fraction",
        kind="measured",
        source="Industry norm for reactionary/cascade delay (Eurocontrol-style benchmark)",
        as_of="général",
        note="~40-50% de tout retard aérien est hérité d'un vol précédent, pas "
             "généré à neuf. Notre modèle de cascade reproduit cette part à "
             "partir de premiers principes, ce qui en est un contrôle de "
             "validité.",
        tags=("aviation",),
    ),

    # ---- Startup / funding context ---------------------------------------
    Fact(
        key="asf_fund_dzd",
        label="Capital de l'Algerian Startup Fund",
        value=2_400_000_000,
        unit="DZD",
        kind="measured",
        source="Algerian Startup Fund (ASF), capitalisé par six banques publiques",
        url="https://asf.dz/",
        as_of="2026",
        note="100+ startups financées sur 350+ candidatures. Pertinent car c'est "
             "un premier chèque réaliste pour cette entreprise.",
        tags=("funding",),
    ),
    Fact(
        key="startup_label_exemption_years",
        label="Exonération fiscale du Label Startup",
        value=4,
        unit="années",
        kind="measured",
        source="startup.dz — Label Startup benefits",
        url="https://www.upgrowth.dz/startup-algerie",
        as_of="2026",
        note="4 ans d'exonération d'impôt sur les bénéfices (IBS), de taxe sur "
             "l'activité professionnelle (TAP) et d'impôt sur le revenu des "
             "fondateurs, plus 0% de TVA sur les équipements importés. Change "
             "sensiblement le calcul de trésorerie.",
        tags=("funding",),
    ),

    # ---- Live API sources -------------------------------------------------
    Fact(
        key="weather_api",
        label="Météo historique & prévisionnelle",
        value="open-meteo",
        unit="",
        kind="live",
        source="Open-Meteo (archive de réanalyse ERA5 + prévision opérationnelle)",
        url="https://open-meteo.com/",
        note="Gratuit, sans clé d'API, par coordonnée. Nous donne une vraie "
             "météo quotidienne pour chaque chef-lieu de wilaya, en historique "
             "et en prévisionnel.",
        tags=("data",),
    ),
    Fact(
        key="macro_api",
        label="Indicateurs macroéconomiques de l'Algérie",
        value="worldbank",
        unit="",
        kind="live",
        source="World Bank Open Data — pays DZA",
        url="https://data.worldbank.org/country/DZ",
        note="Inflation, population, population active. Utilisés pour indexer les "
             "salaires et contrôler la cohérence du dimensionnement du marché.",
        tags=("data",),
    ),

    # ---- Assumptions: stated as assumptions, never as findings ------------
    Fact(
        key="productivity_parcels_per_hour",
        label="Colis triés par employé de hub et par heure",
        value=45,
        unit="colis/employé/heure",
        kind="assumption",
        source="Modèle WorkForce.dz",
        note="Tri manuel avec scan portable. C'est le premier chiffre qu'un "
             "client pilote remplace par son propre débit mesuré , tout le "
             "modèle de coût s'échelonne dessus, d'où le fait qu'on l'expose "
             "comme un curseur plutôt que de l'enterrer.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="overtime_premium",
        label="Majoration des heures supplémentaires",
        value=0.50,
        unit="fraction au-dessus du taux horaire de base",
        kind="assumption",
        source="Modèle WorkForce.dz, aligné sur la pratique du code du travail algérien",
        note="La loi algérienne fixe les heures supplémentaires à une majoration "
             "sur le taux horaire de base ; 50% est la valeur courante en "
             "journée. Le travail de nuit et de jour de repos entraîne des "
             "majorations plus élevées, modélisées séparément.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="temp_agency_markup",
        label="Majoration d'agence d'intérim sur l'emploi direct",
        value=0.35,
        unit="fraction",
        kind="assumption",
        source="Modèle WorkForce.dz",
        note="Frais d'agence au-dessus du coût horaire chargé d'un salarié "
             "employé en direct. Varie beaucoup selon la wilaya et le retard de "
             "la demande , ce qui est exactement le coût que la prévision "
             "supprime.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="understaffing_penalty_multiple",
        label="Multiple de coût d'une heure non couverte vs. une heure couverte",
        value=2.4,
        unit="×",
        kind="assumption",
        source="Modèle WorkForce.dz",
        note="Une heure de demande que l'on ne peut servir ne coûte pas "
             "seulement le salaire économisé. En e-commerce payé à la livraison, "
             "elle coûte la livraison ratée, le trajet retour, et une part de la "
             "valeur vie client. Nous la gardons prudente et l'exposons , c'est "
             "l'hypothèse la plus susceptible d'être contestée.",
        tags=("cost", "assumption"),
    ),
]


REGISTRY = {f.key: f for f in _FACTS}


def get(key: str) -> Fact:
    """Fetch a Fact, failing loudly if it was never registered."""
    if key not in REGISTRY:
        raise KeyError(
            f"No registered source for '{key}'. Add it to core/sources.py "
            f"before using it in the product."
        )
    return REGISTRY[key]


def value(key: str) -> Any:
    """Just the value — for use in calculations."""
    return get(key).value


def by_tag(tag: str) -> list:
    return [f for f in _FACTS if tag in f.tags]


def assumptions() -> list:
    """Every modelling assumption, for the 'what we assumed' disclosure."""
    return [f for f in _FACTS if f.is_assumption]


def measured() -> list:
    """Every externally-sourced measurement."""
    return [f for f in _FACTS if f.kind == "measured"]


def live_sources() -> list:
    return [f for f in _FACTS if f.kind == "live"]


def summary_table():
    """A pandas-ready list of dicts covering the whole registry."""
    rows = []
    for f in _FACTS:
        rows.append({
            "Key": f.key,
            "What": f.label,
            "Value": f.value,
            "Unit": f.unit,
            "Kind": f.kind,
            "Source": f.source,
            "As of": f.as_of,
            "URL": f.url,
            "Note": f.note,
        })
    return rows


if __name__ == "__main__":
    print(f"{len(_FACTS)} registered facts")
    print(f"  measured:    {len(measured())}")
    print(f"  live APIs:   {len(live_sources())}")
    print(f"  assumptions: {len(assumptions())}")
    print()
    for f in assumptions():
        print(f"  ASSUMPTION  {f.label} = {f.value} {f.unit}")
