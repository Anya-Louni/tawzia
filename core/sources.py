"""
core/sources.py
---------------
A single registry for every externally-sourced number used anywhere in
Tawzia, plus every assumption we make.

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
            return f"Assumption: {self.note or 'modelling choice'}"
        bits = [self.source]
        if self.as_of:
            bits.append(self.as_of)
        return ", ".join(bits)


# ---------------------------------------------------------------------------
# LABOUR & COST — the inputs that decide whether our savings number is real
# ---------------------------------------------------------------------------

# Legal rates come from the dated config/dz_payroll_<year>.toml file: the
# registry keeps their provenance, never a second copy of the value.
from . import rules as _rules  # noqa: E402
_RULES = _rules.payroll()
_CNAS = _rules.cnas_rates()

_FACTS = [
    Fact(
        key="snmg_monthly_dzd",
        label="SNMG (guaranteed national minimum wage)",
        value=_RULES["snmg"]["monthly"],
        unit="DZD/month",
        kind="measured",
        source="Council of Ministers / APS: SNMG raised from 20,000 to 24,000 DZD",
        url="https://www.aps.dz/fr/presidence-news/mim6ow3o-augmentation-du-snmg-a-24-000-da-a-partir-de-janvier-2026",
        as_of="in force January 2026",
        note="A 20% rise, the largest in decades. It moves every labour-cost "
             "line in this model, which is why we index on it rather than "
             "invent a salary.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="legal_monthly_hours",
        label="Legal monthly working hours",
        value=_RULES["hours"]["legal_month"],
        unit="hours/month",
        kind="measured",
        source="Algerian labour code: 40-hour legal week",
        as_of="2026",
        note="40 h/week x 52 / 12 = 173.33 h/month. The legal divisor used to "
             "derive an hourly rate from a monthly salary.",
        tags=("labour",),
    ),
    Fact(
        key="cnas_employer_rate",
        label="CNAS employer social contribution",
        value=_CNAS[0],
        unit="fraction of gross",
        kind="measured",
        source="CNAS employer contribution scale",
        as_of="2026",
        note="Sum of the per-branch scale in the rules file [verify: several "
             "sources give 26%]. The main reason the advertised salary is not "
             "the real cost of an hour of work.",
        tags=("labour", "cost"),
    ),
    Fact(
        key="cnas_employee_rate",
        label="CNAS employee social contribution",
        value=_CNAS[1],
        unit="fraction of gross",
        kind="measured",
        source="CNAS contribution scale",
        as_of="2026",
        note="Withheld from the employee, not an employer cost. Tracked so the "
             "model never counts it twice.",
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
        note="Used only to frame the TAM. An order of magnitude, not a precise "
             "measurement.",
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
        note="Reported at 70-95% depending on source and segment. Cash on "
             "delivery is why an understaffed day costs the merchant twice: the "
             "outbound AND the return.",
        tags=("market", "problem"),
    ),
    Fact(
        key="cod_return_rate",
        label="Return rate of cash-on-delivery orders (MENA)",
        value=0.19,
        unit="fraction",
        kind="measured",
        source="MENA COD benchmark — 19% COD vs 8% prepaid",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="In Algeria, carrier choice and delivery reliability move this "
             "between about 15% and 25%. Late or missed delivery attempts, that "
             "is understaffing, push it to the top of the range.",
        tags=("market", "problem"),
    ),
    Fact(
        key="yalidine_branches",
        label="Largest branch network of an Algerian carrier",
        value=160,
        unit="branches",
        kind="measured",
        source="Yalidine network — 160+ branches, 1,469 communes, all 58 wilayas",
        url="https://dz-ecom.com/en/blog/yalidine-vs-zr-express-vs-noest-comparatif-2026",
        as_of="2026",
        note="Each branch is a separate sorting and dispatch operation with "
             "its own shift schedule. That makes the market a multi-site "
             "software sale rather than a one-off consulting job.",
        tags=("market", "sam"),
    ),
    Fact(
        key="port_demurrage_usd_day",
        label="Ship demurrage in congested Algerian ports",
        value=5000,
        unit="USD/day/ship",
        kind="measured",
        source="Recovery Advisers market alert — Algeria customs & port delays",
        url="https://www.recoveryadvisers.com/insights/market-alert-algeria/",
        as_of="2025",
        note="Charged after the third day of delay. Waits passed 7 days in "
             "Algiers and Skikda, with up to 15 ships at anchor at peak. Proof "
             "that logistics timing errors in Algeria are already priced in "
             "hard currency.",
        tags=("market", "problem", "expansion"),
    ),
    Fact(
        key="algiers_port_wait_days",
        label="Ship waiting time, port of Algiers",
        value=7,
        unit="days",
        kind="measured",
        source="Port congestion monitoring — Algiers & Skikda >7 days",
        url="https://www.gocomet.com/real-time-port-congestion/algeria",
        as_of="2025",
        note="Bejaia and Djen-Djen 5-6 days, Oran about 3. Sets up the "
             "expansion vertical: bonded-warehouse and customs labour.",
        tags=("market", "expansion"),
    ),

    # ---- Payroll & compliance -------------------------------------------
    Fact(
        key="irg_exemption_monthly",
        label="IRG exemption threshold (monthly salary)",
        value=_RULES["irg"]["exempt_taxable_up_to"],
        unit="DZD/month",
        kind="measured",
        source="DGI — IRG traitements et salaires (LF 2022 reform)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Monthly salaries at or below 30,000 DZD pay no income tax. As "
             "the SNMG is 24,000, minimum-wage staff are exempt, which the "
             "payroll engine must reflect exactly.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_abatement",
        label="IRG proportional abatement on salary tax",
        value=_RULES["irg"]["abatement_rate"],
        unit="fraction of computed IRG",
        kind="measured",
        source="DGI — 40% abatement, floor 1,000 / cap 1,500 DZD per month",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Applied to the scale-computed tax, bounded to [1000, 1500] "
             "DZD/month.",
        tags=("payroll",),
    ),
    Fact(
        key="irg_family_reduction",
        label="IRG reduction per dependant",
        value=_RULES["irg"]["family_reduction"],
        unit="DZD/month each",
        kind="measured",
        source="DGI — 1,500 DZD/month for a non-earning spouse and per child (max 5)",
        url="https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires",
        as_of="2025",
        note="Reduces monthly IRG directly. A real deployment collects each "
             "employee's dependants; the demo defaults to zero.",
        tags=("payroll",),
    ),
    Fact(
        key="cnas_social_works",
        label="CNAS social-works levy (inside the employer share)",
        value=0.005,
        unit="fraction of gross",
        kind="measured",
        source="CLEISS / CNAS — employer 25% across 5 branches + 0.5% oeuvres sociales",
        url="https://www.cleiss.fr/docs/cotisations/algerie.html",
        as_of="2025",
        note="The employer share splits into social insurance 12.5%, pension "
             "10%, work accidents 1.25%, unemployment 1%, early retirement "
             "0.25%, plus 0.5% social works.",
        tags=("payroll",),
    ),

    # ---- HR / leave law --------------------------------------------------
    Fact(
        key="annual_leave_days",
        label="Legal paid annual leave",
        value=30,
        unit="days/year",
        kind="measured",
        source="Algerian labour code: 2.5 days earned per month worked",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="30 days a year, earned at 2.5 a month. Southern (Saharan) "
             "wilayas add 10 days (40 in total). The leave engine accrues and "
             "enforces this exactly.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="south_leave_bonus_days",
        label="Extra annual leave, southern wilayas",
        value=10,
        unit="days/year",
        kind="measured",
        source="Algerian labour code: Saharan wilayas",
        url="https://vacationtracker.io/leave-laws/africa/algeria/",
        as_of="2024",
        note="Employees in the southern wilayas get 40 days in total.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="maternity_leave_weeks",
        label="Maternity leave",
        value=14,
        unit="weeks",
        kind="measured",
        source="Algerian labour / social-security code: full pay",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="14 weeks at full pay (typically 6 before, 8 after birth), "
             "funded by CNAS.",
        tags=("hr", "leave"),
    ),
    Fact(
        key="sick_leave_split_day",
        label="Sick-pay rate switch day",
        value=15,
        unit="days",
        kind="measured",
        source="Algerian social-security rules: 50% for the first 15 days, then 100%",
        url="https://rivermate.com/guides/algeria/leave",
        as_of="2024",
        note="The first 15 days at half pay; full pay from day 16 or on "
             "hospitalisation.",
        tags=("hr", "leave"),
    ),

    # ---- Aviation vertical (Air Algerie / Algiers airport) ----------------
    Fact(
        key="airalgerie_pax_2025",
        label="Air Algerie passengers, 2025",
        value=8_800_000,
        unit="passengers/year",
        kind="measured",
        source="Air Algerie 2026 transformation plan reporting (DzairTube)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="2025",
        note="Up about 11% on 2024. The growth curve the airport has to "
             "staff for.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="airalgerie_pax_target_2026",
        label="Air Algerie passenger target, 2026",
        value=10_000_000,
        unit="passengers/year",
        kind="measured",
        source="Air Algerie 2026 expansion strategy (DzairTube / Travel & Tour World)",
        url="https://www.dzair-tube.dz/en/air-algerie-targets-nearly-10-million-passengers-in-2026-as-ambitious-transformation-drive-gains-momentum/",
        as_of="2026 target",
        note="A target of about 10M, plus about 60 new aircraft (Boeing 737 "
             "MAX 8/9, wide-bodies, ATR). Fast growth on a congested hub is the "
             "pressure the airport module handles.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="alg_pax_2024",
        label="Algiers airport passengers, 2024",
        value=9_151_517,
        unit="passengers/year",
        kind="measured",
        source="Houari Boumediene Airport traffic figures",
        url="https://en.wikipedia.org/wiki/Houari_Boumediene_Airport",
        as_of="2024",
        note="ALG is Air Algerie's main hub, with documented peak-period "
             "delays and at least one widely reported day of cascading delays.",
        tags=("aviation", "market"),
    ),
    Fact(
        key="reactionary_delay_share",
        label="Reactionary (knock-on) share of flight delays",
        value=0.45,
        unit="fraction",
        kind="measured",
        source="Industry norm for reactionary/cascade delay (Eurocontrol-style benchmark)",
        as_of="general",
        note="About 40-50% of all flight delay is inherited from an earlier "
             "flight. Our cascade model reproduces this share from first "
             "principles, which is a validity check.",
        tags=("aviation",),
    ),

    # ---- Startup / funding context ---------------------------------------
    Fact(
        key="asf_fund_dzd",
        label="Algerian Startup Fund capital",
        value=2_400_000_000,
        unit="DZD",
        kind="measured",
        source="Algerian Startup Fund (ASF), capitalised by six public banks",
        url="https://asf.dz/",
        as_of="2026",
        note="100+ startups funded from 350+ applications. Relevant as a "
             "realistic first cheque for this company.",
        tags=("funding",),
    ),
    Fact(
        key="startup_label_exemption_years",
        label="Startup Label tax exemption",
        value=4,
        unit="years",
        kind="measured",
        source="startup.dz — Label Startup benefits",
        url="https://www.upgrowth.dz/startup-algerie",
        as_of="2026",
        note="4 years exempt from corporate tax (IBS), professional activity "
             "tax (TAP) and founders' income tax, plus 0% VAT on imported "
             "equipment. Changes the cash calculation materially.",
        tags=("funding",),
    ),

    # ---- Live API sources -------------------------------------------------
    Fact(
        key="weather_api",
        label="Historical and forecast weather",
        value="open-meteo",
        unit="",
        kind="live",
        source="Open-Meteo (ERA5 reanalysis archive + operational forecast)",
        url="https://open-meteo.com/",
        note="Free, no API key, per coordinate. Gives real daily weather for "
             "each wilaya capital, historical and forecast.",
        tags=("data",),
    ),
    Fact(
        key="macro_api",
        label="Algeria macroeconomic indicators",
        value="worldbank",
        unit="",
        kind="live",
        source="World Bank Open Data: country DZA",
        url="https://data.worldbank.org/country/DZ",
        note="Inflation, population, labour force. Used to index salaries and "
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
        source="Tawzia model",
        note="Manual sorting with a handheld scanner. The first figure a pilot "
             "client replaces with its own measured throughput: the whole cost "
             "model scales on it, so we expose it as a slider.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="overtime_premium",
        label="Overtime premium",
        value=0.50,
        unit="fraction above the base hourly rate",
        kind="assumption",
        source="Tawzia model, aligned with Algerian labour-code practice",
        note="Algerian law sets overtime as a premium on the base hourly rate; "
             "50% is the usual daytime value. Night and rest-day work carry "
             "higher premiums, modelled separately.",
        tags=("labour", "assumption"),
    ),
    # ---- Sourcing and skills: framing assumptions ------------------------
    # The channel directory names real institutions; the figures attached to
    # each channel are modelled, because no Algerian operator publishes cost
    # per hire. Registered here so the Sources page shows them.
    Fact(
        key="applicants_per_hire",
        label="Applications needed per hire",
        value=8.0,
        unit="applications/hire",
        kind="assumption",
        source="Tawzia model",
        note="Funnel ratio used to size a sourcing campaign. Varies a lot by "
             "channel and role; the first value a pilot replaces with the "
             "client's measured ratio.",
        tags=("sourcing", "assumption"),
    ),
    Fact(
        key="sourcing_shortlist_rate",
        label="Share of applications shortlisted",
        value=0.22,
        unit="fraction",
        kind="assumption",
        source="Tawzia model",
        note="Combined with each channel's quality, gives expected hires per "
             "campaign. Channel volumes, costs and lead times use the same "
             "framing.",
        tags=("sourcing", "assumption"),
    ),
    Fact(
        key="training_cost_per_day",
        label="Direct cost of one training day per person",
        value=3500,
        unit="DZD/day/person",
        kind="assumption",
        source="Tawzia model",
        note="Trainer and materials, trainee salary excluded. With 4 days per "
             "skill level gained, this costs the training plan and the train or "
             "hire choice. A client grid or a CFPA agreement replaces it.",
        tags=("skills", "assumption"),
    ),
    Fact(
        key="external_recruit_cost",
        label="Sourcing and selection cost of an external hire",
        value=45000,
        unit="DZD/hire",
        kind="assumption",
        source="Tawzia model",
        note="Salary excluded, and ramp-up (2 months at half productivity) "
             "counted separately. The benchmark against internal mobility; the "
             "engine recommends external hiring when the skills gap is too wide.",
        tags=("skills", "assumption"),
    ),
    Fact(
        key="temp_agency_markup",
        label="Temp agency markup over direct employment",
        value=0.35,
        unit="fraction",
        kind="assumption",
        source="Tawzia model",
        note="Agency fee on top of a direct employee's loaded hourly cost. "
             "Varies a lot by wilaya and how late the request is, which is the "
             "cost forecasting removes.",
        tags=("labour", "assumption"),
    ),
    Fact(
        key="understaffing_penalty_multiple",
        label="Cost multiple of an uncovered hour vs a covered hour",
        value=2.4,
        unit="×",
        kind="assumption",
        source="Tawzia model",
        note="An hour of demand you cannot serve costs more than the salary "
             "saved. In cash-on-delivery e-commerce it costs the failed delivery, "
             "the return trip and part of customer lifetime value. Kept "
             "conservative and exposed: the assumption most likely challenged.",
        tags=("cost", "assumption"),
    ),

    # ---- Sector-specific assumptions (signature features) ----------------
    Fact(
        key="ecom_avg_order_value_dzd",
        label="Average e-commerce order value (COD)",
        value=3200,
        unit="DZD/order",
        kind="assumption",
        source="Tawzia model",
        note="Average cash-on-delivery order value, to cost the cash couriers "
             "carry and the value tied up in returns. A pilot replaces it with "
             "the merchant's real basket.",
        tags=("delivery", "assumption"),
    ),
    Fact(
        key="transport_daily_driving_limit_h",
        label="Daily driving limit per driver",
        value=9.0,
        unit="hours/day",
        kind="assumption",
        source="Tawzia model, aligned with road-transport practice",
        note="Indicative driving-time cap before mandatory rest, used to size "
             "the fleet without breaches. An operator sets the exact value from "
             "its agreement and transport regulation.",
        tags=("transport", "assumption"),
    ),
    Fact(
        key="school_students_per_teacher",
        label="Students per teacher",
        value=25,
        unit="students/teacher",
        kind="assumption",
        source="Tawzia model, Algerian school-system order of magnitude",
        note="Indicative ratio to size the teaching staff. A school replaces it "
             "with its real class sizes.",
        tags=("school", "assumption"),
    ),
    Fact(
        key="school_students_per_invigilator",
        label="Students per invigilator during exams",
        value=20,
        unit="students/invigilator",
        kind="assumption",
        source="Tawzia model, BEM/BAC invigilation practice",
        note="Indicative exam-room invigilation ratio (term exams, BEM, BAC). "
             "Costs the extra invigilation during exam periods.",
        tags=("school", "assumption"),
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
