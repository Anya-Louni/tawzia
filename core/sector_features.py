"""
core/sector_features.py
-----------------------
A signature feature for each sector.

Changing the activity type must change what the app *does*, not just the volume
numbers. This module gives every sector its own signature analysis , the one
computation that a manager in that sector actually cares about , built on the
same real Algerian cost stack, calendar and forecast as the rest of the app.

    E-commerce hub       -> COD cash and returns exposure
    Airport handling     -> Diaspora wave and passenger peak
    Retail distribution  -> Ramadan / pre-Eid wave (picking reinforcement)
    Hospitality          -> Housekeeping load by occupancy
    Transport and fleet  -> Driving-time compliance
    School               -> School calendar and staffing (exams)

Each `compute()` returns a `SectorFeature` the page renders identically, so the
UI stays simple while the content is genuinely different per sector. Everything
is grounded: market figures come from core/sources (cited), the labour figures
from core/labour_dz, the demand from the same forecast the dashboard uses.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import labour_dz, sources


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------

@dataclass
class SectorFeature:
    key: str
    title: str
    icon: str
    intro: str
    metrics: list = field(default_factory=list)     # (label, display, help)
    table: Optional[pd.DataFrame] = None
    table_caption: str = ""
    chart: Optional[pd.DataFrame] = None            # indexed df for st.*_chart
    chart_kind: str = "bar"
    insight: str = ""
    notes: list = field(default_factory=list)       # citations / assumptions


SIGNATURES = {
    "ecom_hub": {"title": "COD cash and returns", "icon": ":material/payments:",
                 "intro": "In a market where about 95% of orders are paid on delivery, "
                          "every parcel out carries cash and a return risk. Here is "
                          "the COD cash collected, the expected returns and the value "
                          "tied up over the horizon."},
    "airport_ground": {"title": "Diaspora wave and passenger peak",
                       "icon": ":material/flight_takeoff:",
                       "intro": "Algerian airports run on the summer diaspora return, "
                                "a peak any Europe-calibrated model reads as a trough. "
                                "Here is the passenger peak and the check-in staff "
                                "needed at the peak."},
    "retail_dc": {"title": "Ramadan and pre-Eid wave", "icon": ":material/local_grocery_store:",
                  "intro": "Food distribution is the most exposed to Ramadan: load "
                           "concentrates on the first days of the month and before "
                           "Eid. Here is the picking reinforcement to pre-book, and when."},
    "hotel": {"title": "Housekeeping load by occupancy", "icon": ":material/bed:",
              "intro": "Occupancy drives the whole floor: rooms to clean, the "
                       "check-out wave, the weekend peak. Here are the housekeepers "
                       "and front-desk staff to line up with forecast occupancy."},
    "transport": {"title": "Driving-time compliance", "icon": ":material/local_shipping:",
                  "intro": "Drivers are bound by a daily driving limit. Here are the "
                           "driving hours required, the drivers needed to stay within "
                           "limits, and the overload days (pre-Eid) to reinforce."},
    "school": {"title": "School calendar and staffing", "icon": ":material/school:",
               "intro": "A school follows the Algerian school calendar, not the "
                        "market: the rentree is the peak, holidays empty the site, "
                        "and exams (BEM/BAC) need extra invigilation. Here is the "
                        "current phase and the staffing."},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dzd(n: float) -> str:
    if abs(n) >= 1e6:
        return f"{n / 1e6:,.2f} M DZD"
    if abs(n) >= 1e3:
        return f"{n / 1e3:,.0f} k DZD"
    return f"{n:,.0f} DZD"


def _ceil(x: float) -> int:
    return int(math.ceil(x)) if x > 0 else 0


def _daily_volume(plan: Optional[dict]) -> pd.DataFrame:
    """Forecast volume aggregated to one row per day, or empty if unavailable."""
    if not plan or "forecast" not in plan:
        return pd.DataFrame(columns=["date", "volume"])
    fc = plan["forecast"]
    if fc is None or fc.empty or "forecast" not in fc.columns:
        return pd.DataFrame(columns=["date", "volume"])
    d = fc.groupby("date", as_index=False)["forecast"].sum().rename(
        columns={"forecast": "volume"})
    d["date"] = pd.to_datetime(d["date"])
    return d.sort_values("date").reset_index(drop=True)


def _shift_hours() -> float:
    return labour_dz.SHIFTS["morning"].hours


def _cite(*keys) -> list:
    out = []
    for k in keys:
        try:
            f = sources.get(k)
            out.append(f"{f.label}: {f.value} {f.unit}, {f.cite()}")
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Algerian school-year calendar (indicative windows, labelled as such)
# ---------------------------------------------------------------------------

_PHASE_COLOUR = {"cours": "blue", "vacances": "green", "examens": "red", "ete": "orange"}


def school_timeline(as_of: _dt.date) -> list:
    """
    The phases of the Algerian school year containing (or next following)
    `as_of`. Dates are indicative (the Ministry fixes them each year); the
    structure (rentree, three terms, breaks, June exams) is stable. Returns ordered dicts: {phase, kind, start, end}.
    """
    # August onward belongs to the upcoming school year (September rentree ahead).
    y = as_of.year if as_of.month >= 8 else as_of.year - 1
    D = _dt.date
    return [
        {"phase": "Summer holidays", "kind": "ete", "start": D(y, 7, 6), "end": D(y, 9, 20)},
        {"phase": "Rentree and term 1", "kind": "cours", "start": D(y, 9, 21), "end": D(y, 11, 1)},
        {"phase": "Autumn break", "kind": "vacances", "start": D(y, 11, 2), "end": D(y, 11, 8)},
        {"phase": "Term 1 (continued)", "kind": "cours", "start": D(y, 11, 9), "end": D(y, 12, 17)},
        {"phase": "Winter break", "kind": "vacances", "start": D(y, 12, 18), "end": D(y + 1, 1, 4)},
        {"phase": "Term 2", "kind": "cours", "start": D(y + 1, 1, 5), "end": D(y + 1, 3, 18)},
        {"phase": "Spring break", "kind": "vacances", "start": D(y + 1, 3, 19), "end": D(y + 1, 4, 5)},
        {"phase": "Term 3", "kind": "cours", "start": D(y + 1, 4, 6), "end": D(y + 1, 6, 7)},
        {"phase": "Exams (BEM / BAC)", "kind": "examens", "start": D(y + 1, 6, 8), "end": D(y + 1, 6, 25)},
        {"phase": "Year end and summer", "kind": "ete", "start": D(y + 1, 6, 26), "end": D(y + 1, 9, 20)},
    ]


def current_school_phase(as_of: _dt.date) -> dict:
    for ph in school_timeline(as_of):
        if ph["start"] <= as_of <= ph["end"]:
            return ph
    return school_timeline(as_of)[0]


def next_school_event(as_of: _dt.date) -> Optional[dict]:
    future = [ph for ph in school_timeline(as_of) if ph["start"] > as_of]
    return min(future, key=lambda p: p["start"]) if future else None


# ---------------------------------------------------------------------------
# Per-sector signature computations
# ---------------------------------------------------------------------------

def _feat_ecom(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["ecom_hub"]
    d = _daily_volume(plan)
    f = SectorFeature("ecom_hub", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Forecast unavailable (offline mode). Turn live API calls back on."
        return f
    aov = sources.value("ecom_avg_order_value_dzd")
    cod = sources.value("cod_share")
    ret = sources.value("cod_return_rate")
    d["cash_cod"] = d["volume"] * cod * aov
    d["retours"] = d["volume"] * ret
    d["immobilise"] = d["retours"] * aov

    peak = d.loc[d["volume"].idxmax()]
    f.metrics = [
        ("Parcels (horizon)", f"{d['volume'].sum():,.0f}", "Total forecast over the horizon."),
        ("COD cash / day", _dzd(d["cash_cod"].mean()),
         "Cash collected by couriers on an average day (to reconcile)."),
        ("Expected returns / day", f"{d['retours'].mean():,.0f}",
         "Parcels returned at the MENA rate, to check and restock."),
        ("Value tied up (horizon)", _dzd(d["immobilise"].sum()),
         "Value locked in returns: delivery paid twice."),
    ]
    show = d.copy()
    show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={
        "date": "Day", "volume": "Parcels", "cash_cod": "COD cash (DZD)",
        "retours": "Returns", "immobilise": "Tied up (DZD)"})[
        ["Day", "Parcels", "COD cash (DZD)", "Returns", "Tied up (DZD)"]]
    f.table_caption = "Cash and returns per day, at market parameters."
    f.chart = d.set_index("date")[["cash_cod"]].rename(columns={"cash_cod": "COD cash (DZD)"})
    f.chart_kind = "bar"
    f.insight = (f"Peak day on {pd.to_datetime(peak['date']):%d %b}: "
                 f"{_dzd(peak['volume'] * cod * aov)} of COD cash to reconcile and "
                 f"{peak['volume'] * ret:,.0f} returns to process. Reinforce the "
                 f"cash desk and returns control that day.")
    f.notes = _cite("cod_share", "cod_return_rate", "ecom_avg_order_value_dzd")
    return f


def _feat_airport(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["airport_ground"]
    d = _daily_volume(plan)
    f = SectorFeature("airport_ground", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Forecast unavailable (offline mode)."
        return f
    agent = labour_dz.ROLES["checkin_agent"].productivity_per_hour * _shift_hours()
    d["agents"] = np.ceil(d["volume"] / max(agent, 1)).astype(int)
    peak = d.loc[d["volume"].idxmax()]
    trough = d.loc[d["volume"].idxmin()]
    swing = peak["volume"] / max(trough["volume"], 1)
    f.metrics = [
        ("Passengers (horizon)", f"{d['volume'].sum():,.0f}", "Total forecast over the horizon."),
        ("Peak passengers / day", f"{peak['volume']:,.0f}",
         f"Busiest day ({pd.to_datetime(peak['date']):%d %b})."),
        ("Check-in agents at peak", f"{int(peak['agents'])}",
         "Staff needed for check-in throughput on the peak day."),
        ("Peak/trough swing", f"{swing:.1f}x",
         "Gap between the busiest and quietest day of the horizon."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={"date": "Day", "volume": "Passengers",
                                   "agents": "Check-in agents"})[
        ["Day", "Passengers", "Check-in agents"]]
    f.table_caption = "Passengers and check-in staff required per day."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Passengers"})
    f.chart_kind = "area"
    f.insight = ("The **Airport** module goes further: hour-by-hour passenger flow "
                 "and delay cascades. The summer diaspora peak is the real "
                 "annual peak.")
    f.notes = _cite("alg_pax_2024", "airalgerie_pax_target_2026")
    return f


def _feat_retail(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["retail_dc"]
    d = _daily_volume(plan)
    f = SectorFeature("retail_dc", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Forecast unavailable (offline mode)."
        return f
    prod = labour_dz.ROLES["warehouse_op"].productivity_per_hour * _shift_hours()
    baseline = float(d["volume"].median())
    d["surplus"] = (d["volume"] - baseline).clip(lower=0)
    d["renfort"] = np.ceil(d["surplus"] / max(prod, 1)).astype(int)
    d["pointe"] = d["volume"] >= baseline * 1.25
    surge = d[d["pointe"]]
    peak = d.loc[d["volume"].idxmax()]
    first_surge = surge["date"].min() if not surge.empty else None
    f.metrics = [
        ("Median load / day", f"{baseline:,.0f}", "Cartons on an ordinary day."),
        ("Peak load", f"{peak['volume']:,.0f}",
         f"Busiest day ({pd.to_datetime(peak['date']):%d %b})."),
        ("Peak days", f"{int(d['pointe'].sum())}",
         "Days at least 25% above the median over the horizon."),
        ("Reinforcement to pre-book", f"{int(d['renfort'].sum())} staff-days",
         "Temp staff-days to book to absorb the peaks."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    show["Peak"] = np.where(show["pointe"], "● peak", "")
    f.table = show.rename(columns={"date": "Day", "volume": "Cartons",
                                   "renfort": "Reinforcement (staff)"})[
        ["Day", "Cartons", "Reinforcement (staff)", "Peak"]]
    f.table_caption = "Load, picking reinforcement and peak days."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Cartons"})
    if first_surge is not None:
        book_by = (pd.to_datetime(first_surge) - pd.Timedelta(days=3))
        f.insight = (f"First peak on {pd.to_datetime(first_surge):%d %b}: pre-book temps "
                     f"before {book_by:%d %b} (3 days' notice) to avoid the "
                     f"last-minute markup.")
    else:
        f.insight = ("No marked peak over this horizon: load is steady. Watch the "
                     "start of Ramadan for the front-load.")
    return f


def _feat_hotel(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["hotel"]
    d = _daily_volume(plan)
    f = SectorFeature("hotel", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Forecast unavailable (offline mode)."
        return f
    hk = labour_dz.ROLES["housekeeper"].productivity_per_hour * _shift_hours()
    fd = labour_dz.ROLES["front_desk"].productivity_per_hour * _shift_hours()
    d["menage"] = np.ceil(d["volume"] / max(hk, 1)).astype(int)
    d["reception"] = np.ceil(d["volume"] / max(fd, 1)).astype(int)
    d["weekday"] = d["date"].dt.weekday
    peak = d.loc[d["volume"].idxmax()]
    wk = d[d["weekday"].isin([3, 4])]["volume"].mean()   # Thu-Fri leisure
    wd = d[~d["weekday"].isin([3, 4, 5])]["volume"].mean()
    f.metrics = [
        ("Average occupancy", f"{d['volume'].mean():,.0f}", "Occupied rooms / day."),
        ("Peak occupancy", f"{peak['volume']:,.0f}",
         f"Fullest day ({pd.to_datetime(peak['date']):%d %b})."),
        ("Housekeeping at peak", f"{int(peak['menage'])}",
         "Housekeepers needed on the peak day."),
        ("Front desk at peak", f"{int(peak['reception'])}",
         "Receptionists needed at peak arrivals."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={"date": "Day", "volume": "Rooms occ.",
                                   "menage": "Housekeeping", "reception": "Front desk"})[
        ["Day", "Rooms occ.", "Housekeeping", "Front desk"]]
    f.table_caption = "Occupancy and floor/front-desk staff per day."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Occupied rooms"})
    f.chart_kind = "area"
    lift = (wk / wd - 1) * 100 if wd else 0
    sens = "above" if lift >= 0 else "below"
    f.insight = (f"The leisure weekend (Thu-Fri) runs about {abs(lift):.0f}% "
                 f"{sens} the week: focus housekeeping on the check-out wave "
                 f"and reinforce the front desk at arrivals.")
    return f


def _feat_transport(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["transport"]
    d = _daily_volume(plan)
    f = SectorFeature("transport", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Forecast unavailable (offline mode)."
        return f
    prod = labour_dz.ROLES["driver"].productivity_per_hour   # trips / hour
    limit = sources.value("transport_daily_driving_limit_h")
    d["heures_conduite"] = d["volume"] / max(prod, 1)
    d["chauffeurs"] = np.ceil(d["heures_conduite"] / max(limit, 1)).astype(int)
    med = float(d["chauffeurs"].median())
    d["surchauffe"] = d["chauffeurs"] >= med * 1.3
    peak = d.loc[d["volume"].idxmax()]
    f.metrics = [
        ("Driving hours / day", f"{d['heures_conduite'].mean():,.0f} h",
         "Total driving hours required on an average day."),
        ("Drivers needed at peak", f"{int(peak['chauffeurs'])}",
         f"To carry the load without exceeding {limit:.0f} h per driver "
         f"({pd.to_datetime(peak['date']):%d %b})."),
        ("Limit / driver", f"{limit:.0f} h/day",
         "Driving cap before mandatory rest (indicative)."),
        ("Overload days", f"{int(d['surchauffe'].sum())}",
         "Days at least 30% above median staffing: breach and fatigue risk."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    show["Overload"] = np.where(show["surchauffe"], "● reinforce", "")
    show["heures_conduite"] = show["heures_conduite"].round(0)
    f.table = show.rename(columns={"date": "Day", "volume": "Trips",
                                   "heures_conduite": "Driving hours",
                                   "chauffeurs": "Drivers"})[
        ["Day", "Trips", "Driving hours", "Drivers", "Overload"]]
    f.table_caption = "Trips, driving hours and compliant staffing per day."
    f.chart = d.set_index("date")[["chauffeurs"]].rename(columns={"chauffeurs": "Drivers needed"})
    f.insight = ("Overload days (typically pre-Eid) need relief drivers: without "
                 "them, carrying the load forces drivers past their limits, a "
                 "legal and safety risk, not just extra cost.")
    f.notes = _cite("transport_daily_driving_limit_h")
    return f


def _feat_school(plan, people, as_of) -> SectorFeature:
    from . import demand as _demand
    sig = SIGNATURES["school"]
    f = SectorFeature("school", sig["title"], sig["icon"], sig["intro"])

    phase = current_school_phase(as_of)
    nxt = next_school_event(as_of)
    students = int(_demand.PROFILES["school"].base_daily_volume)
    spt = sources.value("school_students_per_teacher")
    inv = sources.value("school_students_per_invigilator")
    teachers_needed = _ceil(students / spt)
    invigilators = _ceil(students / inv)
    staff_now = len(people) if people else 0

    days_to = (nxt["start"] - as_of).days if nxt else None
    f.metrics = [
        ("Current phase", phase["phase"], "Position in the Algerian school year."),
        ("Next milestone",
         f"{nxt['phase']} (D-{days_to})" if nxt else "-",
         f"Starts {nxt['start']:%d %b %Y}." if nxt else ""),
        ("Teachers needed", f"{teachers_needed}",
         f"For {students:,} students at {spt} students per teacher."),
        ("Exam invigilators", f"{invigilators}",
         f"Extra invigilation during BEM/BAC ({inv} students per invigilator)."),
    ]

    tl = school_timeline(as_of)
    rows = []
    for ph in tl:
        rows.append({
            "Phase": ph["phase"],
            "Type": {"cours": "Classes", "vacances": "Holidays",
                     "examens": "Exams", "ete": "Summer"}[ph["kind"]],
            "Start": ph["start"].strftime("%d %b %Y"),
            "End": ph["end"].strftime("%d %b %Y"),
            "Now": "●" if ph is phase else "",
        })
    f.table = pd.DataFrame(rows)
    f.table_caption = ("Algerian school calendar (indicative dates; the Ministry "
                       "sets the exact ones each year).")

    if phase["kind"] == "examens":
        f.insight = (f"Exam period: bring in about {invigilators} invigilators on top "
                     f"of teaching staff, and freeze staff leave until exams end.")
    elif phase["kind"] in ("ete", "vacances") and nxt:
        f.insight = (f"Site in {phase['phase'].lower()}: the window to hire and train "
                     f"before {nxt['phase']} (D-{days_to}). Current staff: "
                     f"{staff_now}, target about {teachers_needed}.")
    else:
        gap = teachers_needed - staff_now
        f.insight = (f"In term: staff {staff_now} against a need of about "
                     f"{teachers_needed} teachers"
                     + (f", about {gap} short." if gap > 0 else ", staffing sufficient."))
    f.notes = _cite("school_students_per_teacher", "school_students_per_invigilator")
    return f


_DISPATCH = {
    "ecom_hub": _feat_ecom,
    "airport_ground": _feat_airport,
    "retail_dc": _feat_retail,
    "hotel": _feat_hotel,
    "transport": _feat_transport,
    "school": _feat_school,
}


def has_feature(profile_key: str) -> bool:
    return profile_key in _DISPATCH


def compute(profile_key: str, plan: Optional[dict], people: Optional[list],
            as_of: Optional[_dt.date] = None) -> Optional[SectorFeature]:
    """Compute the signature feature for a sector, or None if unknown."""
    as_of = as_of or _dt.date.today()
    fn = _DISPATCH.get(profile_key)
    if fn is None:
        return None
    return fn(plan, people or [], as_of)


if __name__ == "__main__":
    from . import demand as _d, hr

    print("Sector signature features, self check\n")
    as_of = _dt.date.today()
    # a tiny fake plan: 14 days of volume per sector base
    for key, prof in _d.PROFILES.items():
        dates = pd.date_range(as_of, periods=14, freq="D")
        vol = np.linspace(prof.base_daily_volume * 0.7, prof.base_daily_volume * 1.6, 14)
        fc = pd.DataFrame({"date": np.repeat(dates, 1), "shift": "morning",
                           "forecast": vol})
        people = hr.sample_workforce(prof.primary_role, 30, "Alger")
        feat = compute(key, {"forecast": fc}, people, as_of)
        print(f"— {prof.label}  →  {feat.title}")
        for label, disp, _ in feat.metrics:
            print(f"     {label:<28} {disp}")
        print(f"     » {feat.insight[:110]}")
        print()
