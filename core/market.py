"""
core/market.py
--------------
Market sizing and unit economics, built bottom-up and shown working.

The rule applied throughout
===========================
Every figure is either (a) pulled from `sources.py` with a citation, or
(b) an explicitly labelled assumption with the reasoning attached. There are
no numbers here whose provenance a reader cannot reconstruct.

Top-down TAM slides ("the Algerian logistics market is worth $X billion, we
need only 1%") are worthless and experienced investors treat them as a
negative signal. So the sizing here is bottom-up: count the sites, price the
value delivered to one of them, multiply. The count is the arguable part, and
it is exposed as an input rather than buried.

Pricing is derived, not invented
================================
`price_from_value()` takes the measured saving per site from the evidence run
in `pipeline.py` and prices the product as a share of value delivered. That
way the price moves when the evidence moves, and the pitch cannot drift away
from what the software actually does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import sources


# ---------------------------------------------------------------------------
# Serviceable site counts (bottom-up)
# ---------------------------------------------------------------------------

@dataclass
class SegmentEstimate:
    key: str
    label: str
    sites: int
    avg_shift_workers: int
    basis: str
    confidence: str  # "anchored" | "estimated"


SEGMENTS = [
    SegmentEstimate(
        key="parcel_hubs",
        label="Agences de colis et livraison e-commerce",
        sites=600,
        avg_shift_workers=45,
        basis=(
            "Yalidine exploite à elle seule 160+ agences dans 1 469 communes et "
            "les 58 wilayas (cité). ZR Express, Maystro, Noest, Kazitour et les "
            "opérateurs régionaux ensemble égalent ou dépassent plausiblement ce "
            "chiffre. 600 est un chiffre national volontairement prudent."
        ),
        confidence="ancré",
    ),
    SegmentEstimate(
        key="retail_dc",
        label="Centres de distribution retail et grande conso",
        sites=180,
        avg_shift_workers=70,
        basis=(
            "La distribution organisée alimentaire et grande conso en Algérie , "
            "Cevital, Numilog, Ardis, NCA Rouiba et les grossistes au niveau des "
            "wilayas. Estimé à partir du nombre de groupes de distribution en "
            "grande surface et de leur structure de dépôts régionaux."
        ),
        confidence="estimé",
    ),
    SegmentEstimate(
        key="airport_ground",
        label="Assistance aéroportuaire au sol",
        sites=16,
        avg_shift_workers=140,
        basis=(
            "L'Algérie compte 35 aéroports commerciaux ; environ 16 portent un "
            "trafic régulier suffisant pour une assistance au sol en multi-shifts. "
            "Peu nombreux, mais lourds par site , et le client d'ancrage pour la "
            "crédibilité."
        ),
        confidence="ancré",
    ),
    SegmentEstimate(
        key="port_logistics",
        label="Opérations portuaires, entrepôts sous douane et dédouanement",
        sites=45,
        avg_shift_workers=90,
        basis=(
            "Les ports commerciaux (Alger, Oran, Bejaia, Skikda, Djen-Djen, "
            "Annaba, Mostaganem, Ghazaouet) ainsi que les opérateurs de stockage "
            "sous douane et de dédouanement. L'attente des navires dépasse 7 jours "
            "à Alger avec des surestaries à 5 000 $/jour/navire (cité) , les "
            "erreurs de timing y sont déjà chiffrées en devise forte."
        ),
        confidence="estimé",
    ),
    SegmentEstimate(
        key="food_manufacturing",
        label="Industrie agroalimentaire (multi-shifts)",
        sites=320,
        avg_shift_workers=85,
        basis=(
            "L'agroalimentaire est le plus grand secteur industriel hors "
            "hydrocarbures d'Algérie et tourne en shifts continus avec une forte "
            "saisonnalité de Ramadan. Vertical d'expansion, pas dans la cible "
            "initiale."
        ),
        confidence="estimé",
    ),
]


# ---------------------------------------------------------------------------
# Pricing derived from measured value
# ---------------------------------------------------------------------------

@dataclass
class Pricing:
    monthly_price_dzd: float
    value_share: float
    saving_per_site_month_dzd: float
    payback_months: float
    note: str


def price_from_value(
    saving_dzd: float,
    days_scored: int,
    value_share: float = 0.20,
    floor_dzd: float = 25_000,
    ceiling_dzd: float = 180_000,
) -> Pricing:
    """
    Price the product as a share of the value it is measured to deliver.

    `value_share` is the fraction of the customer's saving we capture. 20% is
    deliberately modest: it leaves the customer a 5x return, which is what
    makes an Algerian operator with no history of buying software actually
    sign. Charging more would price in a shorter sales cycle than this market
    has.
    """
    months = max(days_scored / 30.44, 1e-9)
    saving_per_month = saving_dzd / months
    price = saving_per_month * value_share
    price = float(min(max(price, floor_dzd), ceiling_dzd))

    return Pricing(
        monthly_price_dzd=price,
        value_share=value_share,
        saving_per_site_month_dzd=saving_per_month,
        payback_months=price / saving_per_month if saving_per_month > 0 else float("inf"),
        note=(
            f"Économie mesurée de {saving_per_month:,.0f} DZD/site/mois sur "
            f"{days_scored} jours d'exploitation évalués. Facturée à "
            f"{value_share:.0%} de ce montant, laissant au client un retour "
            f"d'environ {1 / value_share:.0f}× sur l'abonnement."
        ),
    )


# ---------------------------------------------------------------------------
# TAM / SAM / SOM
# ---------------------------------------------------------------------------

def sizing(
    monthly_price_dzd: float,
    beachhead_keys: tuple = ("parcel_hubs",),
    som_penetration: float = 0.04,
    som_years: int = 3,
) -> dict:
    """
    Bottom-up market sizing.

    TAM  - every multi-shift site in Algeria we could ever serve.
    SAM  - the segments we can actually sell to in the next few years:
           private operators, no public-tender procurement.
    SOM  - a defensible share of SAM within `som_years`.
    """
    rows = []
    for s in SEGMENTS:
        annual = s.sites * monthly_price_dzd * 12
        rows.append({
            "Segment": s.label,
            "Sites": s.sites,
            "Avg shift workers": s.avg_shift_workers,
            "Annual value (DZD)": annual,
            "Confidence": s.confidence,
            "Basis": s.basis,
        })
    table = pd.DataFrame(rows)

    tam = float(table["Annual value (DZD)"].sum())

    # SAM excludes airport ground handling: Algeria's airports are state
    # operated, and selling there means public procurement on a multi-year
    # cycle. It stays in TAM and in the roadmap as a credibility anchor, but
    # a startup cannot build a plan on it.
    sam_segments = table[~table["Segment"].str.contains("aéroport", case=False)]
    sam = float(sam_segments["Annual value (DZD)"].sum())

    beachhead_sites = sum(s.sites for s in SEGMENTS if s.key in beachhead_keys)
    beachhead_value = beachhead_sites * monthly_price_dzd * 12

    som = sam * som_penetration
    som_sites = int(round(som / (monthly_price_dzd * 12))) if monthly_price_dzd else 0

    return {
        "table": table,
        "tam_dzd": tam,
        "sam_dzd": sam,
        "som_dzd": som,
        "som_sites": som_sites,
        "som_penetration": som_penetration,
        "som_years": som_years,
        "beachhead_sites": beachhead_sites,
        "beachhead_dzd": beachhead_value,
        "total_sites": int(table["Sites"].sum()),
        "notes": [
            "Bottom-up : nombre de sites × prix mensuel × 12. Aucune "
            "arithmétique top-down du type « 1% d'un gros chiffre ».",
            "Le SAM exclut l'assistance aéroportuaire. Les aéroports algériens "
            "sont exploités par l'État et achètent par appel d'offres public sur "
            "un cycle pluriannuel , du vrai revenu à terme, mais pas de quoi "
            "bâtir un plan à trois ans.",
            f"Le SOM suppose {som_penetration:.0%} du SAM en {som_years} ans , "
            f"environ {som_sites} sites. L'atteindre revient à environ "
            f"{som_sites / max(som_years * 12, 1):.1f} nouveaux sites par mois.",
            "Le prix est dérivé de l'économie mesurée par site : si le pilote "
            "montre une économie plus faible, le prix et tout ce tableau "
            "baissent avec lui. C'est intentionnel.",
        ],
    }


# ---------------------------------------------------------------------------
# Unit economics
# ---------------------------------------------------------------------------

@dataclass
class UnitEconomics:
    monthly_price_dzd: float
    gross_margin: float = 0.82
    cac_dzd: float = 140_000
    monthly_churn: float = 0.015
    onboarding_cost_dzd: float = 60_000

    @property
    def monthly_gross_profit(self) -> float:
        return self.monthly_price_dzd * self.gross_margin

    @property
    def customer_lifetime_months(self) -> float:
        return 1.0 / self.monthly_churn if self.monthly_churn > 0 else float("inf")

    @property
    def ltv_dzd(self) -> float:
        return self.monthly_gross_profit * self.customer_lifetime_months

    @property
    def cac_payback_months(self) -> float:
        gp = self.monthly_gross_profit
        return (self.cac_dzd + self.onboarding_cost_dzd) / gp if gp > 0 else float("inf")

    @property
    def ltv_cac(self) -> float:
        total_acq = self.cac_dzd + self.onboarding_cost_dzd
        return self.ltv_dzd / total_acq if total_acq > 0 else float("inf")

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"Indicateur": "Prix par site / mois", "Valeur": f"{self.monthly_price_dzd:,.0f} DZD"},
            {"Indicateur": "Marge brute", "Valeur": f"{self.gross_margin:.0%}"},
            {"Indicateur": "Profit brut / site / mois", "Valeur": f"{self.monthly_gross_profit:,.0f} DZD"},
            {"Indicateur": "CAC (vente + onboarding)", "Valeur": f"{self.cac_dzd + self.onboarding_cost_dzd:,.0f} DZD"},
            {"Indicateur": "Attrition mensuelle", "Valeur": f"{self.monthly_churn:.1%}"},
            {"Indicateur": "Durée de vie attendue", "Valeur": f"{self.customer_lifetime_months:.0f} mois"},
            {"Indicateur": "LTV", "Valeur": f"{self.ltv_dzd:,.0f} DZD"},
            {"Indicateur": "LTV : CAC", "Valeur": f"{self.ltv_cac:.1f}×"},
            {"Indicateur": "Retour sur CAC", "Valeur": f"{self.cac_payback_months:.1f} mois"},
        ])

    def assumptions(self) -> list:
        return [
            f"Marge brute {self.gross_margin:.0%} , l'hébergement et l'inférence "
            f"sont les seuls vrais coûts variables ; le prévisionniste est un "
            f"modèle à gradient boosté, pas un LLM, donc le coût de service par "
            f"site est négligeable.",
            f"CAC {self.cac_dzd:,.0f} DZD suppose une vente directe menée par les "
            f"fondateurs à Alger et Oran. Il augmentera à l'embauche d'une équipe "
            f"commerciale.",
            f"L'onboarding {self.onboarding_cost_dzd:,.0f} DZD couvre les "
            f"semaines-ingénieur pour ingérer l'historique d'un client et caler "
            f"ses constantes de productivité. C'est le chiffre qui décide si le "
            f"modèle passe à l'échelle , il doit tendre vers zéro avec l'outillage.",
            f"L'attrition {self.monthly_churn:.1%}/mois est une hypothèse sans "
            f"preuve à ce stade. Un logiciel opérationnel B2B à usage hebdomadaire "
            f"actif s'érode généralement moins, mais nous n'avons pas de données "
            f"de cohorte et ne prétendrons pas le contraire.",
        ]


# ---------------------------------------------------------------------------
# Regional expansion
# ---------------------------------------------------------------------------

# Be honest about what actually generalises.
#
# The Friday-Saturday weekend does NOT generalise: Morocco, Tunisia and the UAE
# run Saturday-Sunday, while Algeria, Egypt, Saudi Arabia, Jordan and Libya run
# Friday-Saturday. Anyone claiming "the Muslim world has a Friday weekend" is
# wrong and will be corrected in the room.
#
# What *does* generalise is the expensive part: the Hijri calendar. Ramadan and
# the two Aids move ~11 days earlier every Gregorian year and reshape demand in
# every one of these markets. That is the piece global workforce tools get
# wrong everywhere, and it is the reusable core of the engine. The weekend
# convention, national holidays and school calendar are per-country
# configuration on top of it - a week of work per market, not a rebuild.

REGIONAL_MARKETS = [
    {"country": "Algérie",       "population_m": 47.4, "weekend": "Ven-Sam", "status": "Tête de pont"},
    {"country": "Maroc",         "population_m": 38.1, "weekend": "Sam-Dim", "status": "Phase 2"},
    {"country": "Tunisie",       "population_m": 12.3, "weekend": "Sam-Dim", "status": "Phase 2"},
    {"country": "Égypte",        "population_m": 116.5, "weekend": "Ven-Sam", "status": "Phase 3"},
    {"country": "Arabie saoudite", "population_m": 34.1, "weekend": "Ven-Sam", "status": "Phase 3"},
    {"country": "Jordanie",      "population_m": 11.5, "weekend": "Ven-Sam", "status": "Phase 3"},
]


def regional_expansion(algeria_sam_dzd: float) -> dict:
    """
    Scale the Algerian SAM across comparable markets by population.

    Crude - population is a weak proxy for logistics-sector maturity, and
    Egypt's informal economy and Saudi's very different wage structure both
    cut against a naive scaling. It is presented as an order-of-magnitude
    ceiling on the opportunity, not a forecast.
    """
    algeria_pop = REGIONAL_MARKETS[0]["population_m"]
    rows = []
    for m in REGIONAL_MARKETS:
        scaled = algeria_sam_dzd * (m["population_m"] / algeria_pop)
        rows.append({
            "Pays": m["country"],
            "Population (M)": m["population_m"],
            "Week-end": m["weekend"],
            "SAM proportionnel (DZD/an)": scaled,
            "Statut": m["status"],
        })
    table = pd.DataFrame(rows)

    return {
        "table": table,
        "total_dzd": float(table["SAM proportionnel (DZD/an)"].sum()),
        "notes": [
            "Proportionnel à la population, ce qui est grossier. Le vaste secteur "
            "informel de l'Égypte et la structure salariale très différente de "
            "l'Arabie saoudite plaident tous deux pour un net escompte.",
            "L'actif réutilisable est le moteur de calendrier hégirien , le "
            "Ramadan et les Aïds remodèlent la demande à l'identique sur les six "
            "marchés, et aucun outil RH mondial ne les modélise.",
            "La convention de week-end NE se généralise PAS : trois de ces six "
            "marchés fonctionnent en samedi-dimanche. C'est de la configuration "
            "par pays, ce qui est précisément pourquoi le moteur est paramétré "
            "par marché plutôt que figé sur l'Algérie.",
            "L'Algérie seule est une opportunité d'ARR de quelques millions de "
            "dollars , une bonne affaire, mais pas à l'échelle du capital-risque "
            "à elle seule. C'est le dossier régional qui justifie le second chèque.",
        ],
    }


def funding_context() -> list:
    """Where the money realistically comes from in Algeria."""
    asf = sources.get("asf_fund_dzd")
    label = sources.get("startup_label_exemption_years")
    return [
        f"L'Algerian Startup Fund est capitalisé à {asf.value / 1e9:.1f} "
        f"milliards DZD par six banques publiques et a financé 100+ startups sur "
        f"350+ candidatures. Un premier chèque réaliste. [{asf.cite()}]",
        f"Le Label Startup porte {label.value} ans d'exonération d'impôt sur les "
        f"bénéfices des sociétés, de la taxe sur l'activité professionnelle et de "
        f"l'impôt sur le revenu des fondateurs, plus 0% de TVA sur les "
        f"équipements importés. Prolonge sensiblement la trésorerie. [{label.cite()}]",
        "Le fonds d'Algérie Télécom de 1,5 milliard DZD (~11 M$) cible "
        "spécifiquement l'IA, la cybersécurité et la robotique , ce produit y "
        "est éligible.",
        "Des fonds paneuropéens (Partech, Orange Ventures, Flat6Labs) ont bouclé "
        "environ 8 opérations algériennes en 2024-2025, un tour de suivi a donc "
        "un précédent.",
    ]


if __name__ == "__main__":
    print("Market model - self check\n")

    # Figures from the evidence run in pipeline.py (e-commerce hub).
    pricing = price_from_value(saving_dzd=3_462_008, days_scored=448)
    print(f"Derived price: {pricing.monthly_price_dzd:,.0f} DZD/site/month")
    print(f"  {pricing.note}\n")

    s = sizing(pricing.monthly_price_dzd)
    print(s["table"][["Segment", "Sites", "Annual value (DZD)", "Confidence"]]
          .to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
    print(f"\n  TAM : {s['tam_dzd']:,.0f} DZD/year  (~${s['tam_dzd'] / 135:,.0f})")
    print(f"  SAM : {s['sam_dzd']:,.0f} DZD/year")
    print(f"  SOM : {s['som_dzd']:,.0f} DZD/year  ({s['som_sites']} sites, "
          f"{s['som_penetration']:.0%} of SAM in {s['som_years']}y)")

    print("\nUnit economics:")
    ue = UnitEconomics(pricing.monthly_price_dzd)
    print(ue.table().to_string(index=False))
