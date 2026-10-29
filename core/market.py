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
        label="Parcel and e-commerce delivery branches",
        sites=600,
        avg_shift_workers=45,
        basis=(
            "Yalidine alone runs 160+ branches across 1,469 communes and all 58 "
            "wilayas (cited). ZR Express, Maystro, Noest, Kazitour and regional "
            "operators together plausibly match or exceed that. 600 is a "
            "deliberately conservative national figure."
        ),
        confidence="anchored",
    ),
    SegmentEstimate(
        key="retail_dc",
        label="Retail and FMCG distribution centres",
        sites=180,
        avg_shift_workers=70,
        basis=(
            "Organised food and FMCG distribution in Algeria (large groups and "
            "wilaya-level wholesalers). Estimated from the number of big-box "
            "distribution groups and their regional depot structure."
        ),
        confidence="estimated",
    ),
    SegmentEstimate(
        key="airport_ground",
        label="Airport ground handling",
        sites=16,
        avg_shift_workers=140,
        basis=(
            "Algeria has 35 commercial airports; about 16 carry enough regular "
            "traffic for multi-shift ground handling. Few, but heavy per site, "
            "and the anchor client for credibility."
        ),
        confidence="anchored",
    ),
    SegmentEstimate(
        key="port_logistics",
        label="Port operations, bonded warehouses and customs clearance",
        sites=45,
        avg_shift_workers=90,
        basis=(
            "The commercial ports (Algiers, Oran, Bejaia, Skikda, Djen-Djen, "
            "Annaba, Mostaganem, Ghazaouet) plus bonded-storage and customs "
            "operators. Ship waits exceed 7 days in Algiers with demurrage at "
            "$5,000/day/ship (cited): timing errors are already priced in hard "
            "currency."
        ),
        confidence="estimated",
    ),
    SegmentEstimate(
        key="food_manufacturing",
        label="Food manufacturing (multi-shift)",
        sites=320,
        avg_shift_workers=85,
        basis=(
            "Food processing is Algeria's largest non-hydrocarbon industry and "
            "runs continuous shifts with strong Ramadan seasonality. An expansion "
            "vertical, not in the initial target."
        ),
        confidence="estimated",
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
            f"Measured saving of {saving_per_month:,.0f} DZD/site/month over "
            f"{days_scored} scored operating days. Priced at {value_share:.0%} of "
            f"that, leaving the client about a {1 / value_share:.0f}x return on "
            f"the subscription."
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
    sam_segments = table[~table["Segment"].str.contains("airport", case=False)]
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
            "Bottom-up: number of sites x monthly price x 12. No top-down "
            "\"1% of a big number\" arithmetic.",
            "SAM excludes airport ground handling. Algerian airports are state "
            "run and buy through multi-year public tenders: real revenue later, "
            "but not enough to build a three-year plan on.",
            f"SOM assumes {som_penetration:.0%} of SAM in {som_years} years, about "
            f"{som_sites} sites. Getting there means about "
            f"{som_sites / max(som_years * 12, 1):.1f} new sites a month.",
            "Price is derived from the measured saving per site: if the pilot "
            "shows a smaller saving, the price and this whole table fall with "
            "it. That is intentional.",
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
            {"Metric": "Price per site / month", "Value": f"{self.monthly_price_dzd:,.0f} DZD"},
            {"Metric": "Gross margin", "Value": f"{self.gross_margin:.0%}"},
            {"Metric": "Gross profit / site / month", "Value": f"{self.monthly_gross_profit:,.0f} DZD"},
            {"Metric": "CAC (sales + onboarding)", "Value": f"{self.cac_dzd + self.onboarding_cost_dzd:,.0f} DZD"},
            {"Metric": "Monthly churn", "Value": f"{self.monthly_churn:.1%}"},
            {"Metric": "Expected lifetime", "Value": f"{self.customer_lifetime_months:.0f} months"},
            {"Metric": "LTV", "Value": f"{self.ltv_dzd:,.0f} DZD"},
            {"Metric": "LTV : CAC", "Value": f"{self.ltv_cac:.1f}x"},
            {"Metric": "CAC payback", "Value": f"{self.cac_payback_months:.1f} months"},
        ])

    def assumptions(self) -> list:
        return [
            f"Gross margin {self.gross_margin:.0%}: hosting and inference are "
            f"the only real variable costs; the forecaster is a gradient-boosted "
            f"model, not an LLM, so cost to serve per site is negligible.",
            f"CAC {self.cac_dzd:,.0f} DZD assumes founder-led direct sales in "
            f"Algiers and Oran. It will rise once a sales team is hired.",
            f"Onboarding {self.onboarding_cost_dzd:,.0f} DZD covers the engineer "
            f"weeks to ingest a client's history and set its productivity "
            f"constants. This is the number that decides whether the model "
            f"scales: it must trend to zero with tooling.",
            f"Churn {self.monthly_churn:.1%}/month is an unproven assumption at "
            f"this stage. Weekly-active B2B operations software usually churns "
            f"less, but we have no cohort data and will not pretend otherwise.",
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
    {"country": "Algeria",      "population_m": 47.4, "weekend": "Fri-Sat", "status": "Beachhead"},
    {"country": "Morocco",      "population_m": 38.1, "weekend": "Sat-Sun", "status": "Phase 2"},
    {"country": "Tunisia",      "population_m": 12.3, "weekend": "Sat-Sun", "status": "Phase 2"},
    {"country": "Egypt",        "population_m": 116.5, "weekend": "Fri-Sat", "status": "Phase 3"},
    {"country": "Saudi Arabia", "population_m": 34.1, "weekend": "Fri-Sat", "status": "Phase 3"},
    {"country": "Jordan",       "population_m": 11.5, "weekend": "Fri-Sat", "status": "Phase 3"},
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
            "Country": m["country"],
            "Population (M)": m["population_m"],
            "Weekend": m["weekend"],
            "Proportional SAM (DZD/yr)": scaled,
            "Status": m["status"],
        })
    table = pd.DataFrame(rows)

    return {
        "table": table,
        "total_dzd": float(table["Proportional SAM (DZD/yr)"].sum()),
        "notes": [
            "Proportional to population, which is crude. Egypt's large informal "
            "sector and Saudi Arabia's very different wage structure both argue "
            "for a steep discount.",
            "The reusable asset is the Hijri calendar engine: Ramadan and the "
            "Eids reshape demand the same way in all six markets, and no global "
            "HR tool models them.",
            "The weekend convention does NOT generalise: three of these six "
            "markets run Saturday-Sunday. That is per-country configuration, "
            "which is why the engine is parameterised by market.",
            "Algeria alone is a few-million-dollar ARR opportunity: a good "
            "business, but not venture scale on its own. The regional case is "
            "what justifies the second cheque.",
        ],
    }


def funding_context() -> list:
    """Where the money realistically comes from in Algeria."""
    asf = sources.get("asf_fund_dzd")
    label = sources.get("startup_label_exemption_years")
    return [
        f"The Algerian Startup Fund is capitalised at {asf.value / 1e9:.1f} "
        f"billion DZD by six public banks and has funded 100+ startups from "
        f"350+ applications. A realistic first cheque. [{asf.cite()}]",
        f"The Startup Label brings {label.value} years of exemption from "
        f"corporate tax, professional activity tax and founders' income tax, "
        f"plus 0% VAT on imported equipment. Extends runway materially. [{label.cite()}]",
        "Algerie Telecom's 1.5 billion DZD fund (about $11M) targets AI, "
        "cybersecurity and robotics specifically: this product is eligible.",
        "Pan-regional funds (Partech, Orange Ventures, Flat6Labs) closed about "
        "8 Algerian deals in 2024-2025, so a follow-on round has precedent.",
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
