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
            return f"Assumption — {self.note or 'modelling choice'}"
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
        label="SNMG (national guaranteed minimum wage)",
        value=24000,
        unit="DZD/month",
        kind="measured",
        source="Conseil des ministres / APS — SNMG raised from 20,000 to 24,000 DZD",
        url="https://www.aps.dz/fr/presidence-news/mim6ow3o-augmentation-du-snmg-a-24-000-da-a-partir-de-janvier-2026",
        as_of="in force January 2026",
        note="A 20% rise — the largest in decades. Directly moves every labour "
             "cost line in this model, which is why we key off it rather than "
             "inventing a wage.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="legal_monthly_hours",
        label="Legal monthly working hours",
        value=173.33,
        unit="hours/month",
        kind="measured",
        source="Algerian labour code — 40h legal working week",
        as_of="2026",
        note="40h/week x 52 / 12 = 173.33h/month. The statutory divisor used "
             "to derive an hourly rate from a monthly wage.",
        tags=("labour",),
    ),
    Fact(
        key="cnas_employer_rate",
        label="CNAS employer social contribution",
        value=0.26,
        unit="fraction of gross",
        kind="measured",
        source="CNAS employer contribution schedule",
        as_of="2026",
        note="Employer share (~25% + social works levy). The single biggest "
             "reason headline wage != true cost of an hour of labour.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="cnas_employee_rate",
        label="CNAS employee social contribution",
        value=0.09,
        unit="fraction of gross",
        kind="measured",
        source="CNAS contribution schedule",
        as_of="2026",
        note="Deducted from the worker, not an employer cost. Tracked so the "
             "model never double-counts it.",
        tags=("labour",),
    ),

    # ---- Market: the problem we sell against -----------------------------
    Fact(
        key="ecom_market_usd",
        label="Algerian e-commerce market size",
        value=2_000_000_000,
        unit="USD/year",
        kind="measured",
        source="EasySell market analysis — Algeria e-commerce & COD landscape",
        url="https://easysellapp.com/blogs/wiki/algeria-ecommerce-cod-market-entry-shopify-2026",
        as_of="2026",
        note="Used for TAM framing only. Treated as an order-of-magnitude "
             "figure, not a precise measurement.",
        tags=("market",),
    ),
    Fact(
        key="cod_share",
        label="Share of Algerian e-commerce orders paid cash on delivery",
        value=0.95,
        unit="fraction",
        kind="measured",
        source="EasySell / dz-ecom market analyses",
        url="https://easysellapp.com/blogs/wiki/algeria-ecommerce-cod-market-entry-shopify-2026",
        as_of="2026",
        note="Reported in the 70-95% range depending on source and segment. "
             "COD is why a mis-staffed delivery day costs the merchant twice: "
             "outbound AND return shipping.",
        tags=("market", "problem"),
    ),
    Fact(
        key="cod_return_rate",
        label="COD order return rate (MENA)",
        value=0.19,
        unit="fraction",
        kind="measured",
        source="MENA COD benchmark — 19% COD vs 8% prepaid",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="In Algeria specifically, carrier choice and delivery reliability "
             "swing this between roughly 15% and 25%. Late or missed delivery "
             "attempts — i.e. understaffing — push it toward the top of that band.",
        tags=("market", "problem"),
    ),
    Fact(
        key="yalidine_branches",
        label="Largest Algerian carrier branch network",
        value=160,
        unit="branches",
        kind="measured",
        source="Yalidine network — 160+ branches, 1,469 communes, all 58 wilayas",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="Each branch is a separate sorting-and-dispatch operation with its "
             "own shift roster. This is what makes the market a multi-site "
             "software sale rather than a single consulting engagement.",
        tags=("market", "sam"),
    ),
    Fact(
        key="port_demurrage_usd_day",
        label="Vessel demurrage at congested Algerian ports",
        value=5000,
        unit="USD/day/vessel",
        kind="measured",
        source="Recovery Advisers market alert — Algeria customs & port delays",
        url="https://www.recoveryadvisers.com/insights/market-alert-algeria/",
        as_of="2025",
        note="Charged after the third day of delay. Waiting times exceeded 7 "
             "days at Algiers and Skikda, with up to 15 vessels anchored at "
             "peak. Evidence that Algerian logistics timing errors are already "
             "priced in hard currency.",
        tags=("market", "problem", "expansion"),
    ),
    Fact(
        key="algiers_port_wait_days",
        label="Vessel waiting time, Port of Algiers",
        value=7,
        unit="days",
        kind="measured",
        source="Port congestion monitoring — Algiers & Skikda >7 days",
        url="https://www.gocomet.com/real-time-port-congestion/algeria",
        as_of="2025",
        note="Bejaia and Djen-Djen 5-6 days, Oran ~3 days. Sets up the "
             "expansion vertical: bonded-warehouse and clearance labour.",
        tags=("market", "expansion"),
    ),

    # ---- Payroll & compliance -------------------------------------------
    Fact(
        key="irg_exemption_monthly",
        label="IRG exemption threshold (monthly salary)",
        value=30000,
        unit="DZD/month",
        kind="measured",
        source="DGI — IRG traitements et salaires (LF 2022 reform)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Monthly salaries at or below 30,000 DZD pay no income tax. Since "
             "the SNMG is 24,000, minimum-wage workers are exempt — which the "
             "payroll engine must reflect exactly.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_abatement",
        label="IRG proportional abatement on salary tax",
        value=0.40,
        unit="fraction of computed IRG",
        kind="measured",
        source="DGI — 40% abatement, floor 1,000 / cap 1,500 DZD per month",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Applied to the bracket-computed tax, bounded to [1000, 1500] "
             "DZD/month.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_family_reduction",
        label="IRG reduction per dependant",
        value=1500,
        unit="DZD/month each",
        kind="measured",
        source="DGI — 1,500 DZD/month for a non-earning spouse and per child (max 5)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Directly reduces monthly IRG. A real deployment collects each "
             "worker's dependants; the demo defaults to zero.",
        tags=("payroll",),
    ),
    Fact(
        key="cnas_social_works",
        label="CNAS social-works levy (within employer 26%)",
        value=0.005,
        unit="fraction of gross",
        kind="measured",
        source="CLEISS / CNAS — employer 25% across 5 branches + 0.5% oeuvres sociales",
        url="https://www.cleiss.fr/docs/cotisations/algerie.html",
        as_of="2025",
        note="The employer 26% breaks down as social insurance 12.5%, "
             "retirement 10%, work-accidents 1.25%, unemployment 1%, early "
             "retirement 0.25%, plus 0.5% social works.",
        tags=("payroll",),
    ),

    # ---- HR / leave law --------------------------------------------------
    Fact(
        key="annual_leave_days",
        label="Statutory annual paid leave",
        value=30,
        unit="days/year",
        kind="measured",
        source="Algerian labour code — 2.5 days accrued per month worked",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="30 days a year, accrued at 2.5/month. Southern (Saharan) "
             "provinces add 10 days (40 total). The leave engine must accrue "
             "and enforce this exactly.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="south_leave_bonus_days",
        label="Extra annual leave, southern provinces",
        value=10,
        unit="days/year",
        kind="measured",
        source="Algerian labour code — Saharan provinces",
        url="https://vacationtracker.io/leave-laws/africa/algeria/",
        as_of="2024",
        note="Workers in the southern wilayas receive 40 days total.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="maternity_leave_weeks",
        label="Maternity leave",
        value=14,
        unit="weeks",
        kind="measured",
        source="Algerian labour / social-security code — full salary",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="14 weeks at full pay (typically 6 before, 8 after birth), "
             "funded through CNAS.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="sick_leave_split_day",
        label="Sick-pay step-up day",
        value=15,
        unit="days",
        kind="measured",
        source="Algerian social-security rules — 50% for first 15 days, then 100%",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="First 15 days paid at half salary; full salary from day 16 or on "
             "hospitalisation.",
        tags=("hr", "leave"),
    ),

    # ---- Aviation vertical (Air Algérie / Aéroport d'Alger) --------------
    Fact(
        key="airalgerie_pax_2025",
        label="Air Algérie passengers, 2025",
        value=8_800_000,
        unit="passengers/year",
        kind="measured",
        source="Air Algérie 2026 transformation plan reporting (DzairTube)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="2025",
        note="Up ~11% on 2024. The growth curve the airport has to staff for.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="airalgerie_pax_target_2026",
        label="Air Algérie passenger target, 2026",
        value=10_000_000,
        unit="passengers/year",
        kind="measured",
        source="Air Algérie 2026 expansion strategy (DzairTube / Travel & Tour World)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="target 2026",
        note="~10M target, plus ~60 new aircraft (Boeing 737 MAX 8/9, "
             "widebody, ATR). Rapid growth onto a congested hub is precisely "
             "the pressure the airport-ops module addresses.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="alg_pax_2024",
        label="Aéroport d'Alger passengers, 2024",
        value=9_151_517,
        unit="passengers/year",
        kind="measured",
        source="Houari Boumediene Airport traffic figures",
        url="https://en.wikipedia.org/wiki/Houari_Boumediene_Airport",
        as_of="2024",
        note="ALG is Air Algérie's main hub, with documented peak-period "
             "delays and at least one publicised cascading-delay day.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="reactionary_delay_share",
        label="Reactionary (knock-on) share of airline delays",
        value=0.45,
        unit="fraction",
        kind="measured",
        source="Industry norm for reactionary/cascade delay (Eurocontrol-style benchmark)",
        as_of="general",
        note="~40–50% of all airline delay is inherited from a previous "
             "flight, not generated fresh. Our cascade model reproduces this "
             "share from first principles, which is a validity check on it.",
        tags=("aviation",),
    ),

    # ---- Startup / funding context ---------------------------------------
    Fact(
        key="asf_fund_dzd",
        label="Algerian Startup Fund capital",
        value=2_400_000_000,
        unit="DZD",
        kind="measured",
        source="Algerian Startup Fund (ASF), capitalised with six public banks",
        url="https://asf.dz/",
        as_of="2026",
        note="100+ startups funded from 350+ applications. Relevant because it "
             "is a realistic first cheque for this company.",
        tags=("funding",),
    ),
    Fact(
        key="startup_label_exemption_years",
        label="Startup-label tax exemption",
        value=4,
        unit="years",
        kind="measured",
        source="startup.dz — Label Startup benefits",
        url="https://www.upgrowth.dz/startup-algerie",
        as_of="2026",
        note="4 years' exemption on corporate income tax (IBS), professional "
             "activity tax (TAP) and founder income tax, plus 0% VAT on "
             "imported equipment. Materially changes our runway maths.",
        tags=("funding",),
    ),

    # ---- Live API sources -------------------------------------------------
    Fact(
        key="weather_api",
        label="Historical & forecast weather",
        value="open-meteo",
        unit="",
        kind="live",
        source="Open-Meteo (ERA5 reanalysis archive + operational forecast)",
        url="https://open-meteo.com/",
        note="Free, no API key, per-coordinate. Gives us genuine daily weather "
             "for every wilaya capital, historical and forward.",
        tags=("data",),
    ),
    Fact(
        key="macro_api",
        label="Algeria macroeconomic indicators",
        value="worldbank",
        unit="",
        kind="live",
        source="World Bank Open Data — country DZA",
        url="https://data.worldbank.org/country/DZ",
        note="Inflation, population, labour force. Used to index wages and to "
             "sanity-check market sizing.",
        tags=("data",),
    ),

    # ---- Assumptions: stated as assumptions, never as findings ------------
    Fact(
        key="productivity_parcels_per_hour",
        label="Parcels sorted per hub worker per hour",
        value=45,
        unit="parcels/worker/hour",
        kind="assumption",
        source="WorkForce.dz model",
        note="Manual sort with handheld scanning. This is the first number a "
             "pilot customer replaces with their own measured throughput — the "
             "whole cost model scales off it, so we expose it as a slider "
             "rather than burying it.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="overtime_premium",
        label="Overtime premium",
        value=0.50,
        unit="fraction above base hourly",
        kind="assumption",
        source="WorkForce.dz model, aligned to Algerian labour code practice",
        note="Algerian law sets overtime at a premium over the base hourly "
             "rate; 50% is the common daytime figure. Night and rest-day work "
             "attract higher premiums, modelled separately.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="temp_agency_markup",
        label="Temp-agency markup over direct employment",
        value=0.35,
        unit="fraction",
        kind="assumption",
        source="WorkForce.dz model",
        note="Agency fee on top of the loaded hourly cost of a directly "
             "employed worker. Varies widely by wilaya and by how late the "
             "request is made — which is exactly the cost forecasting removes.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="understaffing_penalty_multiple",
        label="Cost multiple of an uncovered hour vs. a covered one",
        value=2.4,
        unit="x",
        kind="assumption",
        source="WorkForce.dz model",
        note="An hour of demand you cannot serve does not merely cost the "
             "wage you saved. In COD e-commerce it costs the failed delivery, "
             "the return leg, and a share of lifetime customer value. We keep "
             "this conservative and expose it — it is the single assumption "
             "most likely to be challenged.",
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
